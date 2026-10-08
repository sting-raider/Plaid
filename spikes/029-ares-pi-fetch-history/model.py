"""Original finite byte/writer and resident-line checker, independent of CPU code."""


def rom_bytes():
    source = bytearray(16384)
    for offset, word in ((0, 0x80371240), (0x80, 0xae090000), (0x84, 0xbe100000),
                         (0x1000, 0x34081111), (0x2000, 0x34081111), (0x3000, 0x34083333)):
        source[offset:offset+4] = word.to_bytes(4, "big")
    return source


def check(events):
    source = rom_bytes()
    assert [e["ordinal"] for e in events] == list(range(1, len(events)+1))
    ram, resident, buffer = {}, {}, {}
    transfer = block = attempt = committed = context = pending = None
    returned = False
    previous = None
    reads = []
    samples, writes, completions = [], [], []
    stage = block_count = transfer_stage = 0

    def bytes_for(address, width, value, writer, rom_offset=None, transfer_id=None):
        values = value.to_bytes(width, "big")
        return [dict(value=byte, writer=writer, rom_offset=None if rom_offset is None else rom_offset+i,
                     transfer=transfer_id) for i, byte in enumerate(values)]

    def backing(address, values):
        origins = []
        for index, value in enumerate(values):
            origin = ram.get(address+index)
            if origin is not None:
                assert origin["value"] == value
            origins.append(origin)
        return origins

    for e in events:
        kind = e["kind"]
        assert type(e["stage"]) is int and stage <= e["stage"] <= 20
        stage = e["stage"]
        if context is not None:
            assert stage == context["stage"]
        if transfer is not None:
            assert stage == transfer_stage
        if pending is not None:
            assert kind == "fetch", "prologue must immediately follow access return"
        if kind == "pi":
            assert context is None
            event = e["event"]
            if event == 1:
                assert transfer is None and block is None and attempt is None
                assert e["transfer"] == len(completions)+1 and e["block"] == 0
                transfer, returned = e["transfer"], False
                transfer_stage, block_count = stage, 0
            else:
                assert e["transfer"] == transfer
            if event == 2:
                assert block is None and not returned and attempt is None
                block_count += 1
                assert e["block"] == block_count
                block = e["block"]
                assert 0 < e["length"] <= 128 and 0 <= e["lane"] <= 7
                buffer = {}
            elif event in (3, 4, 5, 6):
                assert block is not None and block == e["block"] and not returned
                if event == 3:
                    assert attempt is None and e["lane"] % 2 == 0 and e["lane"] < e["length"]
                    assert e["lane"] not in buffer
                    witnessed = previous is not None and previous["kind"] == "rom" \
                        and previous["transfer"] == transfer and previous["block"] == block \
                        and previous["offset"]+0x10000000 == e["pbus"] and previous["value"] == e["value"]
                    origins = bytes_for(0, 2, e["value"], None,
                                        previous["offset"] if witnessed else None, transfer)
                    for index, origin in enumerate(origins):
                        buffer[e["lane"]+index] = origin
                elif event == 4:
                    assert attempt is None and e["lane"] in buffer
                    assert e["value"] == buffer[e["lane"]]["value"]
                    attempt, committed = e, None
                elif event == 5:
                    assert attempt is not None
                    assert all(e[key] == attempt[key] for key in ("dram", "pbus", "length", "lane", "value"))
                    if committed is not None:
                        origin = dict(buffer[e["lane"]], writer=committed["ordinal"])
                        ram[e["dram"]] = origin
                        writes.append(dict(address=e["dram"], **origin))
                    attempt = committed = None
                else:
                    assert attempt is None
                    block = None
            elif event == 7:
                assert block is None and attempt is None and not returned
                returned = True
            elif event == 8:
                assert returned and block is None and e["lane"] == 0 and e["value"] == 1
                completions.append(transfer)
                transfer = None
            else:
                assert event == 1
        elif kind == "rom":
            assert transfer == e["transfer"] and block == e["block"] and attempt is None and not returned
            offset = e["offset"]
            assert 0 <= offset <= len(source)-2
            assert e["value"] == int.from_bytes(source[offset:offset+2], "big")
        elif kind == "scalar":
            assert e["context"] == (context["ordinal"] if context else 0)
            assert e["bytes"] in (1, 2, 4, 8) and 0 <= e["address"] < 8388608
            assert 0 <= e["value"] < 1 << (e["bytes"]*8)
            if e["write"]:
                assert context is None
                if e["device"] == 5:
                    assert attempt is not None and committed is None and e["bytes"] == 1
                    assert (e["address"], e["value"]) == (attempt["dram"], attempt["value"])
                    committed = e
                else:
                    assert transfer is None and e["device"] == 3 and e["bytes"] == 4
                    origins = bytes_for(e["address"], 4, e["value"], e["ordinal"])
                    for index, origin in enumerate(origins):
                        ram[(e["address"] & ~3)+index] = origin
            elif context is not None:
                reads.append(e)
        elif kind == "begin":
            assert context is None and transfer is None and pending is None
            assert e["context"] == e["ordinal"] and e["bus"] == e["translated"]
            assert e["bus"] % 4 == 0 and e["value"] == 0
            context, reads = e, []
        elif kind == "burst":
            assert context is not None and e["context"] == context["ordinal"] and context["cached"]
            assert not e["write"] and e["bytes"] == 32 and e["device"] == 1
            assert e["address"] % 32 == 0 and len(e["words"]) == 8
            backing(e["address"], b"".join(word.to_bytes(4, "big") for word in e["words"]))
        elif kind == "fill":
            assert context is not None and e["context"] == context["ordinal"] and context["cached"]
            assert previous["kind"] == "burst" and previous["context"] == e["context"]
            assert e["slot"] == (context["vaddr"] >> 5 & 511) and e["physical"] == context["bus"]
            assert e["index"] == (e["slot"] << 5 & 0xfe0)
            address = (e["physical"] & ~0xfff) | e["index"]
            assert address == previous["address"] and e["words"] == previous["words"]
            values = b"".join(word.to_bytes(4, "big") for word in e["words"])
            resident[e["slot"]] = dict(tag=(e["physical"] & ~0xfff) | 1,
                                       words=e["words"], origins=backing(address, values), fill=e["ordinal"])
        elif kind == "end":
            assert context is not None
            assert all(e[key] == context[key] for key in ("context", "vaddr", "translated", "bus", "cached"))
            pending = dict(e, reads=reads)
            context = None
        elif kind == "fetch":
            assert pending is not None and context is None
            assert e["pc"] == pending["vaddr"] and e["physical"] == pending["bus"]
            assert e["cached"] == pending["cached"] and e["word"] == pending["value"]
            assert e["stage"] == pending["stage"] and e["slot"] == (e["pc"] >> 5 & 511)
            origins, fill = [None]*4, None
            if e["cached"]:
                line = resident.get(e["slot"])
                assert line is not None and line["tag"] == e["tag"] and line["words"] == e["words"]
                assert e["tag"] == (e["physical"] & ~0xfff) | 1
                lane = e["physical"] >> 2 & 7
                assert e["word"] == line["words"][lane] and not pending["reads"]
                origins, fill = line["origins"][lane*4:lane*4+4], line["fill"]
            else:
                assert e["words"] == [] and e["tag"] == 0
                eligible = [read for read in pending["reads"] if not read["write"] and
                            read["device"] == 3 and read["bytes"] == 4 and read["address"] == e["physical"] and
                            read["value"] == e["word"]]
                if len(eligible) == 1:
                    origins = backing(e["physical"], e["word"].to_bytes(4, "big"))
            offsets = [origin["rom_offset"] if origin else None for origin in origins]
            contiguous = all(offset is not None for offset in offsets) and offsets == list(range(offsets[0], offsets[0]+4))
            samples.append(dict(stage=e["stage"], word=e["word"], cached=e["cached"], fill=fill,
                                rom_offsets=offsets, writers=[o["writer"] if o else None for o in origins],
                                transfers=[o["transfer"] if o else None for o in origins],
                                contiguous_rom_word=contiguous))
            pending = None
        elif kind == "cache":
            assert context is None and transfer is None and e["operation"] == 16
            slot = e["vaddr"] >> 5 & 511
            line = resident.get(slot)
            assert line is not None and line["tag"] == e["before_tag"] and line["words"] == e["before_words"]
            assert (e["physical"] & ~0xfff) | 1 == e["before_tag"]
            assert e["after_tag"] == e["before_tag"] & ~1 and e["after_words"] == e["before_words"]
            del resident[slot]
        else:
            raise AssertionError("unsupported event")
        previous = e
    assert context is pending is attempt is block is transfer is None and completions == [1, 2, 3, 4]
    return dict(samples=samples, pi_writes=writes, completions=completions)
