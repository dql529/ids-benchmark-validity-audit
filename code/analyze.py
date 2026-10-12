#!/usr/bin/env python3
"""Phase 5 结果分析：时钟扰动敏感性。

统计口径（Phase A.2b 健全性三问已内建）：
  - 每个 (file, arm, level) 先对 10 个 seed 取均值 → 再与该 file 的 level=0 基线配对
    （seed 不作独立样本，避免独立性违规）
  - 配对检验 = Wilcoxon signed-rank，n = 该基准的文件数（CTAT 40 / ROAD 13 / SynCAN 5）
  - floor 检查：单侧 Wilcoxon 最小可达 p = 2^-n（n=5 → 0.0625，永远不显著 → 只报方向）
  - 多重比较：每个基准 9 个 level，用 Holm 校正
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

RES = Path(__file__).resolve().parent.parent / "results"
D = pd.read_csv(RES / "jitter_sensitivity.csv")

BASE = D[D.arm == "none"].set_index(["benchmark", "file"])
PERT = D[D.arm != "none"]
SEED_MEAN = (PERT.groupby(["benchmark", "file", "arm", "level"])
             [["trivial_f1", "oracle_f1", "degenerate_f1"]].agg(["mean", "std"]))
SEED_MEAN.columns = ["_".join(c) for c in SEED_MEAN.columns]
SEED_MEAN = SEED_MEAN.reset_index()


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni 校正后的 p 值（保序）。"""
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(running, 1.0)
    return adj.tolist()


def compare(bench: str, metric: str) -> pd.DataFrame:
    rows = []
    sub = SEED_MEAN[SEED_MEAN.benchmark == bench]
    base = BASE.loc[bench][metric]
    for (arm, level), g in sub.groupby(["arm", "level"]):
        g = g.set_index("file")
        common = g.index.intersection(base.index)
        b = base.loc[common].to_numpy(float)
        a = g.loc[common, f"{metric}_mean"].to_numpy(float)
        d = a - b
        n = len(common)
        if np.allclose(d, 0):
            p, stat = 1.0, 0.0
        else:
            try:
                stat, p = stats.wilcoxon(a, b, zero_method="wilcox")
            except ValueError:
                stat, p = 0.0, 1.0
        sd = d.std(ddof=1) if n > 1 else 0.0
        rows.append({
            "arm": arm, "level": level, "n_files": n,
            "baseline_mean": round(float(b.mean()), 4),
            "perturbed_mean": round(float(a.mean()), 4),
            "delta_mean": round(float(d.mean()), 4),
            "delta_sd": round(float(sd), 4),
            "cohen_dz": round(float(d.mean() / sd), 3) if sd > 0 else np.nan,
            "p_raw": p,
            # ⛔ scipy.wilcoxon 默认 two-sided：全部同号时 W=0，最小可达 p = 2·2^-n = 2^-(n-1)。
            # 初版写 2^-n（单侧口径）→ ROAD 的 p=2.44e-4 (= 2^-12, n=13) 被漏判成"未饱和"。
            "floor_p": 2.0 ** (-(n - 1)),
        })
    out = pd.DataFrame(rows)
    out["p_holm"] = holm(out["p_raw"].tolist())
    out["floor_hit"] = out["p_raw"] <= out["floor_p"] * 1.001
    out["sig"] = (out["p_holm"] < 0.05) & (~out["floor_hit"])
    return out.sort_values(["arm", "level"])


def fmt(df: pd.DataFrame) -> str:
    show = df.copy()
    show["p_raw"] = show["p_raw"].map(lambda v: f"{v:.2e}")
    show["p_holm"] = show["p_holm"].map(lambda v: f"{v:.2e}")
    show["floor_p"] = show["floor_p"].map(lambda v: f"{v:.2e}")
    return show.to_string(index=False)


print("=" * 112)
print("Phase A.1 — 基线（level=0）与退化解对照")
print("=" * 112)
b = BASE.reset_index()
print(b.groupby("benchmark")[["trivial_f1", "oracle_f1", "degenerate_f1"]]
      .agg(["mean", "min", "max"]).round(4).to_string())

for metric in ["trivial_f1", "oracle_f1"]:
    for bench in ["ctat", "road", "syncan"]:
        print("\n" + "=" * 112)
        print(f"Phase A.2 — {bench.upper()} / {metric}  (配对 Wilcoxon vs level=0, Holm 校正)")
        print("=" * 112)
        print(fmt(compare(bench, metric)))

# ---- 关键格：Arm A @100µs（ROAD 自述 Kvaser 硬件精度）与 CTAT 强判别文件
print("\n" + "=" * 112)
print("Phase A.3 — 关键单元格明细")
print("=" * 112)
key_files = [
    ("ctat", "test_01_known_vehicle_known_attack|rpm-3.csv"),
    ("ctat", "test_01_known_vehicle_known_attack|force-neutral-3.csv"),
    ("ctat", "test_01_known_vehicle_known_attack|DoS-3.csv"),
    ("road", "correlated_signal_attack_2_masquerade.csv"),
    ("syncan", "test_flooding"),
]
for bench, f in key_files:
    b0 = BASE.loc[(bench, f)]
    print(f"\n{f}   [基线 trivial={b0.trivial_f1:.4f} oracle={b0.oracle_f1:.4f} "
          f"退化解={b0.degenerate_f1:.4f}]")
    g = SEED_MEAN[(SEED_MEAN.benchmark == bench) & (SEED_MEAN.file == f)]
    for _, r in g.sort_values(["arm", "level"]).iterrows():
        unit = "µs" if r.arm == "A" else "σ"
        print(f"   Arm {r.arm}  {r.level:>7.2f}{unit}   trivial {r.trivial_f1_mean:.4f}±{r.trivial_f1_std:.4f}"
              f"   oracle {r.oracle_f1_mean:.4f}±{r.oracle_f1_std:.4f}")

# ---- 崩溃点：trivial 跌破基线 50% 的最小 level
print("\n" + "=" * 112)
print("Phase A.4 — 崩溃点（各文件 trivial 首次跌破基线 50% 的 level；仅统计基线 >0.3 的文件）")
print("=" * 112)
for arm in ["A", "B"]:
    print(f"\nArm {arm}:")
    for bench in ["ctat", "road", "syncan"]:
        base = BASE.loc[bench]
        strong = base[base.trivial_f1 > 0.3].index
        if len(strong) == 0:
            print(f"  {bench:<7} 无基线 trivial>0.3 的文件")
            continue
        pts = []
        for f in strong:
            g = SEED_MEAN[(SEED_MEAN.benchmark == bench) & (SEED_MEAN.file == f)
                          & (SEED_MEAN.arm == arm)].sort_values("level")
            thr = base.loc[f, "trivial_f1"] * 0.5
            hit = g[g.trivial_f1_mean < thr]
            pts.append(float(hit.level.iloc[0]) if len(hit) else np.inf)
        finite = [p for p in pts if np.isfinite(p)]
        print(f"  {bench:<7} n={len(strong):>2}  崩溃文件 {len(finite)}/{len(strong)}"
              + (f"  最小崩溃 level={min(finite)}  中位={np.median(finite)}" if finite else "  全部未崩溃"))
