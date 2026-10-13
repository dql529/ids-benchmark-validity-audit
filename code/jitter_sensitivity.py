#!/usr/bin/env python3
"""Phase 5: 时钟扰动敏感性实验 —— 重做 Phase 3 的"抖动退化归因"。

⛔ 为什么重做（REVIEW_2026-08-11 P2）:
  旧 `audit_phase3.add_jitter()` 把良性帧时间轴**整个换掉**:
  `t' = t0 + cumsum(nominal_median * |N(1,0.1)|)`。
  nominal 是该 ID 的 dt 中位，于是重建后的良性序列总跨度 = n*中位，
  在 dt 重尾下与真实跨度差出量级（ROAD 全局 dt 中位 1µs vs 均值 497µs）。
  那不是"给真实数据加抖动"，是"用另一个合成钟替换这个合成钟"——
  得到的退化曲线无法支撑任何关于"真实时钟下会怎样"的结论。

当前设计：三条扰动臂；以下早期两臂说明保留为设计背景，实际定义以实现为准。

  Arm A — 硬件时间戳误差（对全部帧）:  t' = t + N(0, s)
     s ∈ {1, 10, 100, 1000} µs。**s=100µs 有一手依据**: ROAD 官方自述
     "timestamps are reported with a precision of 1 μs, but the Kvaser hardware
     only guarantees an accuracy of 100 μs"（Zenodo 10462796 / arXiv 2012.14600 §4.3）。
     问的是: 该基准提供的时序判别性，能不能扛住它自己宣称的采集硬件精度。

  Arm B — gap乘单位均值lognormal因子，再cumsum重建，包含累积漂移。
     σ ∈ {0.05, 0.1, 0.2, 0.5, 1.0}。仅CTAT攻击帧保持原样；ROAD/SynCAN全部帧同钟扰动。
     跨度仅在期望上保留，不能称分布形状不变或单独识别jitter效应。
  Arm C — t'=t+ε·gap，ε~N(0,σ)，不累积位置误差；与B的分布及相关结构不同，不能隔离漂移。

⚠️ 结论边界（论文必须照写）: 两条臂都是**敏感性分析**，底层 gap 仍是合成的。
   它们能回答"判别性对时钟噪声有多脆"，**不能**回答"真实采集下会怎样"——
   后者需要真实时序档（CrySyS），是独立待办。

用法:
  python3 jitter_sensitivity.py --stage cache --run-dir RUN_DIR
  python3 jitter_sensitivity.py --stage sweep --pilot --run-dir RUN_DIR
  python3 jitter_sensitivity.py --stage sweep --workers 14 --run-dir RUN_DIR
输出: RUN_DIR/results/jitter_sensitivity.csv（旧结果保留）
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from . import run_contract
else:
    import run_contract

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
CTAT_DIR = Path(os.path.expanduser("~/Datasets/can_ids/can-train-and-test/set_01"))
ROAD_SIG = Path(os.path.expanduser("~/Datasets/can_ids/ROAD/road/signal_extractions"))
SYNCAN_DIR = Path(os.path.expanduser("~/Datasets/can_ids/SynCAN"))

# SynCAN Time 列单位是毫秒（官方 README），换算成秒后与其余基准同量纲
SYNCAN_TIME_SCALE = 1e-3

ARM_A_LEVELS_US = [1.0, 10.0, 100.0, 1000.0]      # 硬件时间戳误差 (µs)
ARM_B_SIGMAS = [0.05, 0.10, 0.20, 0.50, 1.00]      # 良性 gap 相对抖动(含累积漂移)
ARM_C_SIGMAS = [0.05, 0.10, 0.20, 0.50, 1.00]      # 同幅度, 但有界不漂移(去混淆对照臂)
N_SEEDS = 10

# Arm B 只对"良性钟"上的帧加抖动。攻击帧是否在**独立**时间轴上, 逐基准不同:
#   CTAT   — 攻击帧 ~3ms 注入节奏, 与良性合成钟不同源 (Phase 2 任务③) → 不动攻击帧
#   ROAD   — 攻击帧与良性帧同为 1-2µs 合成钟 (Phase 2 任务②同质) → 一起抖
#   SynCAN — "攻击"标注的是被篡改载荷的普通帧, 时序与良性同源 → 一起抖
# ⛔ pilot 抓到: 若对 SynCAN 只抖良性帧, test_continuous 的 trivial 从 0.0000 跳到 0.3392
#    —— 那是"给两类帧装了不同的钟"制造出来的判别性, 纯伪影。
ARM_B_ATTACK_INDEPENDENT = {"ctat"}


# ---------------------------------------------------------------- 解析与缓存

def _save(name: str, ts: np.ndarray, aid: np.ndarray, y: np.ndarray,
          seg: np.ndarray | None = None) -> None:
    """seg = 捕获段编号。同一 ID 跨段**不构成前后帧**（每段是独立采集会话）。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    if seg is None:
        seg = np.zeros(len(ts), dtype=np.int32)
    np.savez_compressed(CACHE / f"{name}.npz", ts=ts.astype(np.float64),
                        aid=aid.astype(np.int64), y=y.astype(np.int8),
                        seg=seg.astype(np.int32))


def _load(name: str, cache_dir: Path | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    d = np.load((cache_dir or CACHE) / f"{name}.npz")
    return d["ts"], d["aid"], d["y"], d["seg"]


def _aid_codes(values: pd.Series, kind: str) -> np.ndarray:
    """把 arbitration id 映射成**跨文件稳定**的整数。

    ⛔ 自审修复 (致命)：初版用 `astype('category').cat.codes` 逐文件编码 ——
    同一个整数在 train 与 test 里代表**不同的 CAN ID**，nominal 会张冠李戴。
    改为直接用 ID 本身的数值语义，无需词表即全局一致。
    """
    s = values.astype(str).str.strip()
    if kind == "hex":            # CTAT: '0F9' 等十六进制
        return s.apply(lambda x: int(x, 16)).to_numpy(dtype=np.int64)
    if kind == "int":            # ROAD signal_extractions: 已是十进制整数
        return s.astype(np.int64).to_numpy()
    if kind == "syncan":         # SynCAN: 'id1'..'id10'
        return s.str.removeprefix("id").astype(np.int64).to_numpy()
    raise ValueError(kind)


def _concat_sequential(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """拼接多个捕获文件, 并把每段平移到前一段之后。

    ⛔ 自审修复 (致命)：CTAT 的 train 文件**全部起始于 1672531200.0**，
    直接 concat 会让跨文件时间戳重叠 → dt_id 退化成噪声 → tau 从 0.7384 掉到 0.0025，
    trivial F1 变 0（level=0 自检就是这么抓出来的）。
    Phase 3 是逐文件算完 dt_id 再拼；此处等价做法 = 拼前按段平移，段内 gap 完全不变。
    """
    out, offset = [], 0.0
    for i, df in enumerate(parts):
        d = df.copy()
        t = d["timestamp"].to_numpy()
        d["timestamp"] = t - t.min() + offset
        d["seg"] = i                                    # 段号: dt_id 分组键的一部分
        offset = float(d["timestamp"].max()) + 1.0      # 段间留 1s，保证严格不重叠
        out.append(d)
    return pd.concat(out, ignore_index=True)


def cache_ctat() -> list[str]:
    """按攻击类型分别缓存 train 集（与 Phase 3 的 train 选择规则一致，保可比性）。"""
    names = []
    train_files = sorted(CTAT_DIR.glob("train_01/*.csv"))

    def read(p: Path) -> pd.DataFrame:
        return pd.read_csv(p, usecols=["timestamp", "arbitration_id", "attack"],
                           dtype={"timestamp": np.float64, "arbitration_id": str})

    groups: dict[str, list[Path]] = {"ALL": train_files}
    for p in train_files:
        groups.setdefault(p.stem.rsplit("-", 1)[0], []).append(p)
    for gname, paths in groups.items():
        tr = _concat_sequential([read(p) for p in paths])
        key = f"ctat__TRAINSET|{gname}"
        _save(key, tr["timestamp"].to_numpy(), _aid_codes(tr["arbitration_id"], "hex"),
              tr["attack"].astype(int).to_numpy(), tr["seg"].to_numpy())
        names.append(key)

    for p in sorted(CTAT_DIR.glob("test_*/*.csv")):
        df = pd.read_csv(p, usecols=["timestamp", "arbitration_id", "attack"],
                         dtype={"timestamp": np.float64, "arbitration_id": str})
        key = "ctat__" + str(p.relative_to(CTAT_DIR)).replace("/", "|")
        _save(key, df["timestamp"].to_numpy(), _aid_codes(df["arbitration_id"], "hex"),
              df["attack"].astype(int).to_numpy())
        names.append(key)
    return names


def _road_one(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, usecols=["Label", "Time", "ID"], dtype={"Label": "Int64"})
    df = df.rename(columns={"Label": "attack", "Time": "timestamp", "ID": "arbitration_id"})
    df["attack"] = df["attack"].fillna(0).astype(int)
    return df


def cache_road() -> list[str]:
    names = []
    amb = _concat_sequential([_road_one(p) for p in sorted((ROAD_SIG / "ambient").glob("*.csv"))])
    _save("road__TRAINSET|ALL", amb["timestamp"].to_numpy(),
          _aid_codes(amb["arbitration_id"], "int"), amb["attack"].to_numpy(),
          amb["seg"].to_numpy())
    names.append("road__TRAINSET|ALL")
    for p in sorted((ROAD_SIG / "attacks").glob("*.csv")):
        df = _road_one(p)
        if int(df["attack"].sum()) == 0:      # accelerator 系列无正例, 跳过
            continue
        key = "road__" + p.name
        _save(key, df["timestamp"].to_numpy(), _aid_codes(df["arbitration_id"], "int"),
              df["attack"].to_numpy())
        names.append(key)
    return names


def _syncan_one(p: Path) -> pd.DataFrame:
    with p.open(newline="", encoding="utf-8-sig") as stream:
        first_row = next(csv.reader(stream), [])
    has_header = run_contract.syncan_has_header(first_row)
    df = pd.read_csv(p, usecols=[0, 1, 2], names=["attack", "timestamp", "arbitration_id"],
                     header=0 if has_header else None,
                     dtype={"timestamp": np.float64, "arbitration_id": str})
    df["attack"] = df["attack"].astype(int)
    df["timestamp"] = df["timestamp"] * SYNCAN_TIME_SCALE      # ms -> s
    return df


def cache_syncan() -> list[str]:
    names = []
    tr = _concat_sequential([_syncan_one(p) for p in sorted(SYNCAN_DIR.glob("train_*/train_*.csv"))])
    _save("syncan__TRAINSET|ALL", tr["timestamp"].to_numpy(),
          _aid_codes(tr["arbitration_id"], "syncan"), tr["attack"].to_numpy(),
          tr["seg"].to_numpy())
    names.append("syncan__TRAINSET|ALL")
    for p in sorted(SYNCAN_DIR.glob("test_*/test_*.csv")):
        df = _syncan_one(p)
        if int(df["attack"].sum()) == 0:
            continue
        key = "syncan__" + p.parent.name
        _save(key, df["timestamp"].to_numpy(), _aid_codes(df["arbitration_id"], "syncan"),
              df["attack"].to_numpy())
        names.append(key)
    return names


# ---------------------------------------------------------------- 扰动

def perturb(ts: np.ndarray, aid: np.ndarray, y: np.ndarray, seg: np.ndarray,
            arm: str, level: float, seed: int, bench: str = "") -> np.ndarray:
    """返回扰动后的时间戳（不改变 aid/y 的对应关系, 调用方负责重排序）。"""
    if arm == "none" or level == 0:
        return ts
    rng = np.random.default_rng(seed)
    if arm == "A":                              # 硬件时间戳误差, 全部帧
        return ts + rng.normal(0.0, level * 1e-6, size=len(ts))
    if arm == "B":                              # 良性 gap 相对抖动, 仅良性帧
        # 全向量化: lexsort 把良性帧按 (aid, ts) 排成连续组, 组内 diff/cumsum 一次算完。
        # (初版按 ID 循环, 每轮对全数组做两次布尔运算 —— ROAD 24.8M 行 ×105 ID
        #  单次 perturb 就要 ~40s, 全量 sweep 会到小时级)
        out = ts.copy()
        # 攻击帧独立成轴的基准只抖良性帧; 否则全部帧一起抖 (见 ARM_B_ATTACK_INDEPENDENT)
        idx = (np.flatnonzero(y == 0) if bench in ARM_B_ATTACK_INDEPENDENT
               else np.arange(len(ts)))
        if len(idx) < 3:
            return out
        order = idx[np.lexsort((ts[idx], aid[idx], seg[idx]))]
        ts_s, key_s = ts[order], np.c_[seg[order], aid[order]]
        # lognormal 乘子: 恒 >0 且 E[mult]=1 —— 保 gap 均值与总跨度。
        # (初版用 1+N(0,σ) 再 clip 到 0, σ≥0.5 时约 16% 的 gap 被压成 0,
        #  dev=0 直接触发阈值 → 制造假阳性, 退化曲线会是伪影)
        gaps = np.diff(ts_s) * rng.lognormal(-0.5 * level ** 2, level, size=len(ts_s) - 1)
        gstart = np.r_[True, (key_s[1:] != key_s[:-1]).any(axis=1)]   # 每个 (段, ID) 组的首帧
        step = np.r_[0.0, gaps]
        step[gstart] = 0.0                                  # 组边界不跨组累加
        cum = np.cumsum(step)
        anchor = np.maximum.accumulate(np.where(gstart, np.arange(len(gstart)), 0))
        out[order] = ts_s[anchor] + (cum - cum[anchor])
        return out
    if arm == "C":
        # ⛔ 2026-08-11 去混淆新增。Arm B 的 cumsum 重建带来**无界累积漂移**
        # (实测 σ=0.05 时良性帧位移中位 45ms / max 2.0s, 而良性 gap 中位仅 10µs),
        # 于是 A(加性/有界) 与 B(乘性/无界) 同时差两个变量, 归因不成立。
        # Arm C = 有界的 gap 比例抖动: t'_i = t_i + ε_i·g_i, ε~N(0,σ) i.i.d.
        # 位置不累积 → Arm B 是 "jitter + cumulative drift"; C 消除了累积成分,
        # 但 B/C 的位移分布与相关结构不同, C vs B 并不隔离"漂移"这单一变量
        # (与论文 method/results 章口径一致: "does not isolate drift")。
        out = ts.copy()
        idx = (np.flatnonzero(y == 0) if bench in ARM_B_ATTACK_INDEPENDENT
               else np.arange(len(ts)))
        if len(idx) < 3:
            return out
        order = idx[np.lexsort((ts[idx], aid[idx], seg[idx]))]
        ts_s, key_s = ts[order], np.c_[seg[order], aid[order]]
        gaps = np.r_[0.0, np.diff(ts_s)]
        gstart = np.r_[True, (key_s[1:] != key_s[:-1]).any(axis=1)]
        gaps[gstart] = 0.0                      # 组首无前驱 gap
        out[order] = ts_s + rng.normal(0.0, level, size=len(ts_s)) * gaps
        return out
    raise ValueError(f"unknown arm: {arm}")


def dt_id_of(ts: np.ndarray, aid: np.ndarray, seg: np.ndarray) -> np.ndarray:
    """每帧与**同段同 ID 前一帧**的间隔（组首记 0）。返回值按原始行序对齐。

    ⛔ 自审修复：只按 aid 分组会把拼接处的段边界当成一次真实间隔，
    ROAD 上把 trivial F1 从 0.0279 抬到 0.0683（与 Phase 3 已发表数字打架）。
    """
    order = np.lexsort((ts, aid, seg))                      # 按 (seg, aid, ts) 分组并排序
    ts_s, key_s = ts[order], np.c_[seg[order], aid[order]]
    d = np.r_[0.0, np.diff(ts_s)]
    d[np.r_[True, (key_s[1:] != key_s[:-1]).any(axis=1)]] = 0.0    # 组首无前驱
    np.maximum(d, 0.0, out=d)
    dt = np.empty(len(ts))
    dt[order] = d
    return dt


def true_oracle(dev: np.ndarray, y: np.ndarray) -> float:
    """全阈值精确扫描的可达最大 F1（预测 = dev < t）。"""
    if len(y) == 0 or y.sum() == 0:
        return 0.0
    order = np.argsort(dev, kind="mergesort")
    ys = y[order].astype(np.int64)
    tp = np.cumsum(ys)
    k = np.arange(1, len(ys) + 1)
    fn = int(ys.sum()) - tp
    denom = 2 * tp + (k - tp) + fn
    f1 = np.where(denom > 0, 2 * tp / np.maximum(denom, 1), 0.0)
    dev_s = dev[order]
    f1 = np.where(np.r_[dev_s[:-1] != dev_s[1:], True], f1, -1.0)   # 只在可实现断点切
    return float(f1.max())


def evaluate(train: tuple, test: tuple, arm: str, level: float, seed: int,
             bench: str = "") -> dict:
    """train/test 各自独立取噪, 同一 (arm, level, seed) 配置。"""
    ts_tr, aid_tr, y_tr, seg_tr = train
    ts_te, aid_te, y_te, seg_te = test
    ts_tr = perturb(ts_tr, aid_tr, y_tr, seg_tr, arm, level, seed, bench)
    ts_te = perturb(ts_te, aid_te, y_te, seg_te, arm, level, seed + 10_000, bench)

    # dt_id_of 返回按原始行序对齐的 dt_id, 因此 aid/y 直接用原数组即可（无需重排）
    dt_tr, dt_te = dt_id_of(ts_tr, aid_tr, seg_tr), dt_id_of(ts_te, aid_te, seg_te)
    aid_tr_o, y_tr_o = aid_tr, y_tr
    aid_te_o, y_te_o = aid_te, y_te

    ben = (y_tr_o == 0) & (dt_tr > 0)
    if not ben.any():
        return {}
    nominal = pd.Series(dt_tr[ben]).groupby(aid_tr_o[ben]).median()
    gm = max(float(np.median(dt_tr[ben])), 1e-9)
    base_map = nominal.to_dict()

    # 向量化查表: aid 是真实 CAN ID 数值, 用 searchsorted 而非逐元素 dict.get
    # (初版 [base_map.get(a, gm) for a in aid_o] 在 ROAD 3000 万行上是分钟级)
    keys = np.array(sorted(base_map), dtype=np.int64)
    vals = np.array([base_map[k] for k in keys], dtype=np.float64)
    vals = np.where(vals <= 0, gm, vals)

    def dev_of(dt, aid_o):
        pos = np.searchsorted(keys, aid_o)
        pos = np.clip(pos, 0, len(keys) - 1)
        hit = keys[pos] == aid_o
        base = np.where(hit, vals[pos], gm)
        return dt / base

    dev_tr = dev_of(dt_tr, aid_tr_o)
    dev_te = dev_of(dt_te, aid_te_o)
    tau = float(np.quantile(dev_tr[y_tr_o == 0], 0.001))
    yhat = (dev_te < tau).astype(int)

    tp = int(((yhat == 1) & (y_te_o == 1)).sum())
    fp = int(((yhat == 1) & (y_te_o == 0)).sum())
    fn = int(((yhat == 0) & (y_te_o == 1)).sum())
    n_neg = int((y_te_o == 0).sum())
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    p = float(y_te_o.mean())
    return {
        "trivial_f1": round(f1, 4),
        "trivial_recall": round(tp / max(tp + fn, 1), 4),
        "trivial_precision": round(tp / max(tp + fp, 1), 4),
        "fpr": round(fp / max(n_neg, 1), 4),
        "oracle_f1": round(true_oracle(dev_te, y_te_o), 4),
        "degenerate_f1": round(2 * p / (1 + p), 4),   # "全判攻击"基线, 判读必须对照它
        "tau": round(tau, 6),
        "atk_frac": round(p, 6),
    }


# ---------------------------------------------------------------- sweep

def resolve_trainset(bench: str, test_name: str, available: set[str]) -> str:
    """与 Phase 3 同规则: CTAT 优先用同攻击类型的 train, 无同类则回落全量。"""
    if bench == "ctat":
        stem = test_name.split("|")[-1].removesuffix(".csv")
        cand = f"ctat__TRAINSET|{stem.rsplit('-', 1)[0]}"
        if cand in available:
            return cand
    return f"{bench}__TRAINSET|ALL"


def _job(args) -> list[dict]:
    bench, test_names, arm, level, seed, available, cache_dir = args
    cache_tr: dict[str, tuple] = {}
    rows = []
    for name in test_names:
        tkey = resolve_trainset(bench, name, available)
        if tkey not in cache_tr:
            cache_tr[tkey] = _load(tkey, cache_dir)
        train = cache_tr[tkey]
        test = _load(name, cache_dir)
        m = evaluate(train, test, arm, level, seed, bench)
        if not m:
            continue
        rows.append({"benchmark": bench, "file": name.split("__", 1)[1],
                     "trainset": tkey.split("|", 1)[1],
                     "arm": arm, "level": level, "seed": seed, **m})
    return rows


def run_sweep(pilot: bool, workers: int, run_dir: Path) -> Path:
    """Internal worker runner; only CLI main is a verified experiment entry point.

    Calling this function directly bypasses main's input/cache contract checks and
    does not produce its bound result manifest. Such output is not a certified run.
    """
    benches, available = {}, set()
    cache_dir = run_dir / "cache"
    for f in sorted(cache_dir.glob("*.npz")):
        b, rest = f.stem.split("__", 1)
        available.add(f.stem)
        if rest.startswith("TRAINSET|"):
            continue
        benches.setdefault(b, []).append(f.stem)
    if not benches:
        sys.exit("cache 为空，先跑 --stage cache")

    if pilot:
        benches = {b: v[:2] for b, v in benches.items()}
        configs = [("none", 0.0, 0), ("A", 100.0, 0), ("B", 0.10, 0), ("C", 0.10, 0)]
        out = run_dir / "results" / "jitter_sensitivity_pilot.csv"
    else:
        configs = [("none", 0.0, 0)]
        configs += [("A", s, sd) for s, sd in itertools.product(ARM_A_LEVELS_US, range(N_SEEDS))]
        configs += [("B", s, sd) for s, sd in itertools.product(ARM_B_SIGMAS, range(N_SEEDS))]
        configs += [("C", s, sd) for s, sd in itertools.product(ARM_C_SIGMAS, range(N_SEEDS))]
        out = run_dir / "results" / "jitter_sensitivity.csv"
    result_manifest = out.with_name(out.stem + "_manifest.json")
    if out.exists() or result_manifest.exists():
        raise FileExistsError(f"result already exists; choose a new run directory: {out}")

    jobs = [(b, names, arm, lv, sd, available, cache_dir) for b, names in benches.items()
            for arm, lv, sd in configs]
    print(f"[sweep] {len(jobs)} jobs × {sum(len(v) for v in benches.values())} 文件"
          f" | workers={workers} | pilot={pilot}", file=sys.stderr)

    rows, t0, done = [], time.time(), 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_job, j): j for j in jobs}
        for fu in as_completed(futs):
            rows.extend(fu.result())
            done += 1
            if done % max(1, len(jobs) // 20) == 0:
                el = time.time() - t0
                print(f"  {done}/{len(jobs)}  {el:.0f}s  eta {el/done*(len(jobs)-done):.0f}s",
                      file=sys.stderr)

    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).sort_values(["benchmark", "file", "arm", "level", "seed"])
    df.to_csv(out, index=False)
    print(f"\nwrote {out}  ({len(df)} rows)", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["cache", "sweep"], required=True)
    ap.add_argument("--run-dir", type=Path, required=True,
                    help="new run directory; existing Phase 5 cache/results are never overwritten")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 4))
    a = ap.parse_args()

    run_dir = a.run_dir.resolve()
    if a.stage == "cache":
        if run_dir.exists() and any(run_dir.iterdir()):
            ap.error(f"run directory is not empty: {run_dir}")
    elif not (run_dir / "input_contract.json").is_file():
        ap.error(f"missing input contract in {run_dir}; build a new cache run first")
    roots = {"ctat": CTAT_DIR, "road": ROAD_SIG, "syncan": SYNCAN_DIR}
    code = {"jitter_sensitivity.py": run_contract.sha256(Path(__file__)),
            "run_contract.py": run_contract.sha256(Path(run_contract.__file__))}
    parameters = {"syncan_time_scale": SYNCAN_TIME_SCALE,
                  "arm_a_levels_us": ARM_A_LEVELS_US, "arm_b_sigmas": ARM_B_SIGMAS,
                  "arm_c_sigmas": ARM_C_SIGMAS, "n_seeds": N_SEEDS,
                  "arm_b_attack_independent": sorted(ARM_B_ATTACK_INDEPENDENT),
                  "numpy_version": np.__version__, "pandas_version": pd.__version__}
    inputs = run_contract.input_snapshot(roots)

    if a.stage == "cache":
        run_dir.mkdir(parents=True, exist_ok=True)
        global CACHE
        CACHE = run_dir / "cache"
        t0 = time.time()
        names = cache_ctat() + cache_road() + cache_syncan()
        print(f"cached {len(names)} arrays -> {CACHE}  ({time.time()-t0:.0f}s)")
        for n in names:
            ts, aid, y, _ = _load(n)
            print(f"  {n:<52} n={len(ts):>9,}  ids={len(np.unique(aid)):>4}  atk={int(y.sum()):>8,}")
        run_contract.check_snapshot("inputs during cache build", inputs,
                                    run_contract.input_snapshot(roots))
        run_contract.write_manifest(run_dir / "input_contract.json", inputs,
                                    run_contract.cache_snapshot(CACHE), code, parameters)
    else:
        caches = run_contract.cache_snapshot(run_dir / "cache")
        contract_id = run_contract.verify_manifest(
            run_dir / "input_contract.json", inputs, caches, code, parameters)
        print(f"input contract {contract_id} verified before workers", file=sys.stderr)
        out = run_sweep(a.pilot, a.workers, run_dir)
        run_contract.check_snapshot("inputs during sweep", inputs,
                                    run_contract.input_snapshot(roots))
        run_contract.check_snapshot("caches during sweep", caches,
                                    run_contract.cache_snapshot(run_dir / "cache"))
        (run_dir / "results" / (out.stem + "_manifest.json")).write_text(
            json.dumps({"contract_id": contract_id, "csv_sha256": run_contract.sha256(out),
                        "csv": out.name, "pilot": a.pilot, "workers": a.workers},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
