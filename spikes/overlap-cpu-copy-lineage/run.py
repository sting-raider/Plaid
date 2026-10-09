"""Execute an exact-pinned ares overlapping uncached word-copy fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/overlap-cpu-copy-lineage"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_builder():
    spec = importlib.util.spec_from_file_location("builder", ROOT / "spikes/003-ares-oracle/run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def worker():
    builder = load_builder()
    assert builder.REV == REV
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    exe = builder.build(HERE / "driver.cpp", OUTPUT / "build", extra_sources=(HERE / "driver.cpp", Path(builder.__file__)))
    raw1 = subprocess.check_output([str(exe)], text=True, timeout=30)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert raw1 == raw2
    data = json.loads(raw1)
    assert data["forward_unique"] == [0x11111111, 0x11111111, 0x11111111, 0x11111111]
    assert data["backward_unique"] == [0x11111111, 0x11111111, 0x22222222, 0x33333333]
    assert data["forward_equal"] == [0xA5A5A5A5] * 4
    assert data["backward_equal"] == [0xA5A5A5A5] * 4
    result = {
        "revision": REV,
        "repeat_equal": True,
        "fixture": data,
        "interpretation": {
            "forward_overlap_self_feeds": True,
            "backward_overlap_preserves_original_words": True,
            "equal_payload_direction_is_not_recoverable_from_final_bytes": True,
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "actual.json"
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(raw1.strip())
    print("ACTUAL_SHA256=" + digest)
    print("PASS exact pinned ares executes forward overlap as self-feeding and backward overlap as preserving source words")


def main():
    if os.name == "nt":
        script = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
