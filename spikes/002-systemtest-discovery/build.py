"""Build an ignored, source-pinned research ROM using the upstream toolchain."""
from pathlib import Path
import hashlib
import io
import json
import os
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/n64-systemtest"
REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"
OUTPUT = ROOT / "target/systemtest-spike"


def build():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() != REV:
        raise SystemExit("n64-systemtest differs from pin")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = OUTPUT / "source"
    source.mkdir(exist_ok=True)
    archive = subprocess.check_output(["git", "archive", "--format=tar", REV], cwd=REF)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(source, filter="data")
    # Old Cargo must not inherit Plaid's newer workspace resolver. This only
    # isolates the exported package; guest source and locked dependencies match.
    with (source / "Cargo.toml").open("a") as manifest:
        manifest.write("\n[workspace]\n")
    cargo = Path.home() / ".cargo/bin/cargo.exe" if os.name == "nt" else Path.home() / ".cargo/bin/cargo"
    tool = ROOT / "target/reference-tools/nust64/bin" / ("nust64.exe" if os.name == "nt" else "nust64")
    if not tool.exists():
        raise SystemExit("Install nust64 0.4.1 --locked into target/reference-tools/nust64")
    version = subprocess.check_output([str(tool), "--version"], text=True).strip()
    if "0.4.1" not in version: raise SystemExit("Packager differs from nust64 0.4.1")
    env = dict(os.environ, CARGO_REGISTRIES_CRATES_IO_PROTOCOL="sparse")
    command = [str(cargo), "+nightly-2022-07-10", "build", "--release", "--locked", "-Z", "sparse-registry", "--target-dir", str(OUTPUT / "build")]
    with (OUTPUT / "build.log").open("w") as log:
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print("\n".join((OUTPUT / "build.log").read_text().splitlines()[-35:]))
        raise SystemExit("Pinned homebrew build failed; inspect target/systemtest-spike/build.log")
    elf = OUTPUT / "build/mips-nintendo64-none/release/n64-systemtest"
    rom = OUTPUT / "n64-systemtest.z64"
    for _ in range(2):
        subprocess.run([str(tool), "--elf", str(elf)], cwd=OUTPUT, check=True)
        rom.write_bytes(elf.with_suffix(".z64").read_bytes())
        current = hashlib.sha256(rom.read_bytes()).hexdigest()
        if _ == 0: first = current
        else: assert current == first, "Packaging was not deterministic"
    manifest = {"source_revision":REV, "source_archive_sha256":hashlib.sha256(archive).hexdigest(),
        "rust_toolchain":"nightly-2022-07-10", "nust64_version":version, "cargo_isolation":"[workspace]",
        "packager_sha256":hashlib.sha256(tool.read_bytes()).hexdigest(),
        "elf_sha256":hashlib.sha256(elf.read_bytes()).hexdigest(), "rom_sha256":current,
        "rom_size":rom.stat().st_size}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
