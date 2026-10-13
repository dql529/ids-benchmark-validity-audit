#!/usr/bin/env python3
"""F 审计 Phase 1: CAN masquerade 基准时序完整性统计。

对 ROAD / can-train-and-test / SynCAN 三个在手基准做逐文件:
  1. 到达间隔分布 (dt: mean/median/p1/p99/max)
  2. 时间戳单调性 (重排对数 / 严格升序比例 / 重复戳比例)
  3. 量化检测 (绝对戳落在整毫秒/整秒网格的比例)
     ⛔ 2026-08-11 REVIEW: 该指标已整类弃用, 不再作为后处理/合成证据。三次栽在同一坑:
       (a) abs() 缺失 -> "49% 距整秒<1µs" 伪影 (已撤销)
       (b) SynCAN Time 单位是毫秒却按秒处理 + 基线取错 -> "毫秒网格 3-11%" 伪影 (已撤销)
       (c) dt "整数µs 量化指纹" 是 candump 6 位小数格式的必然, 无鉴别力 (已撤销)
     结论只用: dt 分布反物理 (dt_lt135us) + 起始整数秒 + 官方声明矛盾。详见 audit/REVIEW_2026-08-11.md
  4. masquerade 标记 (ROAD 文件名含 masquerade)

用法: python3 audit_phase1.py [road|can-train-and-test|syncan|all]
输出: audit_phase1.json (机器可读) + 控制台 markdown 摘要
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROAD_DIR = Path(os.path.expanduser("~/Datasets/can_ids/ROAD/road"))
CTAT_DIR = Path(os.path.expanduser("~/Datasets/can_ids/can-train-and-test/set_01"))
SYNCAN_DIR = Path(os.path.expanduser("~/Datasets/can_ids/SynCAN"))
OUT_DIR = Path(__file__).resolve().parent

# ROAD candump 行: (1110000000.000000) can0 0F4#960C010204B10240
# bytes pattern (流式读入的是 bytes); ID 支持 11-bit(3hex)/29-bit(8hex)
ROAD_RE = re.compile(rb"^\((\d+\.\d+)\)\s+can\d\s+[0-9A-Fa-f]{3,8}#")

# 量化容差: epoch ~1e9 时 float64 ULP ≈ 1.19e-7, 1e-9 容差会全漏报
GRID_TOL = 1e-6

# CAN 帧间隔物理下限通用界 (2026-08-12 更正): 最短合法帧 44 bit + 帧间隔 3 bit
# ÷ 最高标准位速率 1 Mbit/s = 47 µs。135µs 是满位填充上界且假设了无文档的
# 波特率, 不得当下限; 三语料均无波特率文档, 审计零输入假设。
# 见 .omc/decisions/2026-08-12_rate-independent-floor.md
ABS_FLOOR_US = 47.0
ABS_FLOOR = ABS_FLOOR_US * 1e-6  # 换算成秒 (本脚本时间戳口径)


def stat_timestamps(ts):
    """核心统计: ts 为 np.float64 数组(已排序输入顺序, 不假设已排序)。"""
    n = len(ts)
    if n == 0:
        return {"n_rows": 0, "t_start": 0.0, "t_end": 0.0, "span_sec": 0.0,
                "t_start_on_sec_grid": False, "dt": None,
                "strict_increasing_frac": 0.0, "reorder_pairs": 0,
                "dup_pairs": 0, "dup_frac": 0.0,
                "on_ms_grid_frac": 0.0, "on_sec_grid_frac": 0.0}
    dt = np.diff(ts)
    # 时间戳单调性
    order_ok = int(np.sum(dt > 0))
    reorder_pairs = int(np.sum(dt < 0))          # 后一排早于前一排 = 重排证据
    dup_pairs = int(np.sum(dt == 0))             # 完全重复戳
    # 量化检测: 绝对时间戳在网格边界上的比例 (容差须 ≥ float64 ULP;
    # 2026-08-11 修正: 原版缺 abs() 把小数部分 ≥0.5s 的帧误判为网格 → 全撤销重算)
    ms_grid = float(np.mean(np.abs(ts - np.round(ts / 0.001) * 0.001) < GRID_TOL))
    s_grid = float(np.mean(np.abs(ts - np.round(ts / 1.0) * 1.0) < GRID_TOL))
    # 到达间隔分布
    dts = dt[dt > 0]
    dt_stats = None
    if len(dts) > 0:
        dt_stats = {
            "mean": round(float(dts.mean()), 9),
            "median": round(float(np.median(dts)), 9),
            "p1": round(float(np.percentile(dts, 1)), 9),
            "p99": round(float(np.percentile(dts, 99)), 9),
            "max": round(float(dts.max()), 9),
        }
    n_pairs = n - 1
    return {
        "n_rows": n,
        "t_start": round(float(ts[0]), 6),
        "t_end": round(float(ts[-1]), 6),
        "span_sec": round(float(ts[-1] - ts[0]), 6),
        "t_start_on_sec_grid": bool(abs(ts[0] - round(ts[0])) < GRID_TOL),
        "dt": dt_stats,
        "strict_increasing_frac": round(order_ok / n_pairs, 6),
        "reorder_pairs": reorder_pairs,
        "dup_pairs": dup_pairs,
        "dup_frac": round(dup_pairs / n_pairs, 6),
        "on_ms_grid_frac": round(ms_grid, 6),
        "on_sec_grid_frac": round(s_grid, 6),
    }


def judge(st):
    """自动判读: CLEAN / UNPHYSICAL / REORDERED。

    ⛔ 2026-08-11 REVIEW 修订两处 (原判读逻辑是 abs bug 时代调的, 修 bug 后已失配):
      1. 原 docstring 写的 "实测 ROAD 距整秒<1µs 占 49% / 随机基线 24 万倍, 后处理铁证"
         是 abs() bug 伪影, 已撤销 —— 修正后实测 sec_grid ≤ 8.1e-5, 网格整类证据弃用。
      2. UNPHYSICAL 阈值原为 10µs, 偏保守, 导致 CTAT 44/52 文件被判 CLEAN 而与
         summary 结论字面冲突。现改为 47µs 通用界口径 (ABS_FLOOR: 44 bit + 3 IFS
         ÷ 1 Mbit/s, 2026-08-12 由 135µs 再更正, 见 .omc/decisions/
         2026-08-12_rate-independent-floor.md)。
    ⛔ 网格判据整类弃用, 不作判决 (2026-08-11 REVIEW: 三次浮点/十进制打印伪影,
      原 POST-PROCESSED 兜底分支已删除; 修正后实测 sec_grid ≤ 8.1e-5 本不可触发)。
    """
    if st is None:
        return "EMPTY"
    if st["dt"] and st["dt"]["median"] < ABS_FLOOR and st["n_rows"] > 10000:
        return "UNPHYSICAL (median inter-arrival < 47us CAN floor)"
    if st["reorder_pairs"] > st["n_rows"] * 0.001:
        return "REORDERED"
    return "CLEAN"


def parse_road_file(path):
    """流式解析 ROAD .log, 只取时间戳列 (内存: ~24B/行)。"""
    ts = []
    with open(path, "rb") as f:
        for line in f:
            m = ROAD_RE.match(line)
            if m:
                ts.append(float(m.group(1)))
    return np.asarray(ts, dtype=np.float64)


def scan_road():
    results = []
    log_files = sorted(ROAD_DIR.glob("attacks/*.log")) + sorted(ROAD_DIR.glob("ambient/*.log"))
    for p in log_files:
        t0 = time.time()
        ts = parse_road_file(p)
        st = stat_timestamps(ts)
        name = str(p.relative_to(ROAD_DIR))
        results.append({
            "benchmark": "ROAD",
            "file": name,
            "is_masquerade": "masquerade" in name,
            "is_attack": "attacks" in name,
            **st,
            "verdict": judge(st),
            "parse_sec": round(time.time() - t0, 1),
        })
    return results


def scan_ctat():
    """can-train-and-test: CSV 含 timestamp 列。"""
    results = []
    for p in sorted(CTAT_DIR.glob("**/*.csv")):
        t0 = time.time()
        try:
            ts = pd.read_csv(p, usecols=["timestamp"], dtype=np.float64,
                             on_bad_lines="skip")["timestamp"].to_numpy()
        except Exception:
            ts = np.array([])
        st = stat_timestamps(ts)
        name = str(p.relative_to(CTAT_DIR))
        results.append({
            "benchmark": "can-train-and-test",
            "file": name,
            "is_masquerade": False,   # 该基准攻击标注在 attack 列, 此处不做
            "is_attack": False,
            **st,
            "verdict": judge(st),
            "parse_sec": round(time.time() - t0, 1),
        })
    return results


def scan_syncan():
    """SynCAN: CSV 含 Time 列 (相对秒)。注意: 每行信号列数不同(按 ID),
    pandas usecols 会因列宽不一整行跳过 → 流式取第 2 列。"""
    results = []
    for p in sorted(SYNCAN_DIR.glob("**/*.csv")):
        t0 = time.time()
        ts = []
        with open(p, "rb") as f:
            next(f, b"")  # skip header
            for i, line in enumerate(f):
                if i >= 10_000_000:
                    break
                parts = line.split(b",")
                if len(parts) >= 2:
                    try:
                        ts.append(float(parts[1]))
                    except ValueError:
                        pass
        ts = np.asarray(ts, dtype=np.float64)
        st = stat_timestamps(ts)
        name = str(p.relative_to(SYNCAN_DIR))
        results.append({
            "benchmark": "SynCAN",
            "file": name,
            "is_masquerade": "playback" in name,
            "is_attack": not name.startswith("train"),
            **st,
            "verdict": judge(st),
            "parse_sec": round(time.time() - t0, 1),
        })
    return results


def fmt_row(r):
    dt = r["dt"] or {}
    return (f"| {r['benchmark'][:3]} | {r['file'][:52]} | {r['n_rows']:>9,} | "
            f"{dt.get('median', 0):.4f} | {r['strict_increasing_frac']:.4f} | "
            f"{r['reorder_pairs']:>6} | {r['dup_frac']:.4f} | "
            f"{r['on_ms_grid_frac']:.4f} | {r['on_sec_grid_frac']:.4f} | {r['verdict']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scope", nargs="?", default="all",
                    choices=["all", "road", "can-train-and-test", "syncan"])
    args = ap.parse_args()

    all_results = []
    if args.scope in ("all", "road"):
        print("[1/3] scanning ROAD ...", file=sys.stderr)
        all_results += scan_road()
    if args.scope in ("all", "can-train-and-test"):
        print("[2/3] scanning can-train-and-test ...", file=sys.stderr)
        all_results += scan_ctat()
    if args.scope in ("all", "syncan"):
        print("[3/3] scanning SynCAN ...", file=sys.stderr)
        all_results += scan_syncan()

    out_path = OUT_DIR / "audit_phase1.json"
    out_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))

    print("\n## Phase 1 时序完整性统计摘要")
    print("| 基准 | 文件 | 行数 | dt中位(sec) | 严格升序比 | 重排对 | 重复比 | ms网格比 | sec网格比 | 判读 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in all_results:
        print(fmt_row(r))

    verdicts = {}
    for r in all_results:
        verdicts.setdefault(r["benchmark"], {}).setdefault(r["verdict"], 0)
        verdicts[r["benchmark"]][r["verdict"]] += 1
    print("\n### 判读汇总")
    for bench, v in verdicts.items():
        print(f"- **{bench}**: " + ", ".join(f"{k}={c}" for k, c in v.items()))
    print(f"\n完整 JSON: {out_path}")


if __name__ == "__main__":
    main()
