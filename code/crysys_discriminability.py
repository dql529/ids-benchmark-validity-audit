#!/usr/bin/env python3
"""Phase 6: 真实时序档上的 masquerade 判别性 —— 判别性地图缺的最后一档。

为什么需要：Phase 3 的判别性地图三个基准全是合成/网格化时钟，
"masquerade 时序不可判别"这个结论一直缺一个**真实时钟**上的对照。
CrySyS（Scientific Data 2023, CC0）提供 26 段真实良性录制 + 帧级标注的
message-modification（= masquerade）攻击，dt 分布已实证物理合理
（中位 241-599µs，<135µs 占比 0.0000-0.0004）。

方法：与 Phase 3 / Phase 5 完全同构的 per-ID rate 判据
  nominal = train 良性 dt_id 中位（逐 ID）→ dev = dt_id / nominal
  trivial: flag iff dev < tau, tau = train 良性 dev 的 0.1 分位（零学习）
  oracle : 全阈值精确扫描的可达最大 F1（只在 dev 变化处切）
  degenerate: 2p/(1+p)，"全判攻击"的退化解 —— 判读必须对照它
train = 同一 capture 的 benign 档（S-1-1-malicious-* → S-1-1-benign.log）
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

LOGS = Path.home() / "Datasets/can_ids/CrySyS/logs"
OUT = Path(__file__).resolve().parent.parent / "results" / "crysys_discriminability.csv"
# (t) can0 ID#payload [<mod_flag> <inj_flag>]
# ⚠️ benign 档只有 3 字段（无标注列），恶意档才有 5 字段 → 标注部分必须可选，
#    否则 train 解析为空、全部文件被静默跳过（首次运行 0/624 即此因）。
LINE = re.compile(r"^\((\d+)\.(\d+)\)\s+\S+\s+([0-9A-Fa-f]+)#\S*(?:\s+(\S+)\s+(\S+))?\s*$")


def parse(path: Path):
    ts, aid, y = [], [], []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            m = LINE.match(line)
            if not m:
                continue
            ts.append(int(m.group(1)) * 1_000_000 + int((m.group(2) + "000000")[:6]))
            aid.append(int(m.group(3), 16))
            f4, f5 = m.group(4), m.group(5)
            y.append(0 if (f4 is None or (f4 == "False" and f5 == "False")) else 1)
    return (np.asarray(ts, np.int64) / 1e6, np.asarray(aid, np.int64), np.asarray(y, np.int8))


def dt_id_of(ts, aid):
    order = np.lexsort((ts, aid))
    ts_s, aid_s = ts[order], aid[order]
    d = np.r_[0.0, np.diff(ts_s)]
    d[np.r_[True, aid_s[1:] != aid_s[:-1]]] = 0.0
    np.maximum(d, 0.0, out=d)
    out = np.empty(len(ts))
    out[order] = d
    return out


def true_oracle(dev, y):
    if y.sum() == 0:
        return 0.0
    o = np.argsort(dev, kind="mergesort")
    ys = y[o].astype(np.int64)
    tp = np.cumsum(ys)
    k = np.arange(1, len(ys) + 1)
    fn = int(ys.sum()) - tp
    den = 2 * tp + (k - tp) + fn
    f1 = np.where(den > 0, 2 * tp / np.maximum(den, 1), 0.0)
    ds = dev[o]
    if len(ds) > 1:
        f1 = np.where(np.r_[ds[:-1] != ds[1:], True], f1, -1.0)
    return float(f1.max())


def evaluate(train_p: Path, test_p: Path) -> dict | None:
    ts_tr, aid_tr, y_tr = parse(train_p)
    ts_te, aid_te, y_te = parse(test_p)
    if len(ts_tr) < 1000 or len(ts_te) < 1000 or y_te.sum() == 0:
        return None
    dt_tr, dt_te = dt_id_of(ts_tr, aid_tr), dt_id_of(ts_te, aid_te)
    ben = (y_tr == 0) & (dt_tr > 0)
    nominal = pd.Series(dt_tr[ben]).groupby(aid_tr[ben]).median()
    gm = max(float(np.median(dt_tr[ben])), 1e-9)
    keys, vals = nominal.index.to_numpy(), nominal.to_numpy()
    vals = np.where(vals <= 0, gm, vals)

    def dev_of(dt, a):
        pos = np.clip(np.searchsorted(keys, a), 0, len(keys) - 1)
        return dt / np.where(keys[pos] == a, vals[pos], gm)

    tau = float(np.quantile(dev_of(dt_tr, aid_tr)[y_tr == 0], 0.001))
    dev_te = dev_of(dt_te, aid_te)
    yhat = (dev_te < tau).astype(int)
    tp = int(((yhat == 1) & (y_te == 1)).sum())
    fp = int(((yhat == 1) & (y_te == 0)).sum())
    fn = int(((yhat == 0) & (y_te == 1)).sum())
    p = float(y_te.mean())
    return {
        "test": test_p.name, "train": train_p.name,
        "n_frames": len(ts_te), "n_attack": int(y_te.sum()), "atk_frac": round(p, 6),
        "trivial_f1": round(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0, 4),
        "trivial_recall": round(tp / max(tp + fn, 1), 4),
        "oracle_f1": round(true_oracle(dev_te, y_te), 4),
        "degenerate_f1": round(2 * p / (1 + p), 4),
        "tau": round(tau, 4),
    }


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else "msg-mod"
    files = sorted(p for p in LOGS.glob(f"*malicious*{kind}*.log")
                   if "inj-messages" not in p.name)
    rows, skipped = [], 0
    for i, p in enumerate(files, 1):
        cap = p.name.split("-malicious-")[0]
        tr = LOGS / f"{cap}-benign.log"
        if not tr.exists():
            skipped += 1
            continue
        r = evaluate(tr, p)
        if r:
            r["capture"] = cap
            r["attack_kind"] = kind
            rows.append(r)
        if i % 50 == 0:
            print(f"  {i}/{len(files)}", file=sys.stderr)
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    hdr = not OUT.exists() or kind == "msg-mod"
    df.to_csv(OUT, index=False, mode="w" if hdr else "a", header=hdr)
    print(f"\n{kind}: {len(df)} 个文件 (跳过 {skipped}) -> {OUT}")
    if len(df):
        print(f"  trivial F1  : 中位 {df.trivial_f1.median():.4f}  范围 [{df.trivial_f1.min():.4f}, {df.trivial_f1.max():.4f}]")
        print(f"  oracle  F1  : 中位 {df.oracle_f1.median():.4f}  范围 [{df.oracle_f1.min():.4f}, {df.oracle_f1.max():.4f}]")
        print(f"  退化解 F1   : 中位 {df.degenerate_f1.median():.4f}")
        above = (df.oracle_f1 > df.degenerate_f1 + 0.02).sum()
        print(f"  oracle 显著高于退化解的文件: {above}/{len(df)}")


if __name__ == "__main__":
    main()
