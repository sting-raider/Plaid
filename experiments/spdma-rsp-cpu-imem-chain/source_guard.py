#!/usr/bin/env python3
from pathlib import Path
import subprocess, tomllib

EXPECTED = [
    ("7041402beb2ce63a43336ae627372098af50ff0f", "research/sp-dma-dmem-ingress.md", "1d80c92dc22542039494bd606c886a7cafa1d234"),
    ("7041402beb2ce63a43336ae627372098af50ff0f", "spikes/043-ares-sp-dma-dmem-ingress/run.py", "03fe4653abfe75576337dc001ffaf23f7da3d3ba"),
    ("3c89a579aef404dba01aab2353ac2f8723750907", "research/rsp-scalar-load-store-lineage.md", "f81500f36a8ccb438cfaee412cab1cfd33c95aee"),
    ("537f230bc85788c4ff573a716a42acb7809f4989", "research/rsp-dmem-cpu-copy-imem-fetch.md", "41935dd029d85ce51f3834f6e242e627ddd900f4"),
    ("537f230bc85788c4ff573a716a42acb7809f4989", "experiments/rsp-dmem-cpu-copy-imem-fetch/model.py", "6c88a109ba8ce1664139e431ce2714643c39209f"),
]
ARES = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

for commit, path, want in EXPECTED:
    got = subprocess.check_output(["git", "rev-parse", f"{commit}:{path}"], text=True).strip()
    if got != want:
        raise SystemExit(f"source guard mismatch {commit}:{path}: {got} != {want}")

with Path("refs.lock.toml").open("rb") as f:
    refs = tomllib.load(f)
actual = {r["name"]: r["rev"] for r in refs["repo"]}.get("ares")
if actual != ARES:
    raise SystemExit(f"ares pin drift: {actual} != {ARES}")
print(f"PASS: guarded {len(EXPECTED)} prior artifacts and ares {ARES}")
