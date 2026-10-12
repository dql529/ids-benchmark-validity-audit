#!/usr/bin/env python3
"""Recompute the physical-floor statistics against a rate-independent bound.

Written 2026-08-12 after the paper-cross-check Gate 6 external lane caught a unit error:
the manuscript used 135 microseconds as the floor for an eight-byte frame at 500 kbit/s,
but 135 is the frame's length in BITS (including the 3-bit interframe space); at
500 kbit/s that is 270 microseconds.

Chasing the unit slip exposed the larger fault behind it: NONE of the audited corpora
documents its bit rate. "500 kbit/s" was an unsourced assumption carried since Phase 1,
and it had been paired with the 1 Mbit/s value of the floor, so the (rate, floor) pair was
internally inconsistent from the start. Recomputing at 500 kbit/s puts 51% of the gaps in
CrySyS -- the one genuinely-recorded corpus, the reference for what a real clock looks
like -- below the floor, which a real recording cannot do. CrySyS is only consistent with
a bus near 1 Mbit/s.

The fix is to stop assuming a rate. Classic CAN's highest standardised bit rate is
1 Mbit/s and its shortest legal frame occupies 47 bit times including the interframe
space, so no legal CAN configuration whatsoever can produce a gap below 47 microseconds.
That bound is looser than any rate-specific one, which is the point: it cannot be
attacked by disputing the bit rate.

A second error surfaced while checking the first. The manuscript derived the floor from
55+10*l bit times, which is the WORST-case frame length (maximal bit stuffing). A lower
bound on the interval must come from the SHORTEST realisable frame, i.e. zero stuff bits:
44+8*l frame bits plus the 3-bit interframe space = 47+8*l. Using the worst case asserts
that every frame suffers maximal stuffing, which is false, and inflates the floor by up to
21 percent. This script uses 47+8*l throughout.

This script reports three quantities per corpus:
  rho_lt_abs   fraction of gaps below the UNIVERSAL bound (47 us): shortest legal frame
               (DLC=0, no stuffing, 44 bits) plus the 3-bit interframe space, at the
               highest standardised classic-CAN rate. Nothing legal goes below this, so
               it needs no assumption about the bus rate -- which matters because NONE of
               the audited corpora documents its rate. This is the value the paper uses.
  rho_lt_exact fraction below the per-gap floor 47+8l from the preceding frame's DLC.
               Tighter, and still rate-assumption-free at 1 Mbit/s; reported to show the
               headline conclusions do not depend on which of the two is chosen.
  rho_lt_old   fraction below 135 us, the superseded manuscript value, kept so the effect
               of the correction is visible rather than silently absorbed.

Run: /opt/anaconda3/bin/python3 audit/recompute_floor.py --output NEW_RUN.json
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import statistics
from decimal import Decimal
from pathlib import Path

R_MAX = 1_000_000  # bit/s -- the maximum standardised classic-CAN rate (ISO 11898-2)
R = R_MAX


def floor_us(dlc: int) -> float:
    """Minimum start-to-start interval after a frame carrying `dlc` payload bytes.

    44 + 8*dlc is the standard-format frame with ZERO stuff bits (SOF 1, ID 11, RTR 1,
    IDE 1, r0 1, DLC 4, data 8*dlc, CRC 15, CRC delimiter 1, ACK slot 1, ACK delimiter 1,
    EOF 7); +3 for the interframe space. Zero stuffing is what makes this a floor -- the
    worst case 55 + 10*dlc is an upper bound on frame length and cannot bound an interval
    from below.
    """
    return (47 + 8 * dlc) / R * 1e6


def worst_us(dlc: int) -> float:
    """Worst-case (maximal stuffing) counterpart, reported for context only."""
    return (55 + 10 * dlc) / R * 1e6


ABS_FLOOR = floor_us(0)   # 47 us at 1 Mbit/s: the UNIVERSAL bound, rate-independent
OLD_FLOOR = worst_us(8)   # 135 us: the value the manuscript used before this correction

ROAD_LINE = re.compile(r"\((\d+)\.(\d{6})\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)")
CRYSYS_LINE = re.compile(r"\(([\d.]+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)")


def summarise(name: str, gaps_us: list[float], floors_us: list[float]) -> dict:
    n = len(gaps_us)
    below_abs = sum(1 for g in gaps_us if g < ABS_FLOOR)
    below_old = sum(1 for g in gaps_us if g < OLD_FLOOR)
    below_exact = sum(1 for g, f in zip(gaps_us, floors_us) if g < f)
    srt = sorted(gaps_us)
    return {
        "name": name, "n": n,
        "median_us": srt[n // 2] if n else None,
        "standard_median_us": (srt[(n - 1) // 2] + srt[n // 2]) / 2 if n else None,
        "n_below_abs": below_abs,
        "rho_lt_abs": below_abs / n if n else None,
        "rho_lt_exact": below_exact / n if n else None,
        "rho_lt_old": below_old / n if n else None,
    }


def road(files: list[Path]) -> None:
    tot_g: list[float] = []
    tot_f: list[float] = []
    per_file = []
    for p in files:
        prev_u = None
        prev_dlc = 0
        g: list[float] = []
        f: list[float] = []
        for line in p.open():
            m = ROAD_LINE.match(line)
            if not m:
                continue
            u = int(m.group(1)) * 1_000_000 + int(m.group(2))
            dlc = len(m.group(4)) // 2
            if prev_u is not None:
                g.append(u - prev_u)
                f.append(floor_us(prev_dlc))
            prev_u, prev_dlc = u, dlc
        if len(g) < 100:
            continue
        per_file.append(summarise(p.name, g, f))
        tot_g += g
        tot_f += f
    print_block("ROAD (45 files)", tot_g, tot_f, per_file)


def ctat(files: list[Path], root: Path | None = None) -> None:
    if root is None:
        root = Path.home() / "Datasets/can_ids/can-train-and-test"
    tot_g: list[float] = []
    tot_f: list[float] = []
    per_file = []
    affected_g: list[float] = []
    affected_medians: list[float] = []
    affected_files: list[str] = []
    for p in files:
        prev_t = None
        prev_dlc = 0
        g: list[float] = []
        f: list[float] = []
        with p.open() as fh:
            rd = csv.reader(fh)
            header = next(rd, None)
            if header is None or header[:4] != ["timestamp", "arbitration_id", "data_field", "attack"]:
                raise ValueError(f"unexpected CTAT columns in {p}: {header}")
            for line_no, r in enumerate(rd, 2):
                if len(r) < 4:
                    raise ValueError(f"short CTAT row at {p}:{line_no}: {r}")
                if r[3].strip() != "0":
                    prev_t = None
                    continue
                t = Decimal(r[0])
                dlc = len(r[2].strip()) // 2
                if prev_t is not None:
                    d = float(t - prev_t) * 1e6
                    if d >= 0:
                        g.append(d)
                        f.append(floor_us(prev_dlc))
                prev_t, prev_dlc = t, dlc
        if len(g) < 100:
            continue
        row = summarise(p.relative_to(root).as_posix(), g, f)
        per_file.append(row)
        if row["rho_lt_abs"] >= 0.30:
            affected_g.extend(g)
            affected_medians.append(row["standard_median_us"])
            affected_files.append(row["name"])
        tot_g += g
        tot_f += f
    title = "can-train-and-test (normal frames only)"
    print_block(title, tot_g, tot_f, per_file)
    DUMP[title]["affected_medians"] = {
        "pooled_gap_median_us": statistics.median(affected_g) if affected_g else None,
        "pooled_gap_denominator": len(affected_g),
        "median_of_file_medians_us": statistics.median(affected_medians) if affected_medians else None,
        "file_denominator": len(affected_medians),
        "files": affected_files,
    }
    print(f"  affected pooled median={DUMP[title]['affected_medians']['pooled_gap_median_us']} us "
          f"(gaps={len(affected_g)}); median of file medians="
          f"{DUMP[title]['affected_medians']['median_of_file_medians_us']} us "
          f"(files={len(affected_medians)})")


def crysys(files: list[Path]) -> None:
    tot_g: list[float] = []
    tot_f: list[float] = []
    per_file = []
    for p in files:
        prev_t = None
        prev_dlc = 0
        g: list[float] = []
        f: list[float] = []
        for line in p.open():
            m = CRYSYS_LINE.match(line)
            if not m:
                continue
            t = float(m.group(1)) * 1e6
            dlc = len(m.group(3)) // 2
            if prev_t is not None:
                g.append(t - prev_t)
                f.append(floor_us(prev_dlc))
            prev_t, prev_dlc = t, dlc
        if len(g) < 100:
            continue
        per_file.append(summarise(p.name, g, f))
        tot_g += g
        tot_f += f
    print_block("CrySyS (benign recordings)", tot_g, tot_f, per_file)


DUMP: dict = {}


def print_block(title, tot_g, tot_f, per_file) -> None:
    s = summarise("POOLED", tot_g, tot_f)
    DUMP[title] = {"pooled": s, "per_file": per_file}
    print(f"\n=== {title} ===")
    print(f"  files={len(per_file)}  gaps={s['n']}  median={s['median_us']:.2f} us")
    print(f"  rho_< UNIVERSAL bound ({ABS_FLOOR:.0f} us)      = {s['rho_lt_abs']:.6f}")
    print(f"  rho_< exact per-gap floor (47+8l)      = {s['rho_lt_exact']:.6f}")
    print(f"  rho_< superseded 135 us value          = {s['rho_lt_old']:.6f}")
    for key in ("rho_lt_abs", "rho_lt_exact"):
        v = sorted(r[key] for r in per_file)
        print(f"  per-file {key}: min={v[0]:.6f} median={statistics.median(v):.6f} max={v[-1]:.6f}")
    lo = [r for r in per_file if r["rho_lt_exact"] < 0.30]
    print(f"  files with rho_< exact below 0.30: {len(lo)}/{len(per_file)}")
    for r in lo[:6]:
        print(f"     {r['rho_lt_exact']:.4f}  median={r['median_us']:.1f} us  {r['name']}")
    # Pooled over the AFFECTED files only. The registry carries both scopes because a
    # corpus with a plausible minority (can-train-and-test: 4 of 52) has two honest
    # denominators, and quoting one while labelling it the other is exactly the
    # file-level/corpus-level confusion corrected on 2026-08-12.
    aff = [r for r in per_file if r["rho_lt_abs"] >= 0.30]
    if aff and len(aff) < len(per_file):
        num = sum(r["n_below_abs"] for r in aff)
        den = sum(r["n"] for r in aff)
        print(f"  rho_< abs pooled over AFFECTED files only ({len(aff)}/{len(per_file)}): "
              f"{num / den:.4f}  (gaps={den})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path,
                        help="new JSON path; existing 2026-08-12 evidence is never overwritten")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.parent.is_dir() or out.exists():
        parser.error(f"output parent must exist and output must be new: {out}")
    road_root = Path.home() / "Datasets/can_ids/ROAD/road"
    sources = {
        "road": sorted((*((road_root / "ambient").glob("*.log")),
                        *((road_root / "attacks").glob("*.log")))),
        "ctat": sorted((Path.home() / "Datasets/can_ids/can-train-and-test").rglob("*.csv")),
        "crysys": sorted((Path.home() / "Datasets/can_ids/CrySyS/logs").glob("*benign*.log")),
    }
    if any(not files for files in sources.values()):
        parser.error("one or more source groups are empty")

    def fingerprints() -> list[dict[str, str | int]]:
        rows = []
        units = {"road": "candump integer microseconds", "ctat": "decimal seconds",
                 "crysys": "timestamp seconds"}
        for group, files in sources.items():
            for path in files:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1 << 20), b""):
                        digest.update(chunk)
                rows.append({"group": group, "path": str(path.resolve()),
                             "bytes": path.stat().st_size, "sha256": digest.hexdigest(),
                             "time_unit": units[group]})
        return rows

    inputs = fingerprints()
    code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"UNIVERSAL bound  = shortest frame + IFS @ 1 Mbit/s = {ABS_FLOOR:.0f} us")
    print(f"8-byte floor @ 1 Mbit/s = {floor_us(8):.0f} us (worst-case stuffing {worst_us(8):.0f} us)")
    print(f"superseded manuscript value = {OLD_FLOOR:.0f} us\n")
    road(sources["road"])
    ctat(sources["ctat"])
    crysys(sources["crysys"])
    if fingerprints() != inputs:
        raise RuntimeError("source content changed during recomputation; no output written")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != code_sha256:
        raise RuntimeError("analysis code changed during recomputation; no output written")
    # Every per-file value is archived, not just the printed summary lines. The 2026-08-12
    # corrections all had the same shape -- a single file's number quoted as the corpus's --
    # and that is only auditable if the per-file table survives the run.
    DUMP["run_contract"] = {"inputs": inputs, "code_sha256": code_sha256,
                            "absolute_floor_us": ABS_FLOOR,
                            "affected_file_threshold": 0.30,
                            "ctat_gap_filter": "adjacent normal frames; nonnegative gaps; >=100 gaps/file"}
    with out.open("x", encoding="utf-8") as stream:
        json.dump(DUMP, stream, indent=1, sort_keys=True)
        stream.write("\n")
    print(f"\nper-file table -> {out}")
