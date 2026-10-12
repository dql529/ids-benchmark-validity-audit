"""Input and cache fingerprints for a single Phase 5 run directory."""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def syncan_has_header(first_row: list[str]) -> bool:
    if first_row[:3] == ["Label", "Time", "ID"]:
        return True
    if len(first_row) >= 3 and first_row[0] in {"0", "1"} \
            and first_row[2].startswith("id"):
        try:
            Decimal(first_row[1])
            int(first_row[2][2:])
        except (InvalidOperation, ValueError):
            pass
        else:
            return False
    raise ValueError(f"SynCAN first row has unknown layout: {first_row[:3]}")


def input_snapshot(roots: dict[str, Path]) -> list[dict[str, str | int]]:
    patterns = {
        "ctat": ("train_01/*.csv", "test_*/*.csv"),
        "road": ("ambient/*.csv", "attacks/*.csv"),
        "syncan": ("train_*/train_*.csv", "test_*/test_*.csv"),
    }
    expected = {"ctat": {"timestamp", "arbitration_id", "attack"},
                "road": {"Label", "Time", "ID"}}
    units = {"ctat": "seconds", "road": "seconds", "syncan": "milliseconds"}
    rows: list[dict[str, str | int]] = []
    for kind, globs in patterns.items():
        root = roots[kind]
        for pattern in globs:
            files = sorted(root.glob(pattern))
            if not files:
                raise ValueError(f"{kind}: no inputs match {root / pattern}")
            for path in files:
                with path.open(newline="", encoding="utf-8-sig") as stream:
                    header = next(csv.reader(stream), [])
                if kind == "syncan":
                    layout = "header" if syncan_has_header(header) else "no_header"
                elif not expected[kind].issubset(set(header)):
                    raise ValueError(f"{path}: unexpected columns {header[:6]}")
                else:
                    layout = "header"
                rows.append({"kind": kind, "path": str(path.resolve()),
                             "bytes": path.stat().st_size, "sha256": sha256(path),
                             "time_unit": units[kind], "layout": layout})
    return rows


def cache_snapshot(cache_dir: Path) -> list[dict[str, str | int]]:
    files = sorted(cache_dir.glob("*.npz"))
    if not files:
        raise ValueError(f"no cache arrays in {cache_dir}")
    return [{"name": path.name, "bytes": path.stat().st_size,
             "sha256": sha256(path)} for path in files]


def check_snapshot(label: str, expected: object, actual: object) -> None:
    if expected == actual:
        return
    old = {r.get("path", r.get("name")): r for r in expected} if isinstance(expected, list) else expected
    new = {r.get("path", r.get("name")): r for r in actual} if isinstance(actual, list) else actual
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(old.keys() | new.keys()):
            if old.get(key) != new.get(key):
                raise ValueError(f"{label} changed at {key}: expected={old.get(key)} actual={new.get(key)}")
    raise ValueError(f"{label} changed: expected={expected} actual={actual}")


def write_manifest(path: Path, inputs: list[dict[str, str | int]],
                   caches: list[dict[str, str | int]],
                   code: dict[str, str], parameters: dict[str, object]) -> None:
    contract = {"inputs": inputs, "code": code, "parameters": parameters}
    contract_id = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    path.write_text(json.dumps({"contract_id": contract_id, **contract, "caches": caches},
                               indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_manifest(path: Path, inputs: list[dict[str, str | int]],
                    caches: list[dict[str, str | int]],
                    code: dict[str, str], parameters: dict[str, object]) -> str:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    contract = {"inputs": manifest["inputs"], "code": manifest["code"],
                "parameters": manifest["parameters"]}
    actual_id = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    check_snapshot("contract_id", manifest["contract_id"], actual_id)
    for label, actual in (("inputs", inputs), ("caches", caches),
                          ("code", code), ("parameters", parameters)):
        check_snapshot(label, manifest[label], actual)
    return actual_id
