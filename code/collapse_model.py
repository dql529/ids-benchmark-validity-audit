#!/usr/bin/env python3
"""崩溃点的解析预测：为什么 rpm 在 σ=0.5 崩、force-neutral 撑到 σ=1.0？

机制假说
--------
trivial 规则 = flag iff dev < tau，tau = train 良性 dev 的 0.1 分位。
合成钟下良性 dt_id ≈ nominal 恒定 → dev 极度集中在 1 附近 → tau 高达 0.7384，
于是任何"来得比 nominal 快"的注入帧都被干净地切出来。

Arm B 给良性 gap 乘 lognormal(−σ²/2, σ) → 良性 dev 被同一乘子拉开：
    tau(σ) ≈ tau₀ · exp(−σ²/2 + σ·z₀.₀₀₁),  z₀.₀₀₁ = Φ⁻¹(0.001) = −3.090
攻击帧不被抖动（CTAT 攻击帧独立成轴），其 dev 分布不动。
→ **崩溃发生在 tau(σ) 掉到攻击帧 dev 主体之下**，即
    σ* = min{σ : tau(σ) < d_a},  d_a = 攻击帧 dev 的某个分位

预测因此只依赖一个可观测量 d_a：注入节奏相对该 ID nominal 周期的比值。
d_a 越小（注入相对越快），tau 要掉得越低才漏 → 崩溃越晚。

本脚本：从 cache 直接算每个文件的 (tau₀, d_a)，给出 σ* 预测，与实测崩溃点对照。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import norm, spearmanr

import jitter_sensitivity as J

ROOT = Path(__file__).resolve().parent.parent
D = pd.read_csv(ROOT / "results" / "jitter_sensitivity.csv")
BASE = D[D.arm == "none"].set_index(["benchmark", "file"])
AGG = (D[D.arm != "none"].groupby(["benchmark", "file", "arm", "level"])
       ["trivial_f1"].mean().reset_index())
Z = float(norm.ppf(0.001))          # -3.0902
SIGMAS = [0.05, 0.10, 0.20, 0.50, 1.00]


def tau_of(sigma: float, tau0: float) -> float:
    """lognormal 乘子把良性 dev 整体缩放, 0.1 分位随之下移。"""
    return tau0 * np.exp(-0.5 * sigma ** 2 + sigma * Z)


def observed_collapse(bench: str, f: str, base_f1: float) -> float:
    g = AGG[(AGG.benchmark == bench) & (AGG.file == f) & (AGG.arm == "B")].sort_values("level")
    hit = g[g.trivial_f1 < base_f1 * 0.5]
    return float(hit.level.iloc[0]) if len(hit) else np.inf


def predicted_collapse(tau0: float, d_a: float) -> float:
    for s in SIGMAS:
        if tau_of(s, tau0) < d_a:
            return s
    return np.inf


avail = {p.stem for p in (Path(__file__).resolve().parent / "cache").glob("*.npz")}
b = BASE.loc["ctat"]
strong = b[b.trivial_f1 > 0.3].index.tolist()

rows = []
for f in strong:
    key = "ctat__" + f
    ts, aid, y, seg = J._load(key)
    tr = J._load(J.resolve_trainset("ctat", key, avail))
    # 与 evaluate() 同口径重算 dev（level=0）
    dt_tr = J.dt_id_of(tr[0], tr[1], tr[3])
    ben = (tr[2] == 0) & (dt_tr > 0)
    nominal = pd.Series(dt_tr[ben]).groupby(tr[1][ben]).median()
    gm = max(float(np.median(dt_tr[ben])), 1e-9)
    keys = nominal.index.to_numpy()
    vals = np.where(nominal.to_numpy() <= 0, gm, nominal.to_numpy())

    def dev_of(dt, a):
        pos = np.clip(np.searchsorted(keys, a), 0, len(keys) - 1)
        return dt / np.where(keys[pos] == a, vals[pos], gm)

    tau0 = float(np.quantile(dev_of(dt_tr, tr[1])[tr[2] == 0], 0.001))
    dev_te = dev_of(J.dt_id_of(ts, aid, seg), aid)
    d_atk = dev_te[y == 1]
    d_a = float(np.median(d_atk)) if len(d_atk) else np.nan

    base_f1 = float(b.loc[f, "trivial_f1"])
    rows.append({
        "file": f.split("|")[-1].replace(".csv", ""),
        "split": f.split("|")[0].replace("_vehicle", "").replace("_attack", ""),
        "tau0": round(tau0, 4),
        "d_a_median": round(d_a, 4),
        "base_trivial": round(base_f1, 4),
        "sigma_pred": predicted_collapse(tau0, d_a),
        "sigma_obs": observed_collapse("ctat", f, base_f1),
    })

df = pd.DataFrame(rows).sort_values("d_a_median")
print("=" * 104)
print("崩溃点预测 vs 实测（CTAT 16 个基线 trivial>0.3 的文件）")
print("=" * 104)
print(df.to_string(index=False))

ok = df[np.isfinite(df.sigma_obs) & np.isfinite(df.sigma_pred)]
exact = int((df.sigma_pred == df.sigma_obs).sum())
print(f"\n完全命中 {exact}/{len(df)}")
if len(ok) > 2:
    rho, p = spearmanr(ok.d_a_median, ok.sigma_obs)
    print(f"d_a 与实测崩溃点 Spearman ρ = {rho:.3f} (p = {p:.4f}, n = {len(ok)})")
    rho2, p2 = spearmanr(ok.sigma_pred, ok.sigma_obs)
    print(f"预测 σ* 与实测 σ* Spearman ρ = {rho2:.3f} (p = {p2:.4f})")

print("\n=== tau(σ) 曲线（tau₀ = 0.7384 时）===")
for s in [0.0] + SIGMAS:
    print(f"  σ={s:<5} tau={tau_of(s, 0.7384):.4f}")
