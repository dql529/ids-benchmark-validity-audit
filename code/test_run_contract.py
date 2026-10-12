"""Isolated checks for Phase 5's cache-to-sweep input gate."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

if __package__:
    from . import jitter_sensitivity, run_contract
else:
    import jitter_sensitivity
    import run_contract


class RunContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.roots = {kind: base / kind for kind in ("ctat", "road", "syncan")}
        samples = {
            "ctat": ("train_01/a.csv", "test_01/a.csv", "timestamp,arbitration_id,attack\n1.0,0F9,0\n"),
            "road": ("ambient/a.csv", "attacks/a.csv", "Label,Time,ID\n0,1.0,249\n"),
            "syncan": ("train_01/train_01.csv", "test_01/test_01.csv", "Label,Time,ID\n0,1000,id1\n"),
        }
        for kind, (first, second, content) in samples.items():
            for name in (first, second):
                path = self.roots[kind] / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        headerless = self.roots["syncan"] / "train_02/train_02.csv"
        headerless.parent.mkdir(parents=True)
        headerless.write_text("0,1001,id8,0.1\n0,1002,id8,0.2\n", encoding="utf-8")
        self.run_dir = base / "run"
        self.cache_dir = self.run_dir / "cache"
        self.cache_dir.mkdir(parents=True)
        (self.cache_dir / "one.npz").write_bytes(b"baseline cache")
        self.inputs = run_contract.input_snapshot(self.roots)
        self.caches = run_contract.cache_snapshot(self.cache_dir)
        self.code = {
            "jitter_sensitivity.py": run_contract.sha256(Path(jitter_sensitivity.__file__)),
            "run_contract.py": run_contract.sha256(Path(run_contract.__file__)),
        }
        self.parameters = {
            "syncan_time_scale": jitter_sensitivity.SYNCAN_TIME_SCALE,
            "arm_a_levels_us": jitter_sensitivity.ARM_A_LEVELS_US,
            "arm_b_sigmas": jitter_sensitivity.ARM_B_SIGMAS,
            "arm_c_sigmas": jitter_sensitivity.ARM_C_SIGMAS,
            "n_seeds": jitter_sensitivity.N_SEEDS,
            "arm_b_attack_independent": sorted(jitter_sensitivity.ARM_B_ATTACK_INDEPENDENT),
            "numpy_version": np.__version__, "pandas_version": pd.__version__,
        }
        self.manifest = self.run_dir / "input_contract.json"
        run_contract.write_manifest(self.manifest, self.inputs, self.caches,
                                    self.code, self.parameters)

    def test_source_mutation_is_read_and_rejected(self) -> None:
        path = self.roots["ctat"] / "test_01/a.csv"
        path.write_text("timestamp,arbitration_id,attack\n1.1,0F9,0\n", encoding="utf-8")
        actual = run_contract.input_snapshot(self.roots)
        old = next(row for row in self.inputs if row["path"] == str(path.resolve()))
        new = next(row for row in actual if row["path"] == str(path.resolve()))
        self.assertNotEqual(old["sha256"], new["sha256"])
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            run_contract.verify_manifest(self.manifest, actual, self.caches,
                                         self.code, self.parameters)

    def test_direct_sweep_blocks_changed_cache_before_workers(self) -> None:
        (self.cache_dir / "one.npz").write_bytes(b"mutated cache")
        actual = run_contract.cache_snapshot(self.cache_dir)
        self.assertNotEqual(self.caches[0]["sha256"], actual[0]["sha256"])
        argv = ["jitter_sensitivity.py", "--stage", "sweep", "--run-dir", str(self.run_dir)]
        with patch.object(jitter_sensitivity, "CTAT_DIR", self.roots["ctat"]), \
             patch.object(jitter_sensitivity, "ROAD_SIG", self.roots["road"]), \
             patch.object(jitter_sensitivity, "SYNCAN_DIR", self.roots["syncan"]), \
             patch.object(sys, "argv", argv), \
             patch.object(jitter_sensitivity, "run_sweep") as sweep:
            with self.assertRaisesRegex(ValueError, "caches changed"):
                jitter_sensitivity.main()
            sweep.assert_not_called()

    def test_direct_sweep_blocks_changed_source_before_workers(self) -> None:
        source = self.roots["ctat"] / "test_01/a.csv"
        source.write_text("timestamp,arbitration_id,attack\n1.1,0F9,0\n", encoding="utf-8")
        argv = ["jitter_sensitivity.py", "--stage", "sweep", "--run-dir", str(self.run_dir)]
        with patch.object(jitter_sensitivity, "CTAT_DIR", self.roots["ctat"]), \
             patch.object(jitter_sensitivity, "ROAD_SIG", self.roots["road"]), \
             patch.object(jitter_sensitivity, "SYNCAN_DIR", self.roots["syncan"]), \
             patch.object(sys, "argv", argv), \
             patch.object(jitter_sensitivity, "run_sweep") as sweep:
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                jitter_sensitivity.main()
            sweep.assert_not_called()

    def test_valid_direct_sweep_writes_bound_result_manifest(self) -> None:
        argv = ["jitter_sensitivity.py", "--stage", "sweep", "--run-dir", str(self.run_dir)]

        def produce_result(pilot: bool, workers: int, run_dir: Path) -> Path:
            output = run_dir / "results" / "jitter_sensitivity.csv"
            output.parent.mkdir(parents=True)
            output.write_text("benchmark,trivial_f1\nctat,0.5\n", encoding="utf-8")
            return output

        with patch.object(jitter_sensitivity, "CTAT_DIR", self.roots["ctat"]), \
             patch.object(jitter_sensitivity, "ROAD_SIG", self.roots["road"]), \
             patch.object(jitter_sensitivity, "SYNCAN_DIR", self.roots["syncan"]), \
             patch.object(sys, "argv", argv), \
             patch.object(jitter_sensitivity, "run_sweep", side_effect=produce_result) as sweep:
            jitter_sensitivity.main()
            sweep.assert_called_once()
        result_manifest = self.run_dir / "results" / "jitter_sensitivity_manifest.json"
        self.assertIn(run_contract.sha256(self.run_dir / "results" / "jitter_sensitivity.csv"),
                      result_manifest.read_text(encoding="utf-8"))

    def test_cache_stage_refuses_existing_run_directory(self) -> None:
        argv = ["jitter_sensitivity.py", "--stage", "cache", "--run-dir", str(self.run_dir)]
        with patch.object(sys, "argv", argv), \
             patch.object(jitter_sensitivity.run_contract, "input_snapshot") as snapshot:
            with self.assertRaises(SystemExit):
                jitter_sensitivity.main()
            snapshot.assert_not_called()

    def test_cache_stage_writes_a_new_bound_cache(self) -> None:
        fresh = Path(self.temp.name) / "fresh_run"
        argv = ["jitter_sensitivity.py", "--stage", "cache", "--run-dir", str(fresh)]
        with patch.object(jitter_sensitivity, "CTAT_DIR", self.roots["ctat"]), \
             patch.object(jitter_sensitivity, "ROAD_SIG", self.roots["road"]), \
             patch.object(jitter_sensitivity, "SYNCAN_DIR", self.roots["syncan"]), \
             patch.object(sys, "argv", argv):
            jitter_sensitivity.main()
        manifest = fresh / "input_contract.json"
        self.assertTrue(manifest.is_file())
        self.assertEqual(len(run_contract.cache_snapshot(fresh / "cache")), 5)

    def test_syncan_headerless_training_keeps_first_frame(self) -> None:
        source = self.roots["syncan"] / "train_02/train_02.csv"
        parsed = jitter_sensitivity._syncan_one(source)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed["arbitration_id"].tolist(), ["id8", "id8"])
        snapshot = run_contract.input_snapshot(self.roots)
        row = next(item for item in snapshot if item["path"] == str(source.resolve()))
        self.assertEqual(row["layout"], "no_header")

    def test_pilot_sweep_reads_its_run_directory(self) -> None:
        isolated = Path(self.temp.name) / "pilot_run"
        cache = isolated / "cache"
        cache.mkdir(parents=True)
        train = {"ts": np.array([0., 1., 2., 3.]), "aid": np.ones(4, dtype=int),
                 "y": np.zeros(4, dtype=int), "seg": np.zeros(4, dtype=int)}
        test = {**train, "y": np.array([0, 0, 1, 1])}
        np.savez_compressed(cache / "ctat__TRAINSET|ALL.npz", **train)
        np.savez_compressed(cache / "ctat__test_01|a.csv.npz", **test)
        output = jitter_sensitivity.run_sweep(pilot=True, workers=1, run_dir=isolated)
        self.assertEqual(len(pd.read_csv(output)), 4)
        with self.assertRaises(FileExistsError):
            jitter_sensitivity.run_sweep(pilot=True, workers=1, run_dir=isolated)


if __name__ == "__main__":
    unittest.main()
