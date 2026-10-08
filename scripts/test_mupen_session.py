"""Run a hand-authored ROM through pinned core boot, PI DMA and MMIO.

The reference core uses bundled dummy plugins. This checks CPU/device integration,
not graphics, RSP execution or commercial boot compatibility. Generated ROMs and
logs remain under ignored target/. Linux requires build_mupen_core.py dependencies;
Windows dispatches through WSL Ubuntu. Each engine runs in a fresh process.
"""
from pathlib import Path
import ctypes as c
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "target/reference-core"
SESSION = ROOT / "target/mupen-session"
MODES = ("pure", "untraced", "traced", "repeat")
SCENARIOS = ("pi", "reload", "reload_alias")


def fixture(scenario="pi"):
    data = bytearray(8192)
    data[:4] = bytes.fromhex("80371240")
    data[8:12] = (0x80000400).to_bytes(4, "big")
    data[0x20:0x34] = b"PLAID SYNTHETIC TEST"
    data[0x3e] = ord("E")
    # Original IPL3 fixture, entered by the pinned core's PIF HLE at A4000040.
    # PI cartridge -> DRAM: ROM 1000, RAM 400, 256 bytes. Poll the real busy bit.
    boot = [0x3c08a460, 0x34090400, 0xad090000, 0x3c091000, 0x35291000,
            0xad090004, 0x340900ff, 0xad09000c, 0x8d090010, 0x31290003,
            0x1520fffd, 0, 0x3c088000, 0x35080400, 0x01000008, 0]
    # JALR -> subroutine -> JR, then verify an ordinary RAM store with a load.
    body = {0:0x3c088000, 4:0x350804c0, 8:0x0100f809, 0xc:0x24100005,
            0x10:0x3c0d8000, 0x14:0xadb10600, 0x18:0x8dae0600,
            0x1c:0x3c08b3ff, 0x20:0x3c09504c, 0x24:0x35294149, 0x28:0xad090020,
            0x2c:0x3c09445f, 0x30:0x35294f4b, 0x34:0xad090024,
            0x38:0x3c090a00, 0x3c:0xad090028, 0x40:0x34090009,
            0x44:0xad090014, 0x48:0x08000112, 0x4c:0,
            0xc0:0x26110007, 0xc4:0x03e00008, 0xc8:0x24120009}
    if scenario != "pi":
        assert scenario in ("reload", "reload_alias")
        first = dict(body)
        first[0x1c] = 0x26730001  # First payload increments s3, then returns to SP.
        first[0x20] = 0x02e00008  # JR s7 (bootstrap's custom link).
        first[0x24] = 0
        first = {offset:word for offset,word in first.items() if offset <= 0x24 or offset >= 0xc0}
        for offset, word in first.items(): data[0x1000+offset:0x1004+offset] = word.to_bytes(4, "big")
        second_dma = list(boot[:12])
        second_dma[4] = 0x35291100
        alias = scenario == "reload_alias"
        boot = boot[:14] + [0x0100b809, 0] + second_dma + [0x3c08a000 if alias else 0x3c088000, 0x35080400, 0x01000008, 0]
        body[0] = 0x3c08a000 if alias else 0x3c088000
        body[0xc] = 0x2410000b
        body[0xc8] = 0x2412000d
        body[0x48] = 0x08000112  # J preserves the current cached/uncached region.
    for n, word in enumerate(boot): data[64+n*4:68+n*4] = word.to_bytes(4, "big")
    payload_offset = 0x1000 if scenario == "pi" else 0x1100
    for offset, word in body.items(): data[payload_offset+offset:payload_offset+offset+4] = word.to_bytes(4, "big")
    return data


def worker(directory, mode):
    directory = Path(directory)
    config = directory / mode
    config.mkdir(exist_ok=True)
    rom = directory / "synthetic.z64"
    trace = directory / f"{mode}.ndjson"
    os.environ.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
        PLAID_ROM_SHA256=hashlib.sha256(rom.read_bytes()).hexdigest(),
        PLAID_ROM_SIZE=str(rom.stat().st_size), PLAID_TRACE_PATH=str(trace),
        PLAID_TRACE_EXECUTION="1" if mode in ("traced", "repeat") else "0")
    core = c.CDLL(str(OUTPUT / "libmupen64plus.so"))
    debug_type = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_char_p)
    state_type = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_int)
    core.CoreStartup.argtypes = [c.c_int, c.c_char_p, c.c_char_p, c.c_void_p, debug_type, c.c_void_p, state_type]
    core.CoreStartup.restype = c.c_int
    core.CoreDoCommand.argtypes = [c.c_int, c.c_int, c.c_void_p]
    core.CoreDoCommand.restype = c.c_int
    core.CoreAttachPlugin.argtypes = [c.c_int, c.c_void_p]
    core.CoreAttachPlugin.restype = c.c_int
    core.ConfigOpenSection.argtypes = [c.c_char_p, c.POINTER(c.c_void_p)]
    core.ConfigOpenSection.restype = c.c_int
    core.ConfigSetParameter.argtypes = [c.c_void_p, c.c_char_p, c.c_int, c.c_void_p]
    core.ConfigSetParameter.restype = c.c_int
    core.DebugGetCPUDataPtr.argtypes = [c.c_int]
    core.DebugGetCPUDataPtr.restype = c.c_void_p
    logs, callback_errors = [], []
    marker_seen = False
    (directory / f"{mode}-live.log").write_text("")

    @debug_type
    def debug(context, level, message):
        nonlocal marker_seen
        text = message.decode("utf-8", errors="replace")
        logs.append({"level":level, "message":text})
        with (directory / f"{mode}-live.log").open("a") as output:
            output.write(f"{level}: {text}\n")
        if text == "IS64: PLAID_OK" and not marker_seen:
            marker_seen = True
            result = core.CoreDoCommand(6, 0, None)  # Frontend stop request.
            if result: callback_errors.append(result)

    @state_type
    def state(context, parameter, value):
        pass

    def check(result):
        if result: raise RuntimeError(f"Core API error {result}; logs: {logs[-6:]}")

    try:
        check(core.CoreStartup(0x020106, os.fsencode(config), os.fsencode(OUTPUT / "data"), None, debug, None, state))
        section = c.c_void_p()
        check(core.ConfigOpenSection(b"Core", c.byref(section)))
        for name, kind, value in [(b"R4300Emulator", 1, 0 if mode == "pure" else 2),
                                  (b"RandomizeInterrupt", 3, 0), (b"CountPerOp", 1, 2)]:
            number = c.c_int(value)
            check(core.ConfigSetParameter(section, name, kind, c.byref(number)))
        buffer = c.create_string_buffer(rom.read_bytes())
        check(core.CoreDoCommand(1, rom.stat().st_size, buffer))
        # Explicitly attach/start each bundled dummy plugin, including RSP.
        # The pinned startup connects CORE rather than RSP; an uninitialized
        # RSP callback table crashes during normal teardown without this step.
        for plugin in (2, 3, 4, 1): check(core.CoreAttachPlugin(plugin, None))
        check(core.CoreDoCommand(5, 0, None))
        if not marker_seen or callback_errors: raise RuntimeError(f"Missing marker or stop failure: {callback_errors}")

        def read_cpu(kind, array_type):
            pointer = core.DebugGetCPUDataPtr(kind)
            if not pointer: raise RuntimeError("Reference CPU state unavailable")
            return list(c.cast(pointer, c.POINTER(array_type)).contents)

        result = {"regs":read_cpu(2, c.c_int64*32), "hi":read_cpu(3, c.c_int64*1)[0],
                  "lo":read_cpu(4, c.c_int64*1)[0], "pc":read_cpu(1, c.c_uint32*1)[0]}
        (directory / f"{mode}-state.json").write_text(json.dumps(result, indent=2) + "\n")
        check(core.CoreDoCommand(2, 0, None))
        check(core.CoreShutdown())
    finally:
        (directory / f"{mode}-log.json").write_text(json.dumps(logs, indent=2) + "\n")


def verify(directory, scenario, cargo):
    base = 0xa0000400 if scenario == "reload_alias" else 0x80000400
    states = {mode:json.loads((directory / f"{mode}-state.json").read_text()) for mode in MODES}
    for mode, state in states.items():
        assert state["regs"][14] == (12 if scenario == "pi" else 18), (mode, state)
        assert state["regs"][16:20] == ([5,12,9,0] if scenario == "pi" else [11,18,13,1]), (mode, state)
        assert state["pc"] == base + 0x48, (mode, state)
        assert state == states["pure"], states
    first = (directory / "traced.ndjson").read_bytes()
    assert first == (directory / "repeat.ndjson").read_bytes(), "Trace differs on repeated device session"
    events = [json.loads(line)["data"] for line in first.splitlines()[1:-1]]
    dma = [e for e in events if e["event"] == "rom_dma_observed"]
    assert [e["rom_offset"] for e in dma] == ([0x1000] if scenario == "pi" else [0x1000,0x1100]), dma
    assert all(e["physical_destination"] == 0x400 and e["size"] == 256 for e in dma), dma
    indirect = [e for e in events if e["event"] == "indirect_target_observed"]
    assert any(e["site"] == base+8 and e["target"] == base+0xc0 for e in indirect), indirect
    assert any(e["site"] == base+0xc4 and e["target"] == base+0x10 for e in indirect), indirect
    assert "indirect_target_observed" not in (directory / "untraced.ndjson").read_text()
    for args in [("check-trace", str(directory / "traced.ndjson")),
                 ("import-trace", str(directory / "synthetic.z64"), str(directory / "traced.ndjson"), str(directory / "map.json"))]:
        subprocess.run([cargo, "run", "--quiet", "-p", "plaid", "--", *args], cwd=ROOT, check=True)
    report = subprocess.check_output([cargo, "run", "--quiet", "-p", "plaid", "--", "solve",
        str(directory / "synthetic.z64"), str(directory / "map.json")], cwd=ROOT, text=True)
    (directory / "solver.json").write_text(report)
    solved = json.loads(report)
    assert solved["status"] == "open" and not solved["native_complete"]
    assert not any(b["kind"] == "indirect_evidence_disagreement" for b in solved["blockers"])
    imported = json.loads((directory / "map.json").read_text())
    offset = 0x1000 if scenario == "pi" else 0x1100
    assert any(load["rom_offset"] == offset and load["destination"]["start"] == base for load in imported["loads"])
    assert any(load["rom_offset"] == offset+0xc0 and load["destination"]["start"] == base+0xc0 for load in imported["loads"])
    assert sum(len(o["evidence"]) for o in imported["indirect_observations"]) == len(indirect)
    assert any(site["observed"] for site in imported["indirect_sites"])
    assert all(site["closed_proof"] is None for site in imported["indirect_sites"])
    assert all(target[0]["generation"] == site["site"]["generation"]
        for site in imported["indirect_sites"] for target in site["observed"])
    if scenario != "pi":
        earlier = [load for load in imported["loads"] if load["rom_offset"] == 0x1000]
        later = [load for load in imported["loads"] if load["rom_offset"] == 0x1100]
        assert min(load["generation"] for load in later) > max(load["generation"] for load in earlier)
        assert imported["overlays"] and all(o["candidate"] for o in imported["overlays"].values())
    print(f"Pinned full-core {scenario} passes: PI DMA, RAM store/load, JR/JALR and IS64 stop; deterministic {len(events)}-event trace")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3]); return
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_mupen.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_mupen_core.py")], check=True)
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    for scenario in SCENARIOS:
        directory = SESSION / scenario
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "synthetic.z64").write_bytes(fixture(scenario))
        for mode in MODES:
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(directory), mode]
            if os.name == "nt":
                def linux_path(path):
                    return subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", path.as_posix()], text=True).strip()
                command = ["wsl", "-d", "Ubuntu", "--exec", "python3", linux_path(Path(__file__).resolve()), "--worker", linux_path(directory), mode]
            subprocess.run(command, check=True, timeout=30)
        verify(directory, scenario, cargo)


if __name__ == "__main__": main()
