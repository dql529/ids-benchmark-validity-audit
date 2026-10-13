# Physical-Plausibility Audit Toolchain for CAN Security Corpora

Artifact accompanying the paper *"Physically implausible timestamps in CAN intrusion
detection benchmarks: a corpus audit and why it went unnoticed"* (Qianli Di, Keju Du,
Gang Chen, Hai Deng; Nanjing University of Aeronautics and Astronautics).

## What this artifact is

The complete zero-training, exact-arithmetic audit toolchain used in the paper, plus the
result tables it produced. The audit derives a protocol-level lower bound on the
inter-frame gap of the Controller Area Network (47 µs general bound: shortest legal frame
44 bit + intermission 3 bit at the maximum standard bit rate 1 Mbit/s) and tests every
gap of four public corpora against it.

Headline findings reproduced by this code:
- ROAD: all 45 captures have median inter-frame gaps of exactly 1.000 or 2.000 µs;
  64.1 % of gaps fall below the physical floor.
- can-train-and-test (set_01): 48 of 52 normal-frame files physically implausible;
  pooled median 11.0 µs; 65.4 % of gaps below the floor.
- CrySyS (genuinely recorded clocks): 0.00022 % of gaps below the floor
  (0.0056 % in its worst file).
- Under the per-identifier projection that timing-based detectors model, the same ROAD
  data looks textbook-correct (0 of 106 identifiers with implausible median period) —
  the paper names this failure mode *projection invisibility*.

## Contents

```
code/                 audit & analysis scripts (Python 3, standard library only)
  audit_phase1.py     corpus-level audit (floor test, medians, per-file flags)
  audit_phase2.py     per-identifier projection analysis
  audit_phase3.py     taxonomy classification (L0/L1/L2/L3)
  phase5_*.py         discriminability arms, jitter/tau sensitivity, collapse model,
                      figures, provenance & run-contract checks
  phase6_*.py         CrySyS discriminability, KS same-ID test, tau sensitivity
  recompute_floor.py  independent recomputation of the 47 µs bound
results/              result tables (CSV/JSON) as used in the paper
VERIFIED_REGISTRY.md  the paper's single source of truth for every reported number
MANIFEST.sha256       SHA-256 of every file in this deposit
```

## Requirements

Python 3.10+ with the standard library. No ML frameworks: the audit is zero-training.
Exact arithmetic uses `int` (integer-microsecond corpora) and `decimal.Decimal`.

## Data (not included)

The four corpora are public but are not redistributed here; obtain them from their
publishers (references in the paper's Section 2):
**ROAD** (Oak Ridge National Laboratory), **can-train-and-test** (HCRL, Korea University),
**SynCAN** (declared-synthetic control), **CrySyS** (CrySyS Lab, FORTH).

## Reproducing

Each script is standalone CLI; run with `--help` for arguments. Result tables in
`results/` were produced by the runs recorded in `VERIFIED_REGISTRY.md` (each row carries
its provenance). To re-derive a paper number, locate its row in the registry and run the
referenced script with the recorded arguments.

## License

MIT (see LICENSE). Applies to the code, result tables, and registry in this deposit.

## Release

v1.0.1 (2026-10-12) — initial release + MIT license, accompanying the manuscript.
Archived on Zenodo: doi:10.5281/zenodo.23321428.
