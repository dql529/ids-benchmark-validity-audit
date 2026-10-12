#!/usr/bin/env python3
"""F 审计 Phase 2: masquerade 专项对照 + 抽样逐值核对。

任务 ① 抽样逐值核对（防解析伪影的最后一道）:
   - ROAD: correlated_signal_attack_1_masquerade.log 前 20 行, 行级解析输出
     (与 head 原始文本人工比对)
   - CTAT: rpm-1.csv 前 20 行 timestamp 列 (与原始 CSV 人工比对)
任务 ② ROAD 攻击段 vs ambient 段:
   - capture_metadata.json 提供 injection_interval (elapsed sec, 相对捕获起点)
   - 攻击文件按 interval 切 pre-attack / attack / post-attack 三段, 逐段统计
     (interval 为 null 的 accelerator 类整文件并入 pre 段)
   - masquerade vs 同名非 masquerade 成对对照
任务 ③ CTAT 攻击段 vs 正常段:
   - 按 attack 列切分, 攻击段连通性分析 + 两端 dt 分布 + 网格比例
   - 重点: 攻击帧时间戳是否独立于正常帧生成(边界衔接 dt 与内部模式)

用法: /opt/anaconda3/bin/python3 audit_phase2.py
输出: phase2/audit_phase2.json (机器可读) + 控制台 markdown 摘要
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROAD_DIR = Path(os.path.expanduser("~/Datasets/can_ids/ROAD/road"))
CTAT_DIR = Path(os.path.expanduser("~/Datasets/can_ids/can-train-and-test/set_01"))
GRID_TOL = 1e-6
ROAD_RE = re.compile(rb"^\((\d+\.\d+)\)\s+can\d\s+[0-9A-Fa-f]{3,8}#")


def segment_stats(ts):
    """ts: 一段内的 float64 时间戳数组。返回与 Phase 1 一致的统计 + 补充字段。"""
    n = len(ts)
    if n == 0:
        return {"n": 0, "t_start": None, "t_end": None, "span": None,
                "dt_median": None, "dt_p1": None, "dt_p99": None, "dt_max": None,
                "dt_lt10us": None, "dt_lt135us": None, "sec_grid_frac": None,
                "ms_grid_frac": None}
    dt = np.diff(ts)
    dts = dt[dt > 0]
    dt_med = float(np.median(dts)) if len(dts) else None
    out = {
        "n": n,
        "t_start": round(float(ts[0]), 6),
        "t_end": round(float(ts[-1]), 6),
        "span": round(float(ts[-1] - ts[0]), 6),
        "dt_median": round(dt_med, 9) if dt_med is not None else None,
        "dt_p1": round(float(np.percentile(dts, 1)), 9) if len(dts) else None,
        "dt_p99": round(float(np.percentile(dts, 99)), 9) if len(dts) else None,
        "dt_max": round(float(dts.max()), 9) if len(dts) else None,
        "dt_lt10us": round(float(np.mean(dt < 1e-5)), 6) if n > 1 else None,
        "dt_lt135us": round(float(np.mean(dt < 135e-6)), 6) if n > 1 else None,
        "sec_grid_frac": round(float(np.mean(np.abs(ts - np.round(ts)) < GRID_TOL)), 6),
        "ms_grid_frac": round(float(np.mean(np.abs(ts - np.round(ts / 0.001) * 0.001) < GRID_TOL)), 6),
    }
    return out


def parse_road_file(path, max_lines=None):
    ts = []
    with open(path, "rb") as f:
        for i, line in enumerate(f):
            if max_lines is not None and i >= max_lines:
                break
            m = ROAD_RE.match(line)
            if m:
                ts.append(float(m.group(1)))
    return np.asarray(ts, dtype=np.float64)


def task1_value_check():
    """① 逐值核对: 输出前 20 行解析值, 与 head 原始文本比对。"""
    out = {"samples": []}

    # ROAD 抽样: masquerade 文件 + ambient 文件
    for name in ["attacks/correlated_signal_attack_1_masquerade.log",
                 "ambient/ambient_dyno_drive_basic_short.log"]:
        p = ROAD_DIR / name
        ts = parse_road_file(p, max_lines=20)
        raw_lines = []
        with open(p, "rb") as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                raw_lines.append(line.decode("ascii", "replace").strip())
        out["samples"].append({
            "kind": "ROAD", "file": name,
            "raw_lines": raw_lines,
            "parsed_ts": [round(float(t), 6) for t in ts],
        })

    # CTAT 抽样
    p = CTAT_DIR / "train_01/rpm-1.csv"
    df = pd.read_csv(p, nrows=20)
    with open(p) as f:
        raw_lines = [f.readline().strip() for _ in range(21)]
    out["samples"].append({
        "kind": "CTAT", "file": "train_01/rpm-1.csv",
        "raw_lines": raw_lines,
        "parsed_ts": [float(t) for t in df["timestamp"].tolist()],
    })
    return out


def task2_road_segments():
    """② ROAD 攻击段 vs ambient 段 + masquerade 成对对照。"""
    meta = json.load(open(ROAD_DIR / "attacks/capture_metadata.json"))
    out = {"per_file": [], "masquerade_pairs": [], "summary": {}}

    attack_logs = sorted((ROAD_DIR / "attacks").glob("*.log"))
    for p in attack_logs:
        name = p.stem
        m = meta.get(name, {})
        interval = m.get("injection_interval")  # [start, end] elapsed sec 或 None
        ts = parse_road_file(p)
        n = len(ts)
        if n == 0 or ts[0] is None:
            out["per_file"].append({"file": name, "error": "empty"})
            continue
        t0 = float(ts[0])
        segments = {}
        if interval:
            a0, a1 = float(interval[0]), float(interval[1])
            pre = ts[ts < t0 + a0]
            atk = ts[(ts >= t0 + a0) & (ts <= t0 + a1)]
            post = ts[ts > t0 + a1]
            segments = {"pre_attack": pre, "attack": atk, "post_attack": post}
        else:
            segments = {"pre_attack": ts, "attack": np.array([]), "post_attack": np.array([])}
        seg_stats = {k: segment_stats(v) for k, v in segments.items()}
        out["per_file"].append({
            "file": name,
            "is_masquerade": "_masquerade" in name,
            "injection_interval": interval,
            "n_rows": int(n),
            "segments": seg_stats,
        })

    # masquerade 成对对照: {stem}_masquerade vs {stem}
    pair_names = set()
    for e in out["per_file"]:
        if e["file"].endswith("_masquerade"):
            pair_names.add(e["file"][: -len("_masquerade")])
    for base in sorted(pair_names):
        rec = {}
        for e in out["per_file"]:
            if e["file"] == base:
                rec["normal"] = e
            elif e["file"] == base + "_masquerade":
                rec["masquerade"] = e
        out["masquerade_pairs"].append(rec)

    # 汇总: 各段 dt_median / sec_grid 分布 (跨文件)
    for seg in ["pre_attack", "attack", "post_attack"]:
        meds = [e["segments"][seg]["dt_median"] for e in out["per_file"]
                if e["segments"][seg]["n"] > 100]
        grids = [e["segments"][seg]["sec_grid_frac"] for e in out["per_file"]
                 if e["segments"][seg]["n"] > 100]
        if meds:
            out["summary"][seg] = {
                "n_files_with_segment": len(meds),
                "dt_median_min": min(meds), "dt_median_max": max(meds),
                "dt_median_overall": float(np.median(meds)),
                "sec_grid_frac_min": min(grids), "sec_grid_frac_max": max(grids),
            }

    # ambient 整文件统计
    amb_stats = []
    for p in sorted((ROAD_DIR / "ambient").glob("*.log")):
        ts = parse_road_file(p)
        st = segment_stats(ts)
        st["file"] = p.stem
        amb_stats.append(st)
    out["ambient_files"] = amb_stats
    out["summary"]["ambient"] = {
        "n_files_with_segment": len(amb_stats),
        "dt_median_min": min(e["dt_median"] for e in amb_stats if e["n"] > 100),
        "dt_median_max": max(e["dt_median"] for e in amb_stats if e["n"] > 100),
        "sec_grid_frac_min": min(e["sec_grid_frac"] for e in amb_stats if e["n"] > 100),
        "sec_grid_frac_max": max(e["sec_grid_frac"] for e in amb_stats if e["n"] > 100),
    }
    return out


def task3_ctat_segments():
    """③ CTAT 攻击段 vs 正常段: 帧级 attack 标注切分 + 连通段分析。"""
    out = {"per_file": [], "summary": {}}
    csvs = sorted(CTAT_DIR.glob("**/*.csv"))
    for p in csvs:
        t0 = time.time()
        df = pd.read_csv(p, usecols=["timestamp", "attack"], dtype={"timestamp": np.float64})
        ts = df["timestamp"].to_numpy()
        atk = (df["attack"] == 1).to_numpy()
        n = len(ts)

        normal_ts = ts[~atk]
        atk_ts = ts[atk]

        # 攻击段连通性: attack 列连续 run
        runs = []
        if atk.any():
            idx = np.flatnonzero(np.diff(np.concatenate(([0], atk.view(np.int8), [0]))))
            for i in range(0, len(idx), 2):
                runs.append((int(idx[i]), int(idx[i + 1])))
        n_runs = len(runs)
        run_len = np.diff(np.array(runs), axis=1).ravel() if n_runs else np.array([])

        # 边界衔接: 攻击段首帧 vs 前一个正常帧 的 dt (跨段 dt 泄露检查)
        boundary_dts = []
        for s, e in runs:
            if s > 0:
                boundary_dts.append(float(ts[s] - ts[s - 1]))
            if e < n:
                boundary_dts.append(float(ts[e] - ts[e - 1]))

        rec = {
            "file": str(p.relative_to(CTAT_DIR)),
            "n_rows": int(n),
            "n_attack_frames": int(atk.sum()),
            "attack_frac": round(float(atk.mean()), 6),
            "n_attack_runs": n_runs,
            "run_len_median": int(np.median(run_len)) if n_runs else None,
            "normal": segment_stats(normal_ts),
            "attack": segment_stats(atk_ts),
            "boundary_dt": {
                "min": round(min(boundary_dts), 9) if boundary_dts else None,
                "median": round(float(np.median(boundary_dts)), 9) if boundary_dts else None,
                "max": round(max(boundary_dts), 9) if boundary_dts else None,
                "n": len(boundary_dts),
            },
            "parse_sec": round(time.time() - t0, 1),
        }
        out["per_file"].append(rec)

    # 汇总: normal 段 vs attack 段 (有攻击的文件)
    files_with_atk = [r for r in out["per_file"] if r["n_attack_frames"] > 0]
    out["summary"]["n_files"] = len(out["per_file"])
    out["summary"]["n_files_with_attack"] = len(files_with_atk)
    for seg in ["normal", "attack"]:
        meds = [r[seg]["dt_median"] for r in files_with_atk if r[seg]["n"] > 100]
        grids = [r[seg]["sec_grid_frac"] for r in files_with_atk if r[seg]["n"] > 100]
        if meds:
            out["summary"][seg] = {
                "dt_median_min": min(meds), "dt_median_max": max(meds),
                "dt_median_overall": float(np.median(meds)),
                "sec_grid_frac_min": min(grids), "sec_grid_frac_max": max(grids),
                "sec_grid_frac_overall": float(np.median(grids)),
            }
    return out


def main():
    results = {}
    print("[1/3] 任务① 逐值核对 ...", file=sys.stderr)
    results["task1_value_check"] = task1_value_check()
    print("[2/3] 任务② ROAD 攻击/ambient 段对照 ...", file=sys.stderr)
    results["task2_road"] = task2_road_segments()
    print("[3/3] 任务③ CTAT 攻击/正常段对照 ...", file=sys.stderr)
    results["task3_ctat"] = task3_ctat_segments()

    out_path = HERE / "audit_phase2.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    # ---- 控制台摘要 ----
    print("\n## Phase 2 摘要\n")
    print("### 任务① 逐值核对（人工比对 raw_lines vs parsed_ts）")
    for s in results["task1_value_check"]["samples"]:
        print(f"- {s['kind']} {s['file']}: 解析 {len(s['parsed_ts'])} 行")
        print(f"  raw    : {s['raw_lines'][1] if len(s['raw_lines'])>1 else ''}")
        print(f"  parsed : {s['parsed_ts'][0] if s['parsed_ts'] else ''}")
    print("  → 完整对照在 JSON; 关键: ROAD 起始=整数秒, dt 1-2µs; CTAT 起始=1672531200.0")

    r2 = results["task2_road"]
    print("\n### 任务② ROAD 分段（injection_interval 精确切分）")
    print("| 段 | 文件数 | dt中位 min-max (µs) | 整秒网格 min-max |")
    print("|---|---|---|---|")
    for seg, s in r2["summary"].items():
        if isinstance(s, dict) and "dt_median_min" in s:
            print(f"| {seg} | {s['n_files_with_segment']} | {s['dt_median_min']*1e6:.2f}-{s['dt_median_max']*1e6:.2f} | "
                  f"{s['sec_grid_frac_min']:.3f}-{s['sec_grid_frac_max']:.3f} |")
    print(f"\nmasquerade 成对: {len(r2['masquerade_pairs'])} 对")
    for pr in r2["masquerade_pairs"]:
        nm, mq = pr["normal"], pr["masquerade"]
        # 打印整文件级 dt 对照
        dt_n = nm["segments"]["attack"]["dt_median"] if nm["segments"]["attack"]["n"] else nm["segments"]["pre_attack"]["dt_median"]
        dt_m = mq["segments"]["attack"]["dt_median"] if mq["segments"]["attack"]["n"] else mq["segments"]["pre_attack"]["dt_median"]
        print(f"  {nm['file']}: normal dt={dt_n and dt_n*1e6:.1f}µs | masquerade dt={dt_m and dt_m*1e6:.1f}µs")

    r3 = results["task3_ctat"]
    print("\n### 任务③ CTAT 攻击段 vs 正常段")
    print(f"文件数: {r3['summary']['n_files']} (含攻击: {r3['summary']['n_files_with_attack']})")
    if "normal" in r3["summary"] and "attack" in r3["summary"]:
        n, a = r3["summary"]["normal"], r3["summary"]["attack"]
        print(f"normal 段: dt中位 {n['dt_median_overall']*1e6:.2f}µs (min {n['dt_median_min']*1e6:.2f}, max {n['dt_median_max']*1e6:.2f}), "
              f"整秒网格 {n['sec_grid_frac_overall']:.3f}")
        print(f"attack 段: dt中位 {a['dt_median_overall']*1e6:.2f}µs (min {a['dt_median_min']*1e6:.2f}, max {a['dt_median_max']*1e6:.2f}), "
              f"整秒网格 {a['sec_grid_frac_overall']:.3f}")
    print(f"\n完整 JSON: {out_path}")


if __name__ == "__main__":
    main()
