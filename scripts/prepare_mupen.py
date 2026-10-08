"""Apply the research patch only to the exact pinned, clean Mupen checkout."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".refs/mupen64plus-core"
REV = "ba95bab92a76744753bfe61470823a4937850ab0"

def main():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
    if revision != REV:
        raise SystemExit("Mupen revision differs from the pin; refusing patch")
    patch = ROOT / "instruments/mupen/discovery.patch"
    command = ["git", "apply", str(patch)]
    if subprocess.run(command[:2] + ["--reverse", "--check", str(patch)], cwd=REF, capture_output=True).returncode == 0:
        print("Discovery patch already applied")
    else:
        if subprocess.check_output(["git", "diff", "--name-only"], cwd=REF).strip():
            raise SystemExit("Reference has edits; refusing to overwrite")
        subprocess.run(command[:2] + ["--check", str(patch)], cwd=REF, check=True)
        subprocess.run(command, cwd=REF, check=True)
    shutil.copyfile(ROOT / "instruments/mupen/trace_sink.h", REF / "src/device/r4300/new_dynarec/plaid_trace_sink.h")

if __name__ == "__main__":
    main()
