#!/usr/bin/env python3
"""Two-sample KS test: do masquerade-modified frames differ in timing from benign frames
of the SAME arbitration identifier, in the same capture?

Written 2026-08-12 because claim-verify Phase B.5 flagged the paper's KS result as a
phantom experiment: the D and p values appeared in phase6_summary.md but no committed
script computed them. This script makes the claim reproducible. If the numbers had not
reproduced, the paper claim would have had to change, not this script.

The comparison MUST be within one identifier. Comparing all attack frames against all
benign frames yields D=0.88 with a vanishing p-value, which measures identifier
composition (attack frames all carry one 100 ms identifier; benign frames span 18
identifiers with periods from 10 ms to 1000 ms), not timing.

Run: /opt/anaconda3/bin/python3 phase6/ks_same_id_test.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import ks_2samp

LOGS = Path.home() / "Datasets/can_ids/CrySyS/logs"
LINE = re.compile(r"\(([\d.]+)\)\s+\S+\s+([0-9A-Fa-f]+)#(\S*)\s+(\S+)\s+(\S+)")

# The two captures quoted in the paper.
TARGETS = [
    ("S-1-1-malicious-ADD-DECR-msg-mod-0x410-0.4-0.6.log", "410"),
    ("S-2-6-malicious-POS_OFFSET-msg-mod-0x410-0.4-0.6.log", "410"),
    ("S-2-6-malicious-POS_OFFSET-msg-mod-0x410-0.5-0.55.log", "410"),
    ("S-1-1-malicious-ADD-DECR-msg-mod-0x410-0.5-0.55.log", "410"),
]


def parse(path: Path):
    ts, aid, flag = [], [], []
    with path.open() as fh:
        for line in fh:
            m = LINE.match(line)
            if not m:
                continue
            ts.append(float(m.group(1)))
            aid.append(m.group(2).upper().lstrip("0") or "0")
            # CrySyS marks a touched frame with "1" in one of the two trailing
            # columns; untouched frames read "False False". Matching on "True"
            # silently yields zero positives -- claim-verify caught exactly that.
            f4, f5 = m.group(4), m.group(5)
            flag.append(not (f4 == "False" and f5 == "False"))
    return np.array(ts), np.array(aid), np.array(flag)


def same_id_intervals(ts: np.ndarray, aid: np.ndarray, target: str):
    """Return (intervals of modified frames, intervals of benign frames) for one ID."""
    sel = aid == target
    return sel


def main() -> None:
    print(f"logs dir: {LOGS}\n")
    any_run = False
    for fname, target_id in TARGETS:
        p = LOGS / fname
        if not p.exists():
            cands = sorted(LOGS.glob(fname.split("-msg-mod-")[0] + "*msg-mod*"))
            print(f"[skip] {fname} not found; candidates: {[c.name for c in cands[:3]]}")
            continue
        any_run = True
        ts, aid, flag = parse(p)
        tid = target_id.upper().lstrip("0") or "0"
        sel = aid == tid
        if sel.sum() == 0:
            print(f"[skip] {fname}: identifier {target_id} absent "
                  f"(present: {sorted(set(aid))[:12]})")
            continue

        # same-identifier intervals, computed on the target ID's own frame sequence
        idx = np.flatnonzero(sel)
        t_id = ts[idx]
        d_id = np.diff(t_id)
        f_id = flag[idx][1:]  # interval i belongs to the later frame

        mod = d_id[f_id]
        ben = d_id[~f_id]
        print(f"=== {fname}  (ID 0x{target_id}) ===")
        print(f"  frames of this ID: {sel.sum()}   modified: {int(f_id.sum())}   "
              f"benign: {int((~f_id).sum())}")
        if len(mod) < 5 or len(ben) < 5:
            print("  too few samples for a KS test\n")
            continue
        print(f"  modified dt median: {np.median(mod)*1e3:.4f} ms  (n={len(mod)})")
        print(f"  benign   dt median: {np.median(ben)*1e3:.4f} ms  (n={len(ben)})")
        st = ks_2samp(mod, ben)
        print(f"  KS: D={st.statistic:.4f}  p={st.pvalue:.4f}\n")

    if not any_run:
        print("No target capture was processed; listing available msg-mod captures:")
        for c in sorted(LOGS.glob("*msg-mod*"))[:10]:
            print("  ", c.name)
        sys.exit(2)


if __name__ == "__main__":
    main()
