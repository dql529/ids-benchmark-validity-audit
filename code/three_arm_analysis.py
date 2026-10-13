#!/usr/bin/env python3
"""Three-arm de-confounding analysis (Arm A / B / C).

This is the compute-anchor script for the "Three-Arm De-confounding" rows of
VERIFIED_REGISTRY.md. It was originally run inline; claim-verify Phase B.8 correctly
rejected a compute-anchor whose `script` field did not resolve to a file, so the
computation is committed here verbatim.

Collapse point of a file = the smallest perturbation level at which its trivial F1 falls
below half its unperturbed value. Only files with baseline trivial F1 > 0.3 are counted,
matching the "strong-discriminability" cohort used in the paper.

Run: /opt/anaconda3/bin/python3 phase5/three_arm_analysis.py
"""
from __future__ import annotations

import hashlib
import argparse
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .result_provenance import verify_result_source
else:
    from result_provenance import verify_result_source

CSV = Path(__file__).resolve().parents[1] / "results/jitter_sensitivity.csv"
# Delivered contract-bound provenance: results/jitter_sensitivity_manifest.json
# binds the CSV to input_contract.json (repo root); the legacy manifest
# (phase5/legacy_result_2026-08-11.json) predates the 2026-10-04 contract rerun
# and is not part of this deposit.
MANIFEST = Path(__file__).resolve().parents[1] / "results/jitter_sensitivity_manifest.json"
STRONG_THRESHOLD = 0.3


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=CSV)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    args = parser.parse_args()
    provenance = verify_result_source(args.csv, args.manifest)
    print(f"source: {provenance['evidence_kind']}; input_contract="
          f"{provenance.get('contract_id', provenance.get('input_contract_id'))}")
    print(f"input : {args.csv}")
    print(f"sha256: {sha256(args.csv)}")
    d = pd.read_csv(args.csv)
    print(f"rows  : {len(d)}   groups: {d.groupby(['benchmark', 'arm', 'level']).ngroups}")
    print(f"arms  : {sorted(d.arm.unique())}\n")

    ct = d[d.benchmark == "ctat"]
    base = ct[ct.arm == "none"].set_index(["file", "trainset"])
    strong = base[base.trivial_f1 > STRONG_THRESHOLD]
    print(f"CTAT files with baseline trivial F1 > {STRONG_THRESHOLD}: {len(strong)}\n")

    print("=== collapse points per arm ===")
    for arm in ("A", "B", "C"):
        points: list[float] = []
        total = 0
        for (f, ts), row in strong.iterrows():
            sub = ct[(ct.arm == arm) & (ct.file == f) & (ct.trainset == ts)]
            if sub.empty:
                continue
            total += 1
            g = sub.groupby("level").trivial_f1.mean()
            hit = [lv for lv in sorted(g.index) if g[lv] < row.trivial_f1 / 2]
            if hit:
                points.append(float(hit[0]))
        med = statistics.median(points) if points else None
        first = min(points) if points else None
        print(f"  Arm {arm}: collapsed {len(points)}/{total}  earliest={first}  median={med}")

    print("\n=== CTAT mean trivial F1, Arm B vs Arm C ===")
    print(f"  baseline = {ct[ct.arm == 'none'].trivial_f1.mean():.4f}")
    for lv in (0.05, 0.1, 0.2, 0.5, 1.0):
        vals = {}
        for arm in ("B", "C"):
            s = ct[(ct.arm == arm) & (np.isclose(ct.level, lv))]
            vals[arm] = s.trivial_f1.mean() if len(s) else float("nan")
        print(f"  sigma={lv:<5} ArmB={vals['B']:.4f}  ArmC={vals['C']:.4f}")

    print("\n=== ROAD mean oracle F1 ===")
    rd = d[d.benchmark == "road"]
    print(f"  baseline={rd[rd.arm == 'none'].oracle_f1.mean():.4f}  "
          f"degenerate={rd[rd.arm == 'none'].degenerate_f1.mean():.4f}")
    for arm in ("A", "B", "C"):
        s = rd[rd.arm == arm].groupby("level").oracle_f1.mean()
        print(f"  Arm {arm}: " + "  ".join(f"{float(k):g}->{v:.4f}" for k, v in s.items()))


if __name__ == "__main__":
    main()
