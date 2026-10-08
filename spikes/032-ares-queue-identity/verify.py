"""Original independent replay of observed slot identities, not a heap emulator."""

FIELDS = {"ordinal", "phase", "kind", "slot", "other", "event", "clock", "valid", "token"}


def verify(events):
    slots = [None] * 512
    next_token = 0
    popped = set()
    counts = dict(successful_insertions=0, rejected_insertions=0,
                  identified_dispatch_candidates=[], unknown_valid_removals=0,
                  identified_canceled_removals=0, unknown_invalid_removals=0,
                  cancellation_records=0, serialization_boundaries=0)
    for ordinal, e in enumerate(events, 1):
        assert set(e) == FIELDS and type(e["valid"]) is bool
        for k in FIELDS - {"valid"}:
            assert type(e[k]) is int and e[k] >= 0
        assert e["ordinal"] == ordinal and 1 <= e["phase"] <= 6
        kind, slot, other = e["kind"], e["slot"], e["other"]
        assert 1 <= kind <= 9 and e["event"] < 2 and e["clock"] < 2**32
        if kind in (1, 9):
            assert e["token"] == 0 and slot == other == e["event"] == 0
            slots = [None] * 512
            counts["serialization_boundaries"] += kind == 9
        elif kind == 2:
            assert slot == 512 and other == 0 and e["token"] == 0 and not e["valid"]
            counts["rejected_insertions"] += 1
        else:
            assert slot < 512 and other < 512
            if kind == 4:
                next_token += 1
                assert e["token"] == next_token and e["valid"] and other == 0
                slots[slot] = dict(token=next_token, event=e["event"], clock=e["clock"], valid=True)
                counts["successful_insertions"] += 1
            elif kind in (3, 6, 7):
                source = slots[other]
                assert e["token"] == (source["token"] if source else 0)
                if source:
                    assert all(e[k] == source[k] for k in ("event", "clock", "valid"))
                slots[slot] = source.copy() if source else None
            else:
                source = slots[slot]
                assert e["token"] == (source["token"] if source else 0)
                if source:
                    assert all(e[k] == source[k] for k in ("event", "clock", "valid"))
                if kind == 8:
                    assert other == 0
                    counts["cancellation_records"] += 1
                    if source: slots[slot] = dict(source, valid=False)
                else:
                    assert kind == 5
                    if source:
                        assert source["token"] not in popped
                        popped.add(source["token"])
                    if e["valid"]:
                        if source:
                            counts["identified_dispatch_candidates"].append(
                                dict(phase=e["phase"], token=source["token"], event=e["event"], deadline=e["clock"]))
                        else: counts["unknown_valid_removals"] += 1
                    elif source: counts["identified_canceled_removals"] += 1
                    else: counts["unknown_invalid_removals"] += 1
    return counts
