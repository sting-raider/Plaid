#!/usr/bin/env python3
"""Guard the exact pinned reset/NMI producer sources used by this experiment."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"

EXPECTED = {
    "mupen64plus-core": {
        "rev": MUPEN_REV,
        "files": {
            "src/device/device.c": "2c415fb6aaa31e280b43393c97fc401a988effad",
            "src/device/r4300/interrupt.c": "9c81a184c92a2a58eed50265cf816031790fb99b",
            "src/device/pif/pif.c": "f2262039ffe9342c42dc890859c931d4ee76808b",
        },
    },
    "gopher64": {
        "rev": GOPHER_REV,
        "files": {
            "src/device/events.rs": "b4769a4495375cf7e3baf3b77e41ef42e0de683e",
            "src/ui/video.rs": "62ad5b303f5d77d9511c5f4f3bfb073cc38c4217",
            "src/device/exceptions.rs": "629750763f1029347a381fc3f87f1a007e5e25cc",
        },
    },
}

REQUIRED = {
    "mupen64plus-core/src/device/device.c": [
        "add_interrupt_event(&dev->r4300.cp0, HW2_INT, 0);",
        "add_interrupt_event(&dev->r4300.cp0, NMI_INT, 50000000);",
    ],
    "mupen64plus-core/src/device/r4300/interrupt.c": [
        "if (get_event(&cp0->q, type))",
        "event = alloc_node(&cp0->q.pool);",
        "memcpy(buf + len    , &e->data.type , 4);",
        "memcpy(buf + len + 4, &e->data.count, 4);",
        "add_interrupt_event_count(cp0, type, count);",
        "case HW2_INT:",
        "case NMI_INT:",
    ],
    "mupen64plus-core/src/device/pif/pif.c": [
        "void hw2_int_handler(void* opaque)",
        "raise_maskable_interrupt(pif->r4300, CP0_CAUSE_IP4);",
    ],
    "gopher64/src/device/events.rs": [
        "device.cpu.events[name] = Event {",
        "device.cpu.events[next_event_name].enabled = false;",
        "EVENT_TYPE_NMI => device::exceptions::reset_event,",
    ],
    "gopher64/src/ui/video.rs": [
        "COP0_CAUSE_IP4",
        "device::events::EVENT_TYPE_NMI",
        "device.cpu.clock_rate, // 1 second",
    ],
    "gopher64/src/device/exceptions.rs": [
        "pub fn reset_event(device: &mut device::Device)",
        "COP0_CAUSE_IP4",
        "device.cpu.pc = 0xBFC00000;",
    ],
}


def run(*args: str, cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main() -> None:
    root = Path(os.environ.get("PLAID_REFS", ".refs-research")).resolve()
    report: dict[str, object] = {"repos": {}, "required_snippets": {}}
    for name, spec in EXPECTED.items():
        repo = root / name
        if not repo.exists():
            raise SystemExit(f"missing reference checkout: {repo}")
        head = run("git", "rev-parse", "HEAD", cwd=repo)
        if head != spec["rev"]:
            raise SystemExit(f"{name}: expected {spec['rev']}, got {head}")
        hashes: dict[str, str] = {}
        for rel, expected_blob in spec["files"].items():
            blob = run("git", "hash-object", rel, cwd=repo)
            if blob != expected_blob:
                raise SystemExit(f"{name}/{rel}: blob {blob} != {expected_blob}")
            hashes[rel] = blob
        report["repos"][name] = {"rev": head, "blobs": hashes}

    for key, needles in REQUIRED.items():
        repo_name, rel = key.split("/", 1)
        text = (root / repo_name / rel).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise SystemExit(f"{key}: missing guarded semantics: {missing}")
        report["required_snippets"][key] = len(needles)

    payload = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    out = Path("target/reset-hw2-nmi-producer")
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-guard.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"SOURCE_GUARD_SHA256={digest}")


if __name__ == "__main__":
    main()
