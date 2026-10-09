#!/usr/bin/env python3
"""Guard the exact Plaid research inputs composed by this experiment."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
ARES = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

INPUTS = [
    (
        "cda3b458dc1ac77c639a1afc02a05daac642e861",
        "research/rsp-dmem-cpu-refetch-lineage.md",
        "212a7e10812e24406df4c68409216ae9b1c826f7",
        "3bdbf149b3b382fb9fb38c8381a0fee32d4e1045f804f12bebb2ba1066091957",
    ),
    (
        "cda3b458dc1ac77c639a1afc02a05daac642e861",
        "spikes/043-ares-rsp-dmem-cpu-refetch/run.py",
        "a0cff6263697ead0abfbf3bbaddcc45b1f783b4e",
        "phase_writers",
    ),
    (
        "5c13859e536bf42fcfae9e56b9104f5ff6292590",
        "research/cpu-sp-dmem-imem-copy.md",
        "d894a31d3110c76217415a2956533c17b65315ab",
        "45f3126878657b9c084572a7e943a024ca05dad6c5c47a3cfa1e0cc7ab18a39c",
    ),
    (
        "5c13859e536bf42fcfae9e56b9104f5ff6292590",
        "spikes/043-cpu-sp-dmem-imem-copy-gpt56sol/run.py",
        "f7fdad02b938c973a6c3b23b161d7e2c6f5022fb",
        "read_ordinal",
    ),
    (
        "211176e7a489fecf8331d02915ee982cd279cb62",
        "research/rsp-imem-provenance.md",
        "5a04b1f147899db6f865b99495d6ad84c122d0cd",
        "latest-writer",
    ),
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    lock = tomllib.loads((ROOT / "refs.lock.toml").read_text(encoding="utf-8"))
    pins = {row["name"]: row["rev"] for row in lock["repo"]}
    assert pins["ares"] == ARES, (pins["ares"], ARES)

    for commit, path, expected_blob, required_text in INPUTS:
        resolved = git("rev-parse", f"{commit}^{{commit}}")
        assert resolved == commit, (resolved, commit)
        blob = git("rev-parse", f"{commit}:{path}")
        assert blob == expected_blob, (commit, path, blob, expected_blob)
        text = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT, text=True)
        assert required_text in text, (path, required_text)
        assert ARES in text, path

    print("PASS: exact prior research commits/blobs and refs.lock ares pin verified")


if __name__ == "__main__":
    main()
