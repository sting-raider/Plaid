#!/usr/bin/env python3
"""Guard the exact reset/NMI source contracts used by this experiment."""
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "mupen64plus-core": "ba95bab92a76744753bfe61470823a4937850ab0",
    "gopher64": "e96debac941a26ba4961e5145056c0821d3a56f7",
}


def text(repo: str, rel: str) -> str:
    base = ROOT / ".refs" / repo
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=base, text=True).strip()
    assert head == PINS[repo], (repo, head)
    return (base / rel).read_text()


def function(src: str, signature: str, next_marker: str) -> str:
    start = src.index(signature)
    end = src.index(next_marker, start + len(signature))
    return src[start:end]


# ares: soft System::power(true) reaches RSP::power(reset), whose implementation
# ignores the reset flag for RSP storage/state and clears both IMEM and DMA state.
ares_rsp = text("ares", "ares/n64/rsp/rsp.cpp")
ares_system = text("ares", "ares/n64/system/system.cpp")
ares_cpu = text("ares", "ares/n64/cpu/cpu.cpp")
ares_exc = text("ares", "ares/n64/cpu/exceptions.cpp")
rsp_power = function(ares_rsp, "auto RSP::power(bool reset) -> void {", "\n}\n\n}")
for needle in ("dmem.fill();", "imem.fill();", "dma = {};", "ipu.pc = 0;", "status.halted = 1;"):
    assert needle in rsp_power, needle
assert "rsp.power(reset);" in ares_system
assert "if (scc.nmiPending)" in ares_cpu and "exception.nmi();" in ares_cpu
nmi = function(ares_exc, "auto CPU::Exception::nmi() -> void {", "\n}\n")
assert "rsp." not in nmi and "system.power" not in nmi

# Mupen: soft reset schedules HW2+NMI; NMI does CPU/PIF work only. Hard reset
# calls poweron_device, which reaches poweron_rsp and zeroes the entire SP memory.
mupen_device = text("mupen64plus-core", "src/device/device.c")
mupen_irq = text("mupen64plus-core", "src/device/r4300/interrupt.c")
mupen_rsp = text("mupen64plus-core", "src/device/rcp/rsp/rsp_core.c")
soft = function(mupen_device, "void soft_reset_device(struct device* dev)", "\n}")
assert "HW2_INT" in soft and "NMI_INT" in soft and "poweron_rsp" not in soft
mupen_nmi = function(mupen_irq, "void nmi_int_handler(void* opaque)", "\n}\n\n\n/* XXX: needs")
assert "poweron_rsp" not in mupen_nmi and "sp->mem" not in mupen_nmi and "dev->sp.mem" not in mupen_nmi
hard = function(mupen_irq, "void reset_hard_handler(void* opaque)", "\n}\n\n\nstatic void call_interrupt_handler")
assert "poweron_device(dev);" in hard
assert "poweron_rsp(&dev->sp);" in mupen_device
poweron_rsp = function(mupen_rsp, "void poweron_rsp(struct rsp_core* sp)", "\n}")
assert "memset(sp->mem, 0, SP_MEM_SIZE);" in poweron_rsp

# Gopher64: reset_event resets CPU state and SP PC, but has no SP-memory sink.
gopher_exc = text("gopher64", "src/device/exceptions.rs")
gopher_reset = function(gopher_exc, "pub fn reset_event(device: &mut device::Device) {", "\n}\n\nfn exception_general")
assert "SP_PC_REG] = 0" in gopher_reset
assert "rsp.mem" not in gopher_reset and "rsp_interface::write_mem" not in gopher_reset

files = {
    "ares_rsp": ares_rsp,
    "ares_system": ares_system,
    "ares_cpu": ares_cpu,
    "ares_exceptions": ares_exc,
    "mupen_device": mupen_device,
    "mupen_interrupt": mupen_irq,
    "mupen_rsp": mupen_rsp,
    "gopher_exceptions": gopher_exc,
}
for name, src in files.items():
    print(f"{name}_sha256={hashlib.sha256(src.encode()).hexdigest()}")
print("SOURCE_GUARD_PASS")
