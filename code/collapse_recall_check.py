#!/usr/bin/env python3
"""Reproduce the Section 5.4 headline statistic from data.

Why this exists
---------------
The paper states: "Across 80 file-sigma pairs this predicts observed recall with Spearman
rho = 0.699 (p = 5.8e-13) and a median absolute error of 0.034, with 13 of 16 files below
0.10." Those three numbers appear in VERIFIED_REGISTRY.md sourced to a prose record
("CLAUDE.md Phase 5 段") and in math_formalization.md, but no script in the repository
computes them. collapse_model.py is the closest thing and computes something else -- the
collapse POINT sigma* over 16 files, giving rho = 0.736 -- so it cannot be the source.

ieee-reviewer checked the claim by verifying that p = 5.8e-13 is consistent with rho = 0.699
at n = 80 (t = 8.633). That checks the two reported numbers against each other, not either
against the data.

This script closes that gap. It reuses collapse_model.py's deviation-ratio computation
verbatim -- same nominal period per identifier, same 0.001 quantile threshold -- and adds
only the per-(file, sigma) recall comparison the paper describes.

Model under test, Equation (5):
    tau(sigma) = tau0 * exp(-sigma^2/2 + sigma * z_0.001)
    predicted recall(sigma) = F_atk(tau(sigma))     empirical CDF of the attack-frame dev
Observed recall is the seed mean of trivial_recall from results/jitter_sensitivity.csv.

Run: /opt/anaconda3/bin/python3 phase5/collapse_recall_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import jitter_sensitivity as J  # noqa: E402

D = pd.read_csv(ROOT / "results" / "jitter_sensitivity.csv")
BASE = D[D.arm == "none"].set_index(["benchmark", "file"])
Z = float(norm.ppf(0.001))
SIGMAS = [0.05, 0.10, 0.20, 0.50, 1.00]


def tau_of(sigma: float, tau0: float) -> float:
    return tau0 * np.exp(-0.5 * sigma ** 2 + sigma * Z)


def dev_arrays(key: str, avail: set[str]) -> tuple[float, np.ndarray]:
    """(tau0, deviation ratios of the test file's attack frames), level=0.

    Lifted from collapse_model.py so the two scripts cannot drift apart.
    """
    ts, aid, y, seg = J._load(key)
    tr = J._load(J.resolve_trainset("ctat", key, avail))
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
    return tau0, dev_te[y == 1]


def main() -> None:
    avail = {p.stem for p in (HERE / "cache").glob("*.npz")}
    strong = BASE.loc["ctat"]
    strong = strong[strong.trivial_f1 > 0.3].index.tolist()
    obs_all = (D[D.arm != "none"]
               .groupby(["benchmark", "file", "arm", "level"])["trivial_recall"]
               .mean().reset_index())

    rows = []
    for f in strong:
        tau0, d_atk = dev_arrays("ctat__" + f, avail)
        if not len(d_atk):
            continue
        for s in SIGMAS:
            pred = float((d_atk < tau_of(s, tau0)).mean())
            for arm in ("B", "C"):
                m = obs_all[(obs_all.benchmark == "ctat") & (obs_all.file == f)
                            & (obs_all.arm == arm) & (obs_all.level == s)]
                if not len(m):
                    continue
                rows.append({"file": f.split("|")[-1].replace(".csv", ""),
                             "sigma": s, "arm": arm, "pred": pred,
                             "obs": float(m.trivial_recall.iloc[0])})

    df = pd.DataFrame(rows)
    out = {"n_files": len(strong), "sigmas": SIGMAS, "z_0.001": Z, "arms": {}}
    print(f"files with baseline trivial_f1 > 0.3: {len(strong)}")
    for arm in ("B", "C"):
        g = df[df.arm == arm]
        if not len(g):
            continue
        rho, p = spearmanr(g.pred, g.obs)
        ae = (g.pred - g.obs).abs()
        # The paper's "median absolute error" is the median across FILES of each file's
        # MEAN absolute error, not the median of all 80 residuals. The two differ by 3x
        # (0.034 vs 0.011) because the two interval-manipulation files carry large errors
        # that a per-file mean keeps and a pooled median discards. Established by
        # reproducing all four reported numbers under this definition and no other.
        per_file = g.assign(ae=ae).groupby("file")["ae"].mean()
        out["arms"][arm] = {
            "n_pairs": int(len(g)), "spearman_rho": round(float(rho), 4),
            "p_value": float(p), "mae_median": round(float(per_file.median()), 4),
            "mae_pooled_median": round(float(ae.median()), 4),
            "files_mae_below_0.10": int((per_file < 0.10).sum()),
            "n_files_scored": int(len(per_file)),
            "worst_files": {k: round(float(v), 3)
                            for k, v in per_file.nlargest(3).items()},
        }
        a = out["arms"][arm]
        print(f"  arm {arm}: n={a['n_pairs']}  rho={a['spearman_rho']}  "
              f"p={a['p_value']:.2e}  median MAE={a['mae_median']}  "
              f"files MAE<0.10: {a['files_mae_below_0.10']}/{a['n_files_scored']}")
        print(f"           worst: {a['worst_files']}")

    (ROOT / "audit" / "collapse_recall_check.json").write_text(
        json.dumps(out, indent=2) + "\n")
    df.to_csv(ROOT / "audit" / "collapse_recall_points.csv", index=False)
    print("\nwrote audit/collapse_recall_check.json and audit/collapse_recall_points.csv")
    print("paper claims: rho=0.699 p=5.8e-13 n=80 median MAE=0.034 files<0.10 = 13/16")


if __name__ == "__main__":
    main()
