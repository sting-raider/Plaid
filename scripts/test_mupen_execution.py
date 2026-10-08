"""Execute synthetic MIPS on pinned Mupen x64 dynarec and pure interpreter.

Linux needs GCC and NASM. Windows launches the Linux worker through WSL Ubuntu;
Rust artifact checks run on the calling host. No emulator frontend or game ROM.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".refs/mupen64plus-core"


def worker(directory):
    directory = Path(directory)
    cc = os.environ.get("CC", "gcc")
    nasm = os.environ.get("PLAID_NASM") or shutil.which("nasm")
    if not nasm:
        candidate = ROOT / "target/reference-tools/nasm-root/usr/bin/nasm"
        if candidate.exists(): nasm = str(candidate)
    if not nasm: raise SystemExit("NASM required (set PLAID_NASM)")
    flags = ["-std=gnu99", "-O1", "-ffunction-sections", "-fdata-sections", "-fno-pie", "-DNEW_DYNAREC=NEW_DYNAREC_X64", "-DDYNAREC", "-I", str(REF / "src"), "-I", str(REF / "subprojects/md5"), "-I", str(REF / "subprojects/xxhash")]
    definitions = directory / "definitions.o"
    subprocess.run([cc, *flags, "-c", str(REF / "src/asm_defines/asm_defines.c"), "-o", str(definitions)], check=True)
    offsets = re.findall(rb"@ASM_DEFINE (offsetof_struct_\w+) (0x[0-9a-fA-F]+)", definitions.read_bytes())
    assert offsets
    (directory / "asm_defines_nasm.h").write_text("".join(f"%define {name.decode()} ({value.decode()})\n" for name, value in sorted(offsets)))
    linkage = directory / "linkage.o"
    subprocess.run([nasm, "-f", "elf64", "-I", str(directory) + "/", str(REF / "src/device/r4300/new_dynarec/x64/linkage_x64.asm"), "-o", str(linkage)], check=True)
    sources = [ROOT / "instruments/mupen/execution_driver.c", ROOT / "instruments/mupen/execution_traps.c"]
    sources += [REF / "src" / path for path in ["device/r4300/new_dynarec/new_dynarec.c", "device/cart/cart_rom.c", "device/r4300/r4300_core.c", "device/r4300/pure_interp.c", "device/r4300/cp0.c", "device/r4300/cp1.c", "device/r4300/cp2.c", "device/r4300/tlb.c"]]
    exe = directory / "execute"
    subprocess.run([cc, *flags, *map(str, sources), str(linkage), "-no-pie", "-Wl,--gc-sections", "-lm", "-o", str(exe)], check=True)
    for scenario in ("jalr", "jal"):
        rom = directory / f"{scenario}.z64"
        env = dict(os.environ, PLAID_ROM_SHA256=hashlib.sha256(rom.read_bytes()).hexdigest(), PLAID_ROM_SIZE="4096")
        results = {}
        for mode in ("pure", "untraced", "traced", "repeat"):
            trace = directory / f"{scenario}-{mode}.ndjson"
            run_env = dict(env, PLAID_TRACE_PATH=str(trace), PLAID_TRACE_EXECUTION="1" if mode in ("traced", "repeat") else "0")
            results[mode] = json.loads(subprocess.check_output([str(exe), "pure" if mode == "pure" else "dynarec", str(rom)], env=run_env, timeout=15, text=True))
        (directory / f"{scenario}-states.json").write_text(json.dumps(results, indent=2))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(sys.argv[2]); return
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_mupen.py")], check=True)
    (ROOT / "target").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mupen-execution-", dir=ROOT / "target") as temporary:
        directory = Path(temporary)
        for scenario in ("jalr", "jal"):
            data = bytearray(4096)
            data[:4] = bytes.fromhex("80371240")
            words = {0:0x3c088000, 4:0x35080040, 8:0x0100f809 if scenario == "jalr" else 0x0c000010,
                0xc:0x24100005, 0x10:0x26310001, 0x14:0x162afffc, 0x18:0,
                0x1c:0x3c088000, 0x20:0x35080100, 0x24:0x01000008, 0x28:0x35080001,
                0x40:0x26520007, 0x44:0x03e00008, 0x48:0x26730002, 0x100:0x08000040, 0x104:0}
            for offset, word in words.items(): data[64+offset:68+offset] = word.to_bytes(4, "big")
            (directory / f"{scenario}.z64").write_bytes(data)
        if os.name == "nt":
            def linux_path(path):
                return subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", path.as_posix()], text=True).strip()
            subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", linux_path(Path(__file__).resolve()), "--worker", linux_path(directory)], check=True, timeout=120)
        else: worker(directory)
        cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
        for scenario in ("jalr", "jal"):
            states = json.loads((directory / f"{scenario}-states.json").read_text())
            assert all(state == states["pure"] for state in states.values()), states
            state = states["pure"]
            assert state["pc"] == 0x80000100 and state["regs"][16:20] == [5, 3, 21, 6], state
            assert state["regs"][8] == -2147483391 and state["regs"][31] == -2147483632, state
            first = (directory / f"{scenario}-traced.ndjson").read_bytes()
            assert first == (directory / f"{scenario}-repeat.ndjson").read_bytes()
            records = [json.loads(line) for line in first.splitlines()]
            events = [record["data"] for record in records[1:-1]]
            indirect = [event for event in events if event["event"] == "indirect_target_observed"]
            assert sum(event["site"] == 0x80000044 and event["target"] == 0x80000010 for event in indirect) == 3
            assert sum(event["site"] == 0x80000008 and event["target"] == 0x80000040 for event in indirect) == (3 if scenario == "jalr" else 0)
            return_lookups = [event for event in events if event["event"] == "target_lookup" and event["target"] == 0x80000010]
            if scenario == "jal":
                assert not return_lookups, "three returns must exercise the inline mini_ht hit path"
            else:
                assert len(return_lookups) >= 3, "JALR returns exercise the general lookup path"
            assert indirect[-1] == {"event":"indirect_target_observed", "site":0x80000024, "target":0x80000100, "delay_slot_pc":0x80000028}
            untraced = (directory / f"{scenario}-untraced.ndjson").read_text()
            assert "indirect_target_observed" not in untraced
            trace = directory / f"{scenario}-traced.ndjson"
            subprocess.run([cargo, "run", "--quiet", "-p", "plaid", "--", "check-trace", str(trace)], cwd=ROOT, check=True)
            output = directory / f"{scenario}-map.json"
            subprocess.run([cargo, "run", "--quiet", "-p", "plaid", "--", "import-trace", str(directory / f"{scenario}.z64"), str(trace), str(output)], cwd=ROOT, check=True)
            imported = json.loads(output.read_text())
            assert sum(len(o["evidence"]) for o in imported["indirect_observations"]) == len(indirect)
            assert any(site["observed"] for site in imported["indirect_sites"]), "runtime target identities must be correlated"
            assert all(site["closed_proof"] is None for site in imported["indirect_sites"]), "execution samples cannot prove closure"
        print("Pinned CPUs agree: traced/untraced x64 dynarec and pure interpreter; repeated JR/JALR targets and delay-slot operand preservation verified")


if __name__ == "__main__": main()
