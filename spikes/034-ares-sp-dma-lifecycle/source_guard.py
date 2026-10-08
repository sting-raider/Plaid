#!/usr/bin/env python3
"""Pin exact SP DMA lifecycle semantics across the three reference sources."""
from pathlib import Path
import hashlib
import json
import sys

ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"


def digest(path):
    # Hash canonical LF source across Windows CRLF checkouts and Linux.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def git_rev(path):
    import subprocess
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def require(text, marker, label):
    if marker not in text:
        raise AssertionError(f"missing {label}: {marker}")


def main(argv):
    if len(argv) != 4:
        raise SystemExit("usage: source_guard.py ARES MUPEN GOPHER")
    ares, mupen, gopher = map(Path, argv[1:])
    assert git_rev(ares) == ARES_REV
    assert git_rev(mupen) == MUPEN_REV
    assert git_rev(gopher) == GOPHER_REV

    a_io_path = ares / "ares/n64/rsp/io.cpp"
    a_dma_path = ares / "ares/n64/rsp/dma.cpp"
    m_path = mupen / "src/device/rcp/rsp/rsp_core.c"
    g_path = gopher / "src/device/rsp_interface.rs"
    # Mupen's lab checkout has unrelated discovery hooks. Preserve those and
    # require only the exact source-oracle files inspected here to be unchanged.
    import subprocess
    for ref, paths in ((ares, [a_io_path, a_dma_path]), (mupen, [m_path]), (gopher, [g_path])):
        subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD", "--",
                        *(str(p.relative_to(ref)) for p in paths)], cwd=ref, check=True)
    a_io, a_dma, m, g = (p.read_text() for p in (a_io_path, a_dma_path, m_path, g_path))

    # ares: address registers always write dma.pending; length commit sets the
    # one pending status pair, and dmaTransferStart only checks current busy.
    require(a_io, "dma.pending.pbusAddress.bit(3,11)", "ares pending PBUS write")
    require(a_io, "dma.pending.dramAddress.bit(3,23)", "ares pending DRAM write")
    require(a_io, "dma.full.read  = 1", "ares read pending flag")
    require(a_io, "dmaTransferStart(thread);", "ares transfer start")
    require(a_dma, "if(dma.busy.any()) return;", "ares busy-only start guard")
    require(a_dma, "dma.current = dma.pending;", "ares pending promotion")
    require(a_dma, "dma.busy    = dma.full;", "ares direction promotion")
    require(a_dma, "dma.full    = {0,0};", "ares full clear on promotion")
    require(a_dma, "dmaTransferStart(*this);", "ares immediate handoff")

    # Mupen/Gopher independently model a two-entry FIFO by copying the register
    # snapshot into fifo[1] and refuse a push while FULL. Their refusal mode
    # differs (warning+return versus panic), but both reject replacement.
    require(m, "if (sp->regs[SP_DMA_FULL_REG])", "mupen full guard")
    require(m, "RSP DMA attempted but FIFO queue already full", "mupen full rejection")
    require(m, "sp->fifo[1].memaddr = sp->regs[SP_MEM_ADDR_REG]", "mupen pending snapshot")
    require(m, "sp->fifo[1].dramaddr = sp->regs[SP_DRAM_ADDR_REG]", "mupen pending dram snapshot")
    require(g, "if device.rsp.regs[SP_DMA_FULL_REG] != 0", "gopher full guard")
    require(g, "panic!(\"RSP DMA already full\")", "gopher full rejection")
    require(g, "device.rsp.fifo[1].memaddr = device.rsp.regs[SP_MEM_ADDR_REG]", "gopher pending snapshot")
    require(g, "device.rsp.fifo[1].dramaddr = device.rsp.regs[SP_DRAM_ADDR_REG]", "gopher pending dram snapshot")

    report = {
        "revisions": {"ares": ARES_REV, "mupen": MUPEN_REV, "gopher": GOPHER_REV},
        "source_sha256": {
            "ares_io": digest(a_io_path), "ares_dma": digest(a_dma_path),
            "mupen_rsp_core": digest(m_path), "gopher_rsp_interface": digest(g_path),
        },
        "semantics": {
            "ares": {
                "pending_descriptor_mutable_after_full": True,
                "third_length_commit_rejected_when_full": False,
                "pending_promoted_immediately_when_current_finishes": True,
            },
            "mupen": {
                "pending_descriptor_snapshotted_on_push": True,
                "third_push_rejected_when_full": True,
            },
            "gopher": {
                "pending_descriptor_snapshotted_on_push": True,
                "third_push_rejected_when_full": True,
            },
        },
        "cross_reference_agreement": False,
    }
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv)
