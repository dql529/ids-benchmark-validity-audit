#!/usr/bin/env python3
"""F 审计 Phase 3: 可判别性地图 —— 纯时序能否检出 masquerade。

复用 DT-FL kill-test per-ID rate 方法学 (dt_id_dev < tau 零学习阈值 + oracle,
trivial_perid.py 同构), 泛化到三个基准的帧级标注:

  CTAT  : timestamp/attack 列, 4 train 攻击 + 4 未知攻击类型 (48 含攻击文件)
  ROAD  : signal_extractions CSV (Label,Time,ID,...), ambient 学 nominal → attacks 判别
  SynCAN: (Label,Time,ID,...), Time 单位毫秒, train_1-4 → test_* 判别

每基准额外做「合成时钟退化归因」: 给正常帧时间戳叠加该 ID nominal 周期的
±10% 高斯抖动 (模拟真实采集抖动), 重测判别 F1 → 量化判别在多大程度上依赖
合成时钟的"干净" (合成伪影) vs 攻击注入的"真实节奏" (真信号)。

用法: /opt/anaconda3/bin/python3 audit_phase3.py
输出: phase3/audit_phase3.json + 控制台摘要
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score, precision_score

HERE = Path(__file__).resolve().parent
# Resolve the shared input contract also when this file is run directly.
sys.path.insert(0, str(HERE.parent))
from phase5.run_contract import syncan_has_header

CTAT_DIR = Path(os.path.expanduser("~/Datasets/can_ids/can-train-and-test/set_01"))
ROAD_SIG = Path(os.path.expanduser("~/Datasets/can_ids/ROAD/road/signal_extractions"))
SYNCAN_DIR = Path(os.path.expanduser("~/Datasets/can_ids/SynCAN"))
JITTER = 0.10  # 退化实验: 正常帧 dt 加 ±10% 高斯抖动 (相对该 ID nominal period)
SEED = 0


def add_jitter(df, nominal, global_med, rng):
    """把正常帧的 dt_id 重写为 nominal*(1+N(0,0.10)) 模拟真实采集抖动; 攻击帧不动。

    合成时钟下正常帧 dt_id 极干净 (≡nominal), 抖动后 dt_id_dev 分布变宽,
    阈值 tau 必然更松 → 判别 F1 变化量化"依赖合成时钟干净性"的程度。
    """
    base = df["arbitration_id"].map(nominal).fillna(global_med).values
    base = np.where(base <= 0, global_med, base)
    is_norm = (df["attack"].values == 0)
    df = df.copy()
    # 重写正常帧时间戳: 使 dt_id = nominal * jit (累加恢复单调序列;
    # 攻击帧时间戳不动, 允许轻微逆序, dt 负值在 compute_dt_id 中 clamp 0)
    ts = df["timestamp"].values.copy()
    new_ts = ts.copy()
    for aid, idx in df.groupby("arbitration_id").indices.items():
        idx = np.asarray(idx)
        sel = idx[is_norm[idx]]
        if len(sel) < 2:
            continue
        t0 = ts[sel[0]]
        steps = base[sel[1:]] * np.abs(rng.normal(1.0, JITTER, len(sel) - 1))
        new_ts[sel[1:]] = t0 + np.cumsum(steps)
        new_ts[sel[0]] = t0
    df["timestamp"] = new_ts
    return df


def jitter_eval(tr, df, nominal, gm):
    """退化实验: train/test 正常帧都加 ±10% 抖动, 重测判别 (量化合成时钟依赖)。"""
    rng = np.random.default_rng(SEED)
    tr_j = add_jitter(tr, nominal, gm, rng)
    tr_j = compute_dt_id(tr_j)
    df_j = add_jitter(df, nominal, gm, rng)
    df_j = compute_dt_id(df_j)
    trivial_j, oracle_j, _ = per_id_rate_discriminate(tr_j, df_j, verbose=False)
    return trivial_j, oracle_j


def per_id_rate_discriminate(train_df, test_df, verbose=True):
    """per-ID rate 判别: nominal period 从 train 正常帧学, test 帧级判别。

    返回 (trivial 指标 dict, oracle 指标 dict, nominal 分布摘要)。
    """
    tr = train_df
    te = test_df
    # nominal per-ID period: train 正常帧的 dt_id 中位 (同 kill_test)
    ben = tr[(tr.attack == 0) & (tr.dt_id > 0)]
    nominal = ben.groupby("arbitration_id")["dt_id"].median().to_dict()
    global_med = max(float(ben["dt_id"].median()), 1e-9) if len(ben) else 1e-3

    def dev_of(df_):
        base = df_["arbitration_id"].map(nominal).fillna(global_med).values
        base = np.where(base <= 0, global_med, base)
        return df_["dt_id"].values / base

    dev_te = dev_of(te)
    y = te["attack"].values
    # honest tau: train 正常帧 dt_id_dev 0.1th 分位
    dev_ben = dev_of(tr)
    tau = float(np.quantile(dev_ben[tr.attack.values == 0], 0.001))
    yhat = (dev_te < tau).astype(int)
    m = lambda y_, yh: {
        "f1": round(f1_score(y_, yh, pos_label=1, zero_division=0), 4),
        "recall": round(recall_score(y_, yh, pos_label=1, zero_division=0), 4),
        "precision": round(precision_score(y_, yh, pos_label=1, zero_division=0), 4),
        "fpr": round(float((yh[y_ == 0] == 1).mean()) if (y_ == 0).any() else 0.0, 4),
    }
    trivial = m(y, yhat)
    # oracle: 全阈值精确扫描 (2026-08-11 修正)
    # 原版候选阈值只取 dev_te 的 0.01%~5% 分位; 最优阈值落在该区间外时返回值不是上界
    # —— 症状: SynCAN flooding 曾出现 oracle 0.2836 < trivial 0.7497 (上界低于具体阈值, 逻辑矛盾)。
    # 现改为按 dev 升序遍历所有可实现断点, cumsum 向量化求全局最大 F1。
    order = np.argsort(dev_te, kind="mergesort")
    ys = y[order].astype(np.int64)
    tp = np.cumsum(ys)
    k = np.arange(1, len(ys) + 1)
    fn = int(ys.sum()) - tp
    denom = 2 * tp + (k - tp) + fn
    f1s = np.where(denom > 0, 2 * tp / np.maximum(denom, 1), 0.0)
    if len(ys) > 1:
        dev_sorted = dev_te[order]
        # 只在 dev 值变化处切, 保证该切点确实对应某个 "dev < t" 阈值 (并列组内部不可切)
        f1s = np.where(np.r_[dev_sorted[:-1] != dev_sorted[1:], True], f1s, -1.0)
    i = int(np.argmax(f1s))
    yhat_o = np.zeros(len(y), dtype=int)
    yhat_o[order[:i + 1]] = 1
    best_m = m(y, yhat_o)
    return trivial, best_m, {"tau": round(tau, 4), "n_nominal_ids": len(nominal),
                             "n_attack_test": int(y.sum()), "atk_frac": round(float(y.mean()), 4)}


def compute_dt_id(df):
    """给 df (已含 timestamp/attack/arbitration_id) 加 dt_id 列。"""
    df = df.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    dt_id = np.zeros(len(df))
    ts = df["timestamp"].values
    for aid, idx in df.groupby("arbitration_id").indices.items():
        idx = np.asarray(idx)
        tg = ts[idx]
        d = np.empty(len(tg)); d[0] = 0.0
        if len(tg) > 1:
            d[1:] = np.diff(tg)
        d[d < 0] = 0.0
        dt_id[idx] = d
    df["dt_id"] = dt_id
    return df


# ---------------- CTAT ----------------
def scan_ctat():
    out = {"per_file": []}
    csvs = sorted(CTAT_DIR.glob("**/*.csv"))
    for p in csvs:
        df = pd.read_csv(p, dtype={"arbitration_id": str, "timestamp": np.float64})
        df["attack"] = df["attack"].astype(int)
        # train 文件 = 自身正常段学 nominal (DT-FL 同构: train_01 学习, test 判别)
        if "train_" in str(p):
            continue
        df = compute_dt_id(df)
        # train: 同攻击名的 train_01 文件 (攻击类型一致时 ID 空间一致)
        name = p.stem
        atk_type = name.rsplit("-", 1)[0]
        train_files = list(CTAT_DIR.glob(f"train_01/{atk_type}-*.csv"))
        if not train_files:
            train_files = list(CTAT_DIR.glob("train_01/*.csv"))  # 未知类型兜底: 全部 train
        tr = pd.concat([compute_dt_id(pd.read_csv(f, dtype={"arbitration_id": str, "timestamp": np.float64})) for f in train_files], ignore_index=True)
        tr["attack"] = tr["attack"].astype(int)
        trivial, oracle, meta = per_id_rate_discriminate(tr, df)
        # 退化实验: train/test 正常帧加抖动
        ben_tr = tr[tr.attack == 0]
        nominal = ben_tr.groupby("arbitration_id")["dt_id"].median().to_dict()
        gm = max(float(ben_tr["dt_id"].median()), 1e-9)
        trivial_j, oracle_j = jitter_eval(tr, df, nominal, gm)
        out["per_file"].append({
            "benchmark": "CTAT", "file": str(p.relative_to(CTAT_DIR)),
            "attack_type": atk_type, "trivial": trivial, "oracle": oracle,
            "jittered_trivial": trivial_j, "jittered_oracle": oracle_j,
            "meta": meta,
        })
    return out


# ---------------- ROAD signal_extractions ----------------
def load_road_sig(path):
    df = pd.read_csv(path, usecols=["Label", "Time", "ID"], dtype={"Label": "Int64"})
    df = df.rename(columns={"Label": "attack", "Time": "timestamp", "ID": "arbitration_id"})
    df["attack"] = df["attack"].fillna(0).astype(int)
    df["arbitration_id"] = df["arbitration_id"].astype(int)
    return compute_dt_id(df)


def scan_road():
    out = {"per_file": []}
    ambient = pd.concat([load_road_sig(p) for p in sorted((ROAD_SIG / "ambient").glob("*.csv"))],
                        ignore_index=True)
    ambient["attack"] = ambient["attack"].astype(int)
    ben_a = ambient[ambient.attack == 0]
    nominal = ben_a.groupby("arbitration_id")["dt_id"].median().to_dict()
    gm = max(float(ben_a["dt_id"].median()), 1e-9)
    for p in sorted((ROAD_SIG / "attacks").glob("*.csv")):
        df = load_road_sig(p)
        trivial, oracle, meta = per_id_rate_discriminate(ambient, df)
        if (df["attack"] == 1).any():
            trivial_j, oracle_j = jitter_eval(ambient, df, nominal, gm)
        else:
            trivial_j = oracle_j = None
        out["per_file"].append({
            "benchmark": "ROAD", "file": p.name,
            "is_masquerade": "masquerade" in p.name,
            "trivial": trivial, "oracle": oracle, "meta": meta,
            "jittered_trivial": trivial_j, "jittered_oracle": oracle_j,
        })
    return out


# ---------------- SynCAN ----------------
def load_syncan(path):
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        first_row = next(csv.reader(stream), [])
    header = 0 if syncan_has_header(first_row) else None
    df = pd.read_csv(path, usecols=[0, 1, 2], names=["attack", "timestamp", "arbitration_id"],
                     header=header, dtype={"timestamp": np.float64, "arbitration_id": str})
    df["attack"] = df["attack"].astype(int)
    df["arbitration_id"] = df["arbitration_id"].str.strip()
    return compute_dt_id(df)


def scan_syncan():
    out = {"per_file": []}
    train = pd.concat([load_syncan(p) for p in sorted(SYNCAN_DIR.glob("train_*/train_*.csv"))],
                      ignore_index=True)
    ben_tr = train[train.attack == 0]
    nominal = ben_tr.groupby("arbitration_id")["dt_id"].median().to_dict()
    gm = max(float(ben_tr["dt_id"].median()), 1e-9)
    for p in sorted(SYNCAN_DIR.glob("test_*/test_*.csv")):
        df = load_syncan(p)
        trivial, oracle, meta = per_id_rate_discriminate(train, df)
        if (df["attack"] == 1).any():
            trivial_j, oracle_j = jitter_eval(train, df, nominal, gm)
        else:
            trivial_j = oracle_j = None
        out["per_file"].append({
            "benchmark": "SynCAN", "file": str(p.relative_to(SYNCAN_DIR)),
            "trivial": trivial, "oracle": oracle, "meta": meta,
            "jittered_trivial": trivial_j, "jittered_oracle": oracle_j,
        })
    return out


def main():
    scope = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = {}
    if scope in ("all", "ctat"):
        print("[1/3] CTAT ...", file=sys.stderr)
        results["ctat"] = scan_ctat()
    if scope in ("all", "road"):
        print("[2/3] ROAD signal_extractions ...", file=sys.stderr)
        results["road"] = scan_road()
    if scope in ("all", "syncan"):
        print("[3/3] SynCAN ...", file=sys.stderr)
        results["syncan"] = scan_syncan()

    out_path = HERE / "audit_phase3.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    def row(r, name):
        t, o = r["trivial"], r["oracle"]
        jt = r.get("jittered_trivial")
        jt_s = f" | 抖动后 {jt['f1']}" if jt else ""
        return (f"| {name[:10]} | {r['file'][:44]:46s} | {t['f1']:.3f} | {t['recall']:.3f} | "
                f"{o['f1']:.3f} | {r['meta']['atk_frac']:.4f}{jt_s} |")

    print("\n## Phase 3 可判别性地图 (per-ID rate trivial F1)")
    print("| 基准 | 文件 | trivialF1 | recall | oracleF1 | 攻击帧占比 |")
    print("|---|---|---|---|---|---|")
    for key in ("ctat", "road", "syncan"):
        if key in results:
            for r in results[key]["per_file"]:
                print(row(r, r["benchmark"]))
    print(f"\n完整 JSON: {out_path}")


if __name__ == "__main__":
    main()
