"""Build a separately licensed pinned Mupen core for synthetic device sessions.

GCC/make/NASM and SDL2/zlib/libpng headers/runtime libraries are required.
Windows uses native MinGW dependencies (PLAID_REF_DEPS or C:/msys64/mingw64). The pinned source export and all outputs
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
        "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "recipe": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest = OUTPUT / "build.json"
    library = OUTPUT / ("mupen64plus.dll" if os.name == "nt" else "libmupen64plus.so")
    if manifest.exists() and json.loads(manifest.read_text()) == inputs and library.exists():
        print("Pinned reference core build is current"); return
    nasm = os.environ.get("PLAID_NASM") or shutil.which("nasm")
    if not nasm and os.name == "nt" and Path("C:/msys64/usr/bin/nasm.exe").exists():
        nasm = "C:/msys64/usr/bin/nasm.exe"
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
        if os.name == "nt":
            script = directory / "tools/gen_asm_script.sh"
            script.write_bytes(script.read_bytes().replace(b"\r\n", b"\n"))
        command = ["make", "all", "-j4", "OSD=0", "NETPLAY=0", "VULKAN=0", "NEW_DYNAREC=1", "OPTFLAGS=-O1", f"AS={nasm}"]
        deps = Path(os.environ.get("PLAID_REF_DEPS", ROOT / "target/reference-tools/core-root"))
        if os.name == "nt":
            deps = Path(os.environ.get("PLAID_REF_DEPS", "C:/msys64/mingw64"))
            include, lib = deps / "include", deps / "lib"
            command += ["UNAME=MINGW64", "HOST_CPU=x86_64", "PKG_CONFIG=false",
                f"ZLIB_CFLAGS=-I{include.as_posix()}", f"ZLIB_LDLIBS=-L{lib.as_posix()} -lz",
                f"LIBPNG_CFLAGS=-I{include.as_posix()}/libpng16 -I{include.as_posix()}", f"LIBPNG_LDLIBS=-L{lib.as_posix()} -lpng16 -lz",
                f"SDL_CFLAGS=-I{include.as_posix()}/SDL2 -D_REENTRANT", f"SDL_LDLIBS=-L{lib.as_posix()} -lSDL2"]
        elif deps.exists():
            include = deps / "usr/include"
            command += ["PKG_CONFIG=false", f"ZLIB_CFLAGS=-I{include.as_posix()}", "ZLIB_LDLIBS=-l:libz.so.1",
                f"LIBPNG_CFLAGS=-I{include.as_posix()}/libpng16 -I{include.as_posix()}", "LIBPNG_LDLIBS=-l:libpng16.so.16",
                f"SDL_CFLAGS=-I{include.as_posix()}/SDL2 -I{include.as_posix()}/x86_64-linux-gnu -D_REENTRANT", "SDL_LDLIBS=-l:libSDL2-2.0.so.0"]
        env = dict(os.environ)
        if os.name == "nt":
            # Native MSYS tools provide the upstream header-generation shell script.
            env["PATH"] += os.pathsep + "C:/msys64/usr/bin"
        log = OUTPUT / "build.log"
        with log.open("w") as stream:
            result = subprocess.run(command, cwd=directory / "projects/unix", stdout=stream, stderr=subprocess.STDOUT, env=env)
        if result.returncode:
            print("\n".join(log.read_text().splitlines()[-35:]), file=sys.stderr)
            raise SystemExit(f"Reference build failed; see {log}")
        built = directory / "projects/unix" / ("mupen64plus.dll" if os.name == "nt" else "libmupen64plus.so.2.0.0")
        shutil.copyfile(built, library)
        data_output = OUTPUT / "data"
        shutil.copytree(directory / "data", data_output, dirs_exist_ok=True)
        manifest.write_text(json.dumps(inputs, indent=2) + "\n")
    print(f"Built pinned reference core: {library}")


def main():
    build()


if __name__ == "__main__": main()
