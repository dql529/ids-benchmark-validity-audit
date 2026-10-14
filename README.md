# Physical-Plausibility Audit Toolchain for CAN Security Corpora

Artifact accompanying the paper *"Physically implausible timestamps in CAN intrusion
detection benchmarks: a corpus audit and why it went unnoticed"* (Qianli Di, Keju Du,
Gang Chen, Hai Deng; Nanjing University of Aeronautics and Astronautics).

## What this artifact is

The zero-training audit and analysis scripts used in the paper, plus the
result tables it produced. The audit derives a protocol-level lower bound on the
inter-frame gap of the Controller Area Network (47 µs general bound: shortest legal frame
44 bit + a full 3-bit intermission at 1 Mbit/s for standard-format classic CAN).
The floor audit uses corpus-specific eligible gaps; SynCAN is a declared-synthetic
control. ROAD uses integer microseconds, CTAT exact differences followed by floating-point
summaries, and the CrySyS reference and downstream analyses also use floating point.

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
code/                      audit & analysis scripts (Python 3)
  audit_phase1.py          corpus-level audit (floor test, medians, per-file flags)
  audit_phase2.py          segmented timing and attack/benign comparisons
  audit_phase3.py          benign-only and exhaustive-oracle discriminability
  recompute_floor.py       independent recomputation of the 47 µs bound
  jitter_sensitivity.py    clock-perturbation arms A/B/C (produces results CSV)
  analyze.py               statistics over the perturbation sweep (Wilcoxon, Holm)
  three_arm_analysis.py    collapse-point summary + provenance verification
  collapse_model.py        closed-form collapse-point model
  collapse_recall_check.py empirical collapse recall vs. the model
  make_figures.py          pgfplots/TikZ figures from the sweep CSV
  run_contract.py          input-contract hashing (run_contract module)
  result_provenance.py     binds a result CSV to its manifest/contract
  test_run_contract.py     unit tests for run_contract
  test_result_provenance.py unit tests for result_provenance
  crysys_discriminability.py  CrySyS discriminability (phase 6)
  ks_same_id_test.py       KS same-identifier test (phase 6)
  tau_sensitivity.py       tau sensitivity (phase 6)
results/                   result tables (CSV/JSON) as used in the paper
input_contract.json        SHA-256 identity of every raw input and code file of the
                           2026-10-04 contract run behind results/jitter_sensitivity.csv
supplement/                supplementary material S1-S5 (PDF + LaTeX source)
VERIFIED_REGISTRY.md       the paper's single source of truth for every reported number
MANIFEST.sha256            SHA-256 of every file in this deposit
```

## Requirements

Python 3.11+ with `numpy`, `pandas`, `scipy`, and `scikit-learn` (only
`audit_phase3.py` imports scikit-learn, for F1/recall/precision metrics). The audit
itself is zero-training: no model is fitted anywhere. Exact arithmetic uses `int`
(integer-microsecond corpora) and `decimal.Decimal`.

## Data (not included)

The four corpora are public but are not redistributed here; obtain them from their
publishers (references in the paper's Section 2):
**ROAD** (Oak Ridge National Laboratory), **can-train-and-test** (HCRL, Korea University),
**SynCAN** (declared-synthetic control), **CrySyS** (CrySyS Lab, FORTH).

## Reproducing

Run executable analysis scripts from `code/`. The argparse entry points
(`audit_phase1.py`, `recompute_floor.py`, `jitter_sensitivity.py`,
`three_arm_analysis.py`, and `result_provenance.py`) support `--help`; other scripts
use the defaults described in their source, and the contract modules are helpers.
Result tables in `results/` were produced by the runs recorded in
`VERIFIED_REGISTRY.md` (each row carries its provenance). To re-derive a paper
number, locate its row in the registry and run the referenced script with the
recorded arguments.

`results/jitter_sensitivity.csv` (sha256 `c9cf9cd4…`) is the 2026-10-04
contract-bound run. Its identity is verifiable without any experiment:
`three_arm_analysis.py` checks the CSV hash against
`results/jitter_sensitivity_manifest.json` and the manifest's contract ID against
`input_contract.json` (repo root), which records the SHA-256 of every raw input
file and code file that produced the run. The corpus files themselves live at the
paths listed in the contract's `inputs` array and are not redistributed here.

The perturbation sweep and collapse-model scripts additionally read per-file
`cache/*.npz` features derived from the corpora (too large to redistribute):
run `jitter_sensitivity.py --stage cache --run-dir <dir>` first (after placing
the corpora at the paths in `input_contract.json`); `collapse_model.py` expects
those `*.npz` files under `code/cache/`.

## Supplementary material (S1-S5)

`supplement/` contains the paper's supplementary material (S1-S5) as PDF and LaTeX
source: S1 physical-floor construction, S2 audit pseudocode, S3 damage taxonomy,
S4 published statements and measurements, S5 current and historical sensitivity
evidence. These sections moved out of the main text; the main paper references
them by their S-numbers. The two figure sources and the two cited bibliography
entries are included. With a TeX installation providing IEEEtran, IEEEtranN,
algorithm2e, dsfont, siunitx, TikZ/pgfplots and the standard packages:

```sh
cd supplement
latexmk -pdf -interaction=nonstopmode -halt-on-error main_ieee_supplement.tex
```

The deposited PDF is the manuscript companion; rebuild metadata may differ while
rendered content remains unchanged.

## License

MIT (see LICENSE). Applies to the code, result tables, and registry in this deposit.

## Release

v1.0.2 (2026-10-14) — fixes from the pre-submission code review: the phase-1
verdict threshold corrected to the 47 µs general bound (135 µs wording retired),
the deprecated grid-based verdict branch removed, floor-recompute evidence JSONs
and the 2026-10-04 contract-bound sensitivity CSV (+ manifest + input contract)
now delivered in-package, flat-layout imports fixed, and supplementary material
S1-S5 included. Supersedes v1.0.1.

v1.0.1 (2026-10-12) — initial release + MIT license, accompanying the manuscript.
Archived on Zenodo: doi:10.5281/zenodo.23321428.

## Provenance scope

The registry retains historical hashes, including the superseded sensitivity CSV.
They are not the identity of the current CSV. Original absolute input paths in
`input_contract.json` and `results/floor_recompute_2026-10-02.json` are retained
without rewriting the archived provenance. Historical project paths in registry rows
refer to the original analysis layout; the delivered floor tables are under `results/`.
The existing Zenodo version DOI is `10.5281/zenodo.23321428`; the version-family
(concept) DOI is `10.5281/zenodo.23321427`.
