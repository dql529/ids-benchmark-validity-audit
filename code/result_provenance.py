"""Validate result identity without retrospectively certifying historical runs."""
from __future__ import annotations

import argparse
import csv as csv_module
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_MANIFEST = ROOT / 'phase5/legacy_result_2026-08-11.json'


def verify_result_source(csv: Path, manifest: Path) -> dict[str, object]:
    """Bind the consumed CSV to explicit historical or contract-bound metadata."""
    data = json.loads(manifest.read_text(encoding='utf-8'))
    with csv.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if data.get('csv') != csv.name or data.get('csv_sha256') != digest:
        raise ValueError('CSV hash or filename differs from result manifest')
    kind = data.get('evidence_kind', 'contract_bound')
    if kind == 'historical_result':
        if data.get('input_contract_id') != 'unknown' or data.get('historical_code_sha256') != 'unknown':
            raise ValueError('historical runtime metadata must remain unknown')
        with csv.open(newline='', encoding='utf-8') as stream:
            rows = sum(1 for _ in csv_module.DictReader(stream))
        if rows != data.get('rows'):
            raise ValueError('historical CSV row count differs from manifest')
    elif kind == 'contract_bound':
        contract = json.loads((csv.parent.parent / 'input_contract.json').read_text(encoding='utf-8'))
        payload = {key: contract[key] for key in ('inputs', 'code', 'parameters')}
        identifier = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        if identifier != contract.get('contract_id') or identifier != data.get('contract_id'):
            raise ValueError('result contract ID differs from input contract')
    else:
        raise ValueError(f'unsupported result evidence kind: {kind}')
    # This verifies recorded identity, not the execution or current physical input units.
    return {**data, 'evidence_kind': kind}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=ROOT / 'results/jitter_sensitivity.csv')
    parser.add_argument('--manifest', type=Path,
                        default=ROOT / 'results/jitter_sensitivity_manifest.json')
    args = parser.parse_args()
    result = verify_result_source(args.csv, args.manifest)
    print(f"RESULT SOURCE: {result['evidence_kind']}; CSV identity verified; "
          f"input_contract={result.get('contract_id', result.get('input_contract_id'))}")


if __name__ == '__main__':
    main()
