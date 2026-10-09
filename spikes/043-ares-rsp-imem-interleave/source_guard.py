#!/usr/bin/env python3
"""Guard the exact pinned ares source contracts used by this experiment."""
import hashlib
import json
import sys
from pathlib import Path

EXPECTED = {
    "ares/n64/rsp/dma.cpp": "b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6",
    "ares/n64/rsp/io.cpp": "60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860",
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: source_guard.py <ares-checkout>")
    root = Path(sys.argv[1])
    observed = {}
    for rel, expected in EXPECTED.items():
        data = (root / rel).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == expected, (rel, digest, expected)
        observed[rel] = digest

    dma = (root / "ares/n64/rsp/dma.cpp").read_text()
    io = (root / "ares/n64/rsp/io.cpp").read_text()
    required_dma = [
        "auto RSP::dmaTransferStep() -> void",
        "for(u32 i = 0; i <= dma.current.length; i += 8)",
        "imem.write<Dual>(dma.current.pbusAddress, data);",
        "if(dma.current.count)",
        "dma.current.count -= 1;",
        "dmaQueue((dma.current.length+8) / 8 * 3, *this);",
    ]
    required_io = [
        "auto RSP::writeWord(u32 address, u32 data, Thread& thread) -> void",
        "imem.write<Word>(address, data)",
        "dma.pending.count            = data.bit(12,19);",
    ]
    for needle in required_dma:
        assert needle in dma, needle
    for needle in required_io:
        assert needle in io, needle

    print(json.dumps({
        "revision": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
        "sha256": observed,
        "contracts": {
            "one_count_row_per_dmaTransferStep": True,
            "count_reschedules_and_returns": True,
            "direct_imem_word_write_is_independent_sink": True,
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
