from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Union

Words = Tuple[int, ...]


def _words(values: Sequence[int]) -> Words:
    result = tuple(int(v) & 0xFFFFFFFF for v in values)
    if len(result) != 8:
        raise ValueError("I-cache lineage requires exactly eight 32-bit words")
    return result


@dataclass(frozen=True)
class RdramRead:
    address: int
    words: Words
    identity_mapped: bool = True
    icache_requestor: bool = True
    bytes: int = 32


@dataclass(frozen=True)
class RdramWrite:
    address: int
    words: Words
    identity_mapped: bool = True
    icache_requestor: bool = True
    bytes: int = 32


@dataclass(frozen=True)
class Fill:
    slot: int
    physical: int
    index: int
    words: Words


@dataclass(frozen=True)
class CacheOp:
    slot: int
    after_tag: int
    after_words: Words
    operation: int


@dataclass(frozen=True)
class Fetch:
    slot: int
    physical: int
    tag_key: int
    line_words: Words
    lane: int
    word: int
    cached: bool = True


@dataclass(frozen=True)
class ResetOrRestore:
    reason: str


@dataclass(frozen=True)
class Other:
    label: str


Event = Union[RdramRead, RdramWrite, Fill, CacheOp, Fetch, ResetOrRestore, Other]


@dataclass(frozen=True)
class FillWitness:
    witness_id: int
    burst_ordinal: int
    fill_ordinal: int
    slot: int
    physical: int
    index: int
    tag_key: int
    words: Words


@dataclass(frozen=True)
class FetchResult:
    ordinal: int
    origin_witness_id: Optional[int]
    reason: str


class Joiner:
    """Fail-closed model for a bounded ares I-cache/RDRAM chronology.

    The model intentionally treats observer order as evidence only for the exact
    synchronous source path documented by spike 018. A fill receives a backing
    witness only when the immediately preceding observer event is a successful
    identity-mapped 32-byte I-cache RDRAM read with the exact expected address and
    returned words. Resident lineage survives only while the selected cache-line
    tuple remains byte/tag-identical to the witnessed fill.
    """

    def __init__(self) -> None:
        self.ordinal = 0
        self.last_event: Optional[tuple[int, Event]] = None
        self.next_witness_id = 1
        self.resident: dict[int, Optional[FillWitness]] = {}
        self.witnesses: list[FillWitness] = []
        self.fetches: list[FetchResult] = []
        self.rejected_fills: list[tuple[int, str]] = []

    @staticmethod
    def _expected_burst(fill: Fill) -> int:
        return (fill.physical & ~0xFFF) | fill.index

    @staticmethod
    def _fill_tag(fill: Fill) -> int:
        return (fill.physical & ~0xFFF) | 1

    @staticmethod
    def _eligible_read(read: RdramRead) -> bool:
        return (
            read.identity_mapped
            and read.icache_requestor
            and read.bytes == 32
            and len(read.words) == 8
        )

    def push(self, event: Event) -> None:
        self.ordinal += 1
        ordinal = self.ordinal

        if isinstance(event, Fill):
            witness: Optional[FillWitness] = None
            reason = "no immediately preceding successful identity I-cache RDRAM read"
            if self.last_event and isinstance(self.last_event[1], RdramRead):
                burst_ordinal, read = self.last_event
                if not self._eligible_read(read):
                    reason = "preceding RDRAM read is outside identity-mapped I-cache scope"
                elif read.address != self._expected_burst(event):
                    reason = "preceding RDRAM read address does not match fill burst address"
                elif read.words != event.words:
                    reason = "preceding RDRAM read payload does not match completed fill"
                else:
                    witness = FillWitness(
                        witness_id=self.next_witness_id,
                        burst_ordinal=burst_ordinal,
                        fill_ordinal=ordinal,
                        slot=event.slot,
                        physical=event.physical,
                        index=event.index,
                        tag_key=self._fill_tag(event),
                        words=event.words,
                    )
                    self.next_witness_id += 1
                    self.witnesses.append(witness)
            self.resident[event.slot] = witness
            if witness is None:
                self.rejected_fills.append((ordinal, reason))

        elif isinstance(event, CacheOp):
            current = self.resident.get(event.slot)
            if not (
                current is not None
                and current.tag_key == event.after_tag
                and current.words == event.after_words
            ):
                # This catches store-tag, invalidation, or any other mutation that
                # changes the selected resident tuple without a witnessed refill.
                self.resident[event.slot] = None

        elif isinstance(event, ResetOrRestore):
            # A restored cache snapshot is not a fill. A separate restore witness
            # would be required before lineage can resume.
            self.resident.clear()

        elif isinstance(event, Fetch):
            origin: Optional[int] = None
            reason = "uncached fetch"
            if event.cached:
                current = self.resident.get(event.slot)
                if current is None:
                    reason = "no live witnessed fill for selected slot"
                elif current.tag_key != event.tag_key:
                    reason = "selected tag differs from witnessed fill"
                elif current.words != event.line_words:
                    reason = "resident words differ from witnessed fill"
                elif not (0 <= event.lane < 8):
                    reason = "invalid fetched lane"
                elif event.line_words[event.lane] != (event.word & 0xFFFFFFFF):
                    reason = "fetched word differs from resident lane"
                elif (event.physical & ~0xFFF) != (current.physical & ~0xFFF):
                    reason = "fetch physical page differs from witnessed fill"
                else:
                    origin = current.witness_id
                    reason = "resident tuple matches witnessed fill"
            self.fetches.append(FetchResult(ordinal, origin, reason))

        # RDRAM writes deliberately do not invalidate resident I-cache lineage.
        # They mutate backing memory, not the already-resident cache words.
        self.last_event = (ordinal, event)


def controlled_sequence() -> tuple[list[Event], list[Optional[int]]]:
    """Model the spike-015/016 controlled sequence relevant to resident lineage.

    The four successful fill bursts are 0, 0x4000, 0, 0x4000.  The expected
    origin ids for cached fetches demonstrate both stale-tag counterexamples and
    lineage preservation across backing mutation/writeback.
    """
    page0 = _words((0x24100001, 0, 0, 0, 0, 0, 0, 0))
    page4 = _words((0x24100009, 0, 0, 0, 0, 0, 0, 0))
    events: list[Event] = [
        # Initial cached miss -> RDRAM read -> fill -> fetched instruction.
        RdramRead(0x0000, page0),
        Fill(0, 0x0000, 0, page0),
        Fetch(0, 0x0000, 0x0001, page0, 0, 0x24100001),
        # CACHE store-tag retags old page-0 bytes as page 0x4000 without a fill.
        CacheOp(0, 0x4001, page0, 0x08),
        Fetch(0, 0x4000, 0x4001, page0, 0, 0x24100001),
        # Index invalidate then real refill from page 0x4000.
        CacheOp(0, 0x4000, page0, 0x00),
        RdramRead(0x4000, page4),
        Fill(0, 0x4000, 0, page4),
        Fetch(0, 0x4000, 0x4001, page4, 0, 0x24100009),
        # Retag page-0 without fill: stale page-0 identity must not be invented.
        CacheOp(0, 0x0001, page4, 0x08),
        Fetch(0, 0x0000, 0x0001, page4, 0, 0x24100009),
        # Hit invalidate then refill page 0.
        CacheOp(0, 0x0000, page4, 0x10),
        RdramRead(0x0000, page0),
        Fill(0, 0x0000, 0, page0),
        Fetch(0, 0x0000, 0x0001, page0, 0, 0x24100001),
        # Miss invalidate leaves the resident tuple untouched.
        CacheOp(0, 0x0001, page0, 0x10),
        Fetch(0, 0x0000, 0x0001, page0, 0, 0x24100001),
        # Explicit CACHE fill obtains page 0x4000 through the same burst path.
        RdramRead(0x4000, page4),
        Fill(0, 0x4000, 0, page4),
        CacheOp(0, 0x4001, page4, 0x14),
        Fetch(0, 0x4000, 0x4001, page4, 0, 0x24100009),
        # Backing RAM mutates while the cache retains the old fill bytes.
        Other("host/debugger RAM word changes 9 -> 8; no cache fill"),
        # Hit writeback restores RAM to resident 9. The resident origin stays fill 4.
        RdramWrite(0x4000, page4),
        CacheOp(0, 0x4001, page4, 0x18),
        Fetch(0, 0x4000, 0x4001, page4, 0, 0x24100009),
        # A miss writeback likewise leaves this line unchanged.
        CacheOp(0, 0x4001, page4, 0x18),
        # Uncached direct RAM fetch has no cache-fill origin.
        Fetch(0, 0x4000, 0, page4, 0, 0x24100009, cached=False),
    ]
    expected = [1, None, 2, None, 3, 3, 4, 4, None]
    return events, expected
