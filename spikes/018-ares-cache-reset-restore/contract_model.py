#!/usr/bin/env python3
from dataclasses import dataclass
from copy import deepcopy
import json

A = 0x24100001  # addiu s0, zero, 1
B = 0x24100002  # addiu s0, zero, 2

@dataclass
class Line:
    tag_key: int = 0
    index: int = 0
    words: list[int] = None
    def __post_init__(self):
        if self.words is None:
            self.words = [0] * 8
    def valid(self): return bool(self.tag_key & 1)
    def hit(self, paddr):
        return self.valid() and (self.tag_key & ~1) == (paddr & ~0xfff)
    def fill(self, paddr, words):
        self.tag_key = (paddr & ~0xfff) | 1
        self.words = list(words)
    def power(self, slot):
        self.tag_key = 0
        self.index = (slot << 5) & 0xfe0
        self.words = [0] * 8

class FillObserver:
    def __init__(self):
        self.fills = []
        self.last = {}
    def completed_fill(self, slot, paddr, line):
        rec = (slot, paddr, line.index, tuple(line.words))
        self.fills.append(rec)
        self.last[slot] = len(self.fills)
        return len(self.fills)
    def tuple_join(self, slot, paddr, line):
        fid = self.last.get(slot)
        if not fid: return None
        s, phys, index, words = self.fills[fid - 1]
        if s != slot or (phys & ~0xfff) != (paddr & ~0xfff) or index != line.index or words != tuple(line.words):
            return None
        return fid

slot = 0
paddr = 0
ram = [A] + [0] * 7
line = Line(index=0)
obs = FillObserver()
events = []

# Initial fill A.
line.fill(paddr, ram)
fill1 = obs.completed_fill(slot, paddr, line)
saved_line = deepcopy(line)
events.append(["fill", fill1, A])

# Equal-payload refill creates a newer historical fill with the same tuple.
line.tag_key &= ~1
assert not line.hit(paddr)
line.fill(paddr, ram)
fill2 = obs.completed_fill(slot, paddr, line)
events.append(["equal_refill", fill2, A])
assert fill2 != fill1 and obs.tuple_join(slot, paddr, line) == fill2

# Reset/power is a hard boundary and itself performs no fill.
fills_before_reset = len(obs.fills)
line.power(slot)
events.append(["power", line.tag_key, line.words[0]])
assert len(obs.fills) == fills_before_reset
assert not line.hit(paddr) and line.words == [0] * 8

# Savestate restore resurrects a valid resident line with no fill.
line = deepcopy(saved_line)
events.append(["restore", line.tag_key, line.words[0]])
assert len(obs.fills) == fills_before_reset
assert line.hit(paddr) and line.words[0] == A

# Adversarial result: tuple/payload matching falsely points at pre-reset fill2.
naive = obs.tuple_join(slot, paddr, line)
assert naive == fill2
assert naive is not None

# Current backing is not resident-byte origin either.
ram[0] = B
cached_word = line.words[0]
uncached_word = ram[0]
events.append(["backing_mutation", cached_word, uncached_word])
assert cached_word == A and uncached_word == B

# After a reset, a cached fetch cannot reuse the restored line; it must fill current backing.
line.power(slot)
assert not line.hit(paddr)
line.fill(paddr, ram)
fill3 = obs.completed_fill(slot, paddr, line)
events.append(["post_reset_fill", fill3, line.words[0]])
assert line.hit(paddr) and line.words[0] == B and fill3 == 3

result = {
    "hypothesis": "reset is a lineage boundary; restore can resurrect resident bytes without a post-reset fill",
    "fill_ids": [fill1, fill2, fill3],
    "naive_post_restore_join": naive,
    "naive_join_is_pre_reset": naive <= fills_before_reset,
    "cached_after_restore_before_reset": cached_word,
    "current_backing_after_mutation": uncached_word,
    "events": events,
    "result": "COUNTEREXAMPLE_CONFIRMED",
}
print(json.dumps(result, indent=2))
