"""Bounded result-provenance tests; no Phase 5 experiments."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from result_provenance import verify_result_source


class ResultProvenanceTest(unittest.TestCase):
    def test_legacy_csv_mutation_changes_readout_and_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv = root / 'jitter_sensitivity.csv'
            csv.write_text('trivial_f1\n0.3\n')
            manifest = root / 'legacy.json'
            manifest.write_text(json.dumps({'evidence_kind': 'historical_result',
                'csv': csv.name, 'csv_sha256': hashlib.sha256(csv.read_bytes()).hexdigest(),
                'rows': 1, 'input_contract_id': 'unknown', 'historical_code_sha256': 'unknown'}))
            result = verify_result_source(csv, manifest)
            self.assertEqual(result['evidence_kind'], 'historical_result')
            csv.write_text('trivial_f1\n0.9\n')
            self.assertIn('0.9', csv.read_text())
            with self.assertRaisesRegex(ValueError, 'CSV hash'):
                verify_result_source(csv, manifest)

    def test_contract_bound_result_requires_matching_input_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv = root / 'results/jitter_sensitivity.csv'
            csv.parent.mkdir()
            csv.write_text('trivial_f1\n0.3\n')
            contract = {'inputs': [], 'code': {}, 'parameters': {}}
            identifier = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
            (root / 'input_contract.json').write_text(json.dumps({**contract, 'contract_id': identifier}))
            manifest = csv.with_name('jitter_sensitivity_manifest.json')
            metadata = {'csv': csv.name, 'csv_sha256': hashlib.sha256(csv.read_bytes()).hexdigest(),
                        'contract_id': identifier}
            manifest.write_text(json.dumps(metadata))
            self.assertEqual(verify_result_source(csv, manifest)['evidence_kind'], 'contract_bound')
            metadata['contract_id'] = 'wrong'
            manifest.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'contract ID'):
                verify_result_source(csv, manifest)

    def test_legacy_cannot_claim_a_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv = root / 'jitter_sensitivity.csv'
            csv.write_text('trivial_f1\n0.3\n')
            manifest = root / 'legacy.json'
            manifest.write_text(json.dumps({'evidence_kind': 'historical_result',
                'csv': csv.name, 'csv_sha256': hashlib.sha256(csv.read_bytes()).hexdigest(),
                'rows': 1, 'input_contract_id': 'invented', 'historical_code_sha256': 'unknown'}))
            with self.assertRaisesRegex(ValueError, 'historical.*unknown'):
                verify_result_source(csv, manifest)


if __name__ == '__main__':
    unittest.main()
