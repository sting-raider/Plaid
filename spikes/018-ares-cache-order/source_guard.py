from pathlib import Path
import subprocess

REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def require_once(text: str, needle: str, path: str) -> int:
    count = text.count(needle)
    assert count == 1, f"{path}: expected exactly one marker, found {count}: {needle!r}"
    return text.index(needle)


def main() -> None:
    root = Path(__file__).resolve().parents[2] / ".refs" / "ares"
    assert root.is_dir(), f"missing pinned checkout: {root}"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert head == REV, (head, REV)
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=root, check=True)

    cpu_hpp_path = "ares/n64/cpu/cpu.hpp"
    cpu_hpp = (root / cpu_hpp_path).read_text()
    fill_bus = require_once(cpu_hpp, "cpu.busReadBurst<ICache>(tag | index, words);", cpu_hpp_path)
    fill_fn = require_once(cpu_hpp, "auto fill(u32 paddr, CPU& cpu) -> void {", cpu_hpp_path)
    write_bus = require_once(cpu_hpp, "cpu.busWriteBurst<ICache>(tag | index, words);", cpu_hpp_path)
    write_fn = require_once(cpu_hpp, "auto writeBack(CPU& cpu) -> void {", cpu_hpp_path)
    assert fill_fn < fill_bus < write_fn < write_bus

    cpu_cpp_path = "ares/n64/cpu/cpu.cpp"
    cpu_cpp = (root / cpu_cpp_path).read_text()
    fetch = require_once(cpu_cpp, "auto data = fetch(access);", cpu_cpp_path)
    prologue = require_once(cpu_cpp, "instructionPrologue(ipu.pc, *data);", cpu_cpp_path)
    assert fetch < prologue

    mem_path = "ares/n64/cpu/memory.cpp"
    mem = (root / mem_path).read_text()
    cached = require_once(mem, "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);", mem_path)
    uncached = require_once(mem, "return busRead<Word>(paddr);", mem_path)
    assert cached < uncached

    ipu_path = "ares/n64/cpu/interpreter-ipu.cpp"
    ipu = (root / ipu_path).read_text()
    op_fill = require_once(ipu, "line.fill(access.paddr, cpu);", ipu_path)
    op_write = require_once(ipu, "line.writeBack(cpu);", ipu_path)
    assert op_fill < op_write

    rdram_path = "ares/n64/rdram/rdram.hpp"
    rdram = (root / rdram_path).read_text()
    ordinary = require_once(rdram, "return Memory::Writable::read<Size>(address);", rdram_path)
    burst = require_once(rdram, "auto readBurst(u32 address, u32 *value, RBusDevice device) -> void {", rdram_path)
    write_burst = require_once(rdram, "auto writeBurst(u32 address, u32 *value, RBusDevice device) -> void {", rdram_path)
    assert ordinary < write_burst < burst

    # Guard the current Plaid sensor boundary too: spike 016 instruments only
    # RDRAM burst reads/writes. It does not instrument Writable::read<Word>.
    plaid = Path(__file__).resolve().parents[2]
    builder = (plaid / "spikes/003-ares-oracle/run.py").read_text()
    assert "plaidRdramBurstObserver(false" in builder
    assert "plaidRdramBurstObserver(true" in builder
    assert "Memory::Writable::read<Size>(address);" not in builder

    print("PASS: pinned ares synchronous ordering markers and current burst-only sensor boundary are unchanged")


if __name__ == "__main__":
    main()
