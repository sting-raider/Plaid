"""Build a separately licensed pinned Mupen core for synthetic device sessions.

Linux GCC/make/NASM and SDL2/zlib/libpng headers/runtime libraries are required.
Windows dispatches through WSL Ubuntu. The pinned source export and all outputs
stay under ignored target/, leaving the inspected reference checkout intact.
"""
from pathlib import Path
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import hashlib

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".refs/mupen64plus-core"
REV = "ba95bab92a76744753bfe61470823a4937850ab0"
OUTPUT = ROOT / "target/reference-core"


def build():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() != REV:
        raise SystemExit("Mupen checkout differs from pin")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    inputs = {"revision": REV, "patch": hashlib.sha256((ROOT / "instruments/mupen/discovery.patch").read_bytes()).hexdigest(),
        "sink": hashlib.sha256((ROOT / "instruments/mupen/trace_sink.h").read_bytes()).hexdigest(),
        "recipe": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest = OUTPUT / "build.json"
    library = OUTPUT / "libmupen64plus.so"
    if manifest.exists() and json.loads(manifest.read_text()) == inputs and library.exists():
        print("Pinned reference core build is current"); return
    nasm = os.environ.get("PLAID_NASM") or shutil.which("nasm")
    if not nasm:
        candidate = ROOT / "target/reference-tools/nasm-root/usr/bin/nasm"
        if candidate.exists(): nasm = str(candidate)
    if not nasm: raise SystemExit("NASM required (set PLAID_NASM)")
    with tempfile.TemporaryDirectory(prefix="core-build-", dir=ROOT / "target") as temporary:
        directory = Path(temporary)
        archive = subprocess.check_output(["git", "archive", "--format=tar", REV], cwd=REF)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(directory, filter="data")
        subprocess.run(["git", "init", "--quiet"], cwd=directory, check=True)
        subprocess.run(["git", "apply", str(ROOT / "instruments/mupen/discovery.patch")], cwd=directory, check=True)
        shutil.copyfile(ROOT / "instruments/mupen/trace_sink.h", directory / "src/device/r4300/new_dynarec/plaid_trace_sink.h")
        command = ["make", "all", "-j4", "OSD=0", "NETPLAY=0", "VULKAN=0", "NEW_DYNAREC=1", "OPTFLAGS=-O1", f"AS={nasm}"]
        deps = Path(os.environ.get("PLAID_REF_DEPS", ROOT / "target/reference-tools/core-root"))
        if deps.exists():
            include = deps / "usr/include"
            command += ["PKG_CONFIG=false", f"ZLIB_CFLAGS=-I{include}", "ZLIB_LDLIBS=-l:libz.so.1",
                f"LIBPNG_CFLAGS=-I{include}/libpng16 -I{include}", "LIBPNG_LDLIBS=-l:libpng16.so.16",
                f"SDL_CFLAGS=-I{include}/SDL2 -I{include}/x86_64-linux-gnu -D_REENTRANT", "SDL_LDLIBS=-l:libSDL2-2.0.so.0"]
        log = OUTPUT / "build.log"
        with log.open("w") as stream:
            result = subprocess.run(command, cwd=directory / "projects/unix", stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            print("\n".join(log.read_text().splitlines()[-35:]), file=sys.stderr)
            raise SystemExit(f"Reference build failed; see {log}")
        built = directory / "projects/unix/libmupen64plus.so.2.0.0"
        shutil.copyfile(built, library)
        data_output = OUTPUT / "data"
        shutil.copytree(directory / "data", data_output, dirs_exist_ok=True)
        manifest.write_text(json.dumps(inputs, indent=2) + "\n")
    print(f"Built pinned reference core: {library}")


def main():
    if os.name == "nt":
        path = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", path], check=True, timeout=300)
    else: build()


if __name__ == "__main__": main()
