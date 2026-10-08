"""Bounded dummy-plugin reference boot; timeout is not test-suite completion."""
from pathlib import Path
import ctypes as c
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/systemtest-spike"


def worker(mode):
    directory = OUTPUT / mode
    directory.mkdir(exist_ok=True)
    rom = OUTPUT / "n64-systemtest.z64"
    trace = directory / "trace.ndjson"
    os.environ.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
        PLAID_ROM_SHA256=hashlib.sha256(rom.read_bytes()).hexdigest(), PLAID_ROM_SIZE=str(rom.stat().st_size),
        PLAID_TRACE_PATH=str(trace), PLAID_TRACE_EXECUTION="1", PLAID_TRACE_WRITES="1")
    core = c.CDLL(str(ROOT / "target/reference-core/libmupen64plus.so"))
    debug_type = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_char_p)
    state_type = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_int)
    core.CoreStartup.argtypes = [c.c_int,c.c_char_p,c.c_char_p,c.c_void_p,debug_type,c.c_void_p,state_type]
    core.CoreDoCommand.argtypes = [c.c_int,c.c_int,c.c_void_p]
    core.CoreAttachPlugin.argtypes = [c.c_int,c.c_void_p]
    core.ConfigOpenSection.argtypes = [c.c_char_p,c.POINTER(c.c_void_p)]
    core.ConfigSetParameter.argtypes = [c.c_void_p,c.c_char_p,c.c_int,c.c_void_p]
    core.DebugGetCPUDataPtr.argtypes = [c.c_int]
    core.DebugGetCPUDataPtr.restype = c.c_void_p
    logs, errors = [], []
    stopped = threading.Event()
    reason = []

    def stop(why):
        if not stopped.is_set():
            stopped.set()
            reason.append(why)
            code = core.CoreDoCommand(6,0,None)
            if code: errors.append(code)

    @debug_type
    def debug(context, level, message):
        text = message.decode(errors="replace")
        logs.append({"level":level,"message":text})
        with (directory / "live.log").open("a") as log: log.write(f"{level}: {text}\n")
        if text.startswith("IS64:"):
            with (directory / "is64.log").open("a") as log: log.write(text + "\n")
        # A terminal upstream result line, rather than elapsed time, is required
        # to claim the guest finished. Dummy plugins may prevent reaching this.
        if text.startswith("IS64:") and "Done!" in text: stop("guest_done_line")

    @state_type
    def state(context, parameter, value): pass

    def check(code):
        if code: raise RuntimeError(f"Core API {code}; {logs[-4:]}")

    def bound():
        end = time.monotonic() + 5
        while not stopped.wait(0.1):
            if trace.exists() and trace.stat().st_size > 16*1024*1024: stop("trace_byte_budget")
            elif time.monotonic() >= end: stop("wall_time_budget")

    try:
        (directory / "is64.log").write_text("")
        (directory / "live.log").write_text("")
        check(core.CoreStartup(0x020106,os.fsencode(directory),os.fsencode(ROOT / "target/reference-core/data"),None,debug,None,state))
        section = c.c_void_p()
        check(core.ConfigOpenSection(b"Core",c.byref(section)))
        for name, kind, value in [(b"R4300Emulator",1,0 if mode == "pure" else 2),(b"RandomizeInterrupt",3,0),(b"CountPerOp",1,2)]:
            number = c.c_int(value)
            check(core.ConfigSetParameter(section,name,kind,c.byref(number)))
        buffer = c.create_string_buffer(rom.read_bytes())
        check(core.CoreDoCommand(1,rom.stat().st_size,buffer))
        for plugin in (2,3,4,1): check(core.CoreAttachPlugin(plugin,None))
        timer = threading.Thread(target=bound,daemon=True)
        timer.start()
        check(core.CoreDoCommand(5,0,None))
        stopped.set()
        timer.join(timeout=1)
        pc = c.cast(core.DebugGetCPUDataPtr(1),c.POINTER(c.c_uint32)).contents.value
        (directory / "result.json").write_text(json.dumps({"stop_reason":reason,"stop_errors":errors,"pc":pc,
            "guest_completion_claimed":reason == ["guest_done_line"],"plugins":"bundled dummy","wall_budget_seconds":5},indent=2)+"\n")
        check(core.CoreDoCommand(2,0,None))
        check(core.CoreShutdown())
    finally:
        (directory / "core-log.json").write_text(json.dumps(logs,indent=2)+"\n")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker": worker(sys.argv[2]); return
    manifest = json.loads((ROOT / "target/reference-core/build.json").read_text())
    assert manifest["revision"] == "ba95bab92a76744753bfe61470823a4937850ab0"
    for key, path in [("patch", "discovery.patch"),("sink", "trace_sink.h")]:
        assert manifest[key] == hashlib.sha256((ROOT / "instruments/mupen" / path).read_bytes()).hexdigest()
    outcomes = {}
    for mode in ("pure","traced"):
        command = [sys.executable,str(Path(__file__).resolve()),"--worker",mode]
        if os.name == "nt":
            script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
            command = ["wsl","-d","Ubuntu","--exec","python3",script,"--worker",mode]
        process = subprocess.run(command,capture_output=True,text=True,timeout=20)
        directory = OUTPUT / mode
        (directory / "process-output.txt").write_text(process.stdout + process.stderr)
        live = (directory / "live.log").read_text()
        if mode == "pure":
            result = json.loads((directory / "result.json").read_text())
            assert process.returncode == 0 and not result["guest_completion_claimed"], result
            assert "opcode not implemented:" in live and "D0640000" in live
            outcomes[mode] = {"process_exit":0,"outcome":"reference_unimplemented_lld",
                "upstream_failure_messages":live.count("failed:"),"guest_completion_claimed":False}
        else:
            assert process.returncode == 1 and "Compile at bogus memory address: b0001040" in live
            cargo = Path.home() / ".cargo/bin/cargo.exe" if os.name == "nt" else Path.home() / ".cargo/bin/cargo"
            checked = subprocess.run([str(cargo),"run","--quiet","-p","plaid","--","check-trace",str(directory / "trace.ndjson")],cwd=ROOT,capture_output=True,text=True)
            assert checked.returncode != 0 and "missing end record" in checked.stderr
            records = (directory / "trace.ndjson").read_text().splitlines()
            assert not any(json.loads(line)["record"] == "end" for line in records)
            outcomes[mode] = {"process_exit":1,"outcome":"unsupported_cartridge_execution",
                "frontier_pc":0xb0001040,"trace_records":len(records),"trace_bytes":(directory / "trace.ndjson").stat().st_size,
                "trace_import_rejected":True,"guest_completion_claimed":False}
    (OUTPUT / "outcomes.json").write_text(json.dumps(outcomes,indent=2)+"\n")
    print(json.dumps(outcomes,indent=2))


if __name__ == "__main__": main()
