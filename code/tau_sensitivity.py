#!/usr/bin/env python3
"""Sensitivity of the trivial criterion to the quantile that defines its threshold.

Written 2026-08-12 in response to the ieee-reviewer Method Detective pass: the manuscript
sets tau_0 = Q_0.001 of the benign training deviation ratio and never justifies 0.001. The
defence is that no conclusion depends on it (every negative claim rests on the oracle
criterion, which is defined over all thresholds), but a defence is not a measurement. This
script provides the measurement.

Sweeps the quantile over {0.0005, 0.001, 0.005, 0.01, 0.05} on the CrySyS masquerade set,
which carries the paper's strongest negative claim: all 624 files give a trivial F1 of
exactly 0.0000. If that zero were an artefact of a badly chosen quantile, a different
quantile would break it.

Run: /opt/anaconda3/bin/python3 phase6/tau_sensitivity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crysys_discriminability import LOGS, dt_id_of, parse, true_oracle  # noqa: E402

QUANTILES = [0.0005, 0.001, 0.005, 0.01, 0.05]


def evaluate_at(train_p: Path, test_p: Path, qs: list[float]) -> list[dict] | None:
    """Same pipeline as crysys_discriminability.evaluate, but tau swept over `qs`.

    Everything upstream of the threshold (nominal periods, deviation ratios, oracle) is
    computed once, so the sweep costs one parse per file rather than one per quantile.
    """
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

    dev_tr_benign = dev_of(dt_tr, aid_tr)[y_tr == 0]
    dev_te = dev_of(dt_te, aid_te)
    p = float(y_te.mean())
    out = []
    for q in qs:
        tau = float(np.quantile(dev_tr_benign, q))
        yhat = (dev_te < tau).astype(int)
        tp = int(((yhat == 1) & (y_te == 1)).sum())
        fp = int(((yhat == 1) & (y_te == 0)).sum())
        fn = int(((yhat == 0) & (y_te == 1)).sum())
        out.append({
            "test": test_p.name, "q": q, "tau": tau,
            "trivial_f1": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0,
            "oracle_f1": true_oracle(dev_te, y_te),
            "degenerate_f1": 2 * p / (1 + p),
        })
    return out


def main() -> None:
    files = sorted(p for p in LOGS.glob("*malicious*msg-mod*.log")
                   if "inj-messages" not in p.name)
    rows = []
    for i, p in enumerate(files, 1):
        tr = LOGS / f"{p.name.split('-malicious-')[0]}-benign.log"
        if not tr.exists():
            continue
        r = evaluate_at(tr, p, QUANTILES)
        if r:
            rows.extend(r)
        if i % 100 == 0:
            print(f"  {i}/{len(files)}", file=sys.stderr)
    df = pd.DataFrame(rows)
    n_files = df["test"].nunique()
    print(f"\nCrySyS masquerade, n={n_files} files, quantile sweep\n")
    print(f"{'q':>8}  {'max trivial F1':>15}  {'mean trivial F1':>16}  {'files with F1>0':>16}")
    summary = {}
    for q in QUANTILES:
        s = df[df["q"] == q]["trivial_f1"]
        summary[str(q)] = {"max": float(s.max()), "mean": float(s.mean()),
                           "n_nonzero": int((s > 0).sum()), "n_files": int(len(s))}
        print(f"{q:>8}  {s.max():>15.4f}  {s.mean():>16.4f}  {(s > 0).sum():>13}/{len(s)}")
    orc = df[df["q"] == QUANTILES[0]]
    print(f"\noracle F1 median = {orc['oracle_f1'].median():.4f}  "
          f"(degenerate median {orc['degenerate_f1'].median():.4f}) "
          f"-- unchanged by q, by construction")
    out = Path(__file__).resolve().parent.parent / "results/tau_sensitivity.json"
    out.write_text(json.dumps({"quantiles": summary,
                               "oracle_median": float(orc["oracle_f1"].median()),
                               "degenerate_median": float(orc["degenerate_f1"].median()),
                               "n_files": n_files}, indent=1))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
