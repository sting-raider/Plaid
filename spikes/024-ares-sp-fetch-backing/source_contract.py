from dataclasses import dataclass

DMEM_BASE = 0x04000000
IMEM_BASE = 0x04001000
SP_END = 0x0407FFFF


@dataclass(frozen=True)
class Event:
    seq: int
    kind: str
    bank: str | None
    address: int
    value: int | None
    cached: bool | None = None


class Model:
    """Executable source-contract model of the exact pinned ares routing studied here.

    This is deliberately not an emulator. It models only the source-backed routing
    predicates needed to falsify unsafe SP-byte provenance rules.
    """

    def __init__(self):
        self.dmem = bytearray(4096)
        self.imem = bytearray(4096)
        self.events: list[Event] = []
        self.seq = 0
        self.frozen = False

    def emit(self, kind, bank, address, value=None, cached=None):
        self.events.append(Event(self.seq, kind, bank, address, value, cached))
        self.seq += 1

    @staticmethod
    def phys(vaddr):
        lo = vaddr & 0xFFFFFFFF
        if 0x80000000 <= lo <= 0x9FFFFFFF:
            return lo & 0x1FFFFFFF, True
        if 0xA0000000 <= lo <= 0xBFFFFFFF:
            return lo & 0x1FFFFFFF, False
        raise ValueError("only direct 32-bit segments modeled")

    def bank(self, paddr):
        if not (DMEM_BASE <= paddr <= SP_END):
            return None
        return ("imem" if paddr & 0x1000 else "dmem", paddr & 0xFFF)

    def write_word(self, paddr, value, source):
        selected = self.bank(paddr)
        assert selected is not None
        bank, offset = selected
        memory = self.imem if bank == "imem" else self.dmem
        memory[offset : offset + 4] = value.to_bytes(4, "big")
        self.emit(f"{source}_write", bank, paddr, value)

    def read_word(self, paddr):
        selected = self.bank(paddr)
        assert selected is not None
        bank, offset = selected
        memory = self.imem if bank == "imem" else self.dmem
        value = int.from_bytes(memory[offset : offset + 4], "big")
        self.emit("sp_backing_read", bank, paddr, value)
        return value

    def fetch(self, vaddr):
        paddr, cached = self.phys(vaddr)
        if cached:
            # At the pinned ares revision, Bus::readBurst<ICache> accepts N64
            # RDRAM (<= 0x03ffffff), not SP memory. A cached SP fill therefore
            # reaches freezeUncached instead of RSP::read and must not acquire
            # an SP backing witness.
            if paddr > 0x03FFFFFF:
                self.frozen = True
                self.emit("fetch_rejected", None, paddr, None, True)
                return None
            raise AssertionError("RDRAM cached path is outside this contract")

        value = self.read_word(paddr)
        self.emit("fetch", self.bank(paddr)[0], paddr, value, False)
        return value

    def dma_word(self, dram_word, paddr):
        self.write_word(paddr, dram_word, "sp_dma")


def assert_fetch_pairs(events):
    fetches = [event for event in events if event.kind == "fetch"]
    assert fetches
    for fetch in fetches:
        prior = events[fetch.seq - 1]
        assert prior.kind == "sp_backing_read", (prior, fetch)
        assert (prior.bank, prior.address, prior.value) == (
            fetch.bank,
            fetch.address,
            fetch.value,
        )


def main():
    model = Model()

    # Same low offset, deliberately different bank and bytes. Physical-address
    # masking that loses bit 0x1000 is therefore immediately detectable.
    model.write_word(0x04000040, 0x24010001, "setup")
    model.write_word(0x04001040, 0x24020002, "setup")
    model.events.clear()
    model.seq = 0
    assert model.fetch(0xFFFFFFFFA4000040) == 0x24010001
    assert model.fetch(0xFFFFFFFFA4001040) == 0x24020002
    assert_fetch_pairs(model.events)
    assert [event.bank for event in model.events if event.kind == "fetch"] == [
        "dmem",
        "imem",
    ]

    # Successful CPU mutation is a lineage boundary for the next fetch.
    model.events.clear()
    model.seq = 0
    assert model.fetch(0xFFFFFFFFA4000040) == 0x24010001
    model.write_word(0x04000040, 0x24010007, "cpu")
    assert model.fetch(0xFFFFFFFFA4000040) == 0x24010007
    assert_fetch_pairs(model.events)
    assert [event.value for event in model.events if event.kind == "fetch"] == [
        0x24010001,
        0x24010007,
    ]
    assert any(
        event.kind == "cpu_write" and event.address == 0x04000040
        for event in model.events
    )

    # SP DMA mutation independently changes IMEM backing.
    model.events.clear()
    model.seq = 0
    assert model.fetch(0xFFFFFFFFA4001040) == 0x24020002
    model.dma_word(0x24020009, 0x04001040)
    assert model.fetch(0xFFFFFFFFA4001040) == 0x24020009
    assert_fetch_pairs(model.events)
    assert any(
        event.kind == "sp_dma_write" and event.bank == "imem"
        for event in model.events
    )

    # A neighboring successful write is not a mutation of the fetched word.
    model.events.clear()
    model.seq = 0
    model.write_word(0x04000044, 0xDEADBEEF, "cpu")
    assert model.fetch(0xFFFFFFFFA4000040) == 0x24010007
    assert_fetch_pairs(model.events)

    # Cached alias is the adversarial counterexample: under this pinned ares
    # path it cannot be assigned an SP backing witness at all.
    model.events.clear()
    model.seq = 0
    model.frozen = False
    assert model.fetch(0xFFFFFFFF84000040) is None
    assert model.frozen
    assert [event.kind for event in model.events] == ["fetch_rejected"]
    assert not any(event.kind == "sp_backing_read" for event in model.events)

    print(
        "PASS: SP source-contract chronology: DMEM/IMEM distinct; "
        "CPU/DMA writes bound generations; cached SP fetch has no backing witness"
    )


if __name__ == "__main__":
    main()
