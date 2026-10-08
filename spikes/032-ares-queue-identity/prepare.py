"""Generate an opt-in queue observer; upstream implementation stays ignored."""
from pathlib import Path


def generate(reference: Path, destination: Path):
    source = (reference / "nall/nall/priority-queue.hpp").read_text()
    def replace(marker, replacement):
        nonlocal source
        assert source.count(marker) == 1, marker
        source = source.replace(marker, replacement)

    replace("namespace nall {", """namespace nall {
// Original optional callback; metadata lives outside the queue object.
// kind, owner, destination slot, source slot, event type, clock, validity.
using PlaidQueueObserver = void (*)(u32, const void*, u32, u32, u32, u32, bool);
inline PlaidQueueObserver plaidQueueObserver = nullptr;
""")
    replace("    clock = 0;\n    size = 0;",
            "    if(plaidQueueObserver) plaidQueueObserver(1, this, 0, 0, 0, clock, false);\n    clock = 0;\n    size = 0;")
    replace("    if(size >= Size) return false;", """    if(size >= Size) {
      if(plaidQueueObserver) plaidQueueObserver(2, this, size, 0, (u32)event, clock, false);
      return false;
    }""")
    replace("      heap[child].valid = heap[parent].valid;",
            "      heap[child].valid = heap[parent].valid;\n      if(plaidQueueObserver) plaidQueueObserver(3, this, child, parent, (u32)heap[child].event, heap[child].clock, heap[child].valid);")
    replace("    heap[child].valid = true;", "    heap[child].valid = true;\n    if(plaidQueueObserver) plaidQueueObserver(4, this, child, 0, (u32)event, clock, true);")
    replace("    bool valid = heap[0].valid;", "    bool valid = heap[0].valid;\n    if(plaidQueueObserver) plaidQueueObserver(5, this, 0, size-1, (u32)event, heap[0].clock, valid);")
    replace("      heap[parent].valid = heap[child].valid;",
            "      heap[parent].valid = heap[child].valid;\n      if(plaidQueueObserver) plaidQueueObserver(6, this, parent, child, (u32)heap[parent].event, heap[parent].clock, heap[parent].valid);")
    replace("    heap[parent].valid = heap[size].valid;",
            "    heap[parent].valid = heap[size].valid;\n    if(plaidQueueObserver) plaidQueueObserver(7, this, parent, size, (u32)heap[parent].event, heap[parent].clock, heap[parent].valid);")
    replace("        heap[i].valid = false;", "        if(plaidQueueObserver) plaidQueueObserver(8, this, i, 0, (u32)event, heap[i].clock, heap[i].valid);\n        heap[i].valid = false;")
    replace("    s(clock);", "    if(plaidQueueObserver) plaidQueueObserver(9, this, 0, 0, 0, clock, s.reading());\n    s(clock);")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source)


if __name__ == "__main__":
    import sys
    generate(Path(sys.argv[1]), Path(sys.argv[2]))
