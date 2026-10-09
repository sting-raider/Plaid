"""Replay completed RSP IMEM sink events into byte-generation ownership."""
from copy import deepcopy

class VerificationError(RuntimeError):
    pass


def byte_span(offset, size):
    return [((offset + i) & 0xfff) for i in range(size)]


def replay(events):
    active = None
    last_promoted = 0
    request_effects = {}
    owner = [None] * 4096
    generations = 0
    completed = []
    for expected_seq, ev in enumerate(events, 1):
        if ev["seq"] != expected_seq:
            raise VerificationError("non-contiguous event sequence")
        kind = ev["kind"]
        req = ev["request"]
        if kind == "promote":
            if active is not None:
                raise VerificationError("promotion while another request is active")
            if req <= last_promoted:
                raise VerificationError("request generation is not strictly monotonic")
            active = req
            last_promoted = req
            request_effects[req] = []
        elif kind == "dma_sink":
            if active is None or req != active:
                raise VerificationError("DMA sink not owned by active promoted request")
            generations += 1
            token = ("dma", req, generations)
            span = byte_span(ev["pbus"], 8)
            for b in span:
                owner[b] = token
            request_effects[req].append({"span": span, "token": token, "case": ev["case"]})
        elif kind == "cpu_sink":
            if req != 0:
                raise VerificationError("CPU sink forged as DMA-owned")
            generations += 1
            token = ("cpu", ev["case"], generations)
            for b in byte_span(ev["pbus"], 4):
                owner[b] = token
        elif kind == "complete":
            if active is None or req != active:
                raise VerificationError("completion does not match active request")
            completed.append(req)
            active = None
        else:
            raise VerificationError(f"unknown event kind {kind}")
    if active is not None:
        raise VerificationError("trace ended with an active request")
    return {"owner": owner, "request_effects": request_effects, "completed": completed}


def assert_fixture_contract(doc):
    result = replay(doc["events"])
    req1 = result["request_effects"][1]
    assert [x["span"] for x in req1] == [list(range(0x200,0x208)), list(range(0x208,0x210))]
    assert all(result["owner"][b][0] == "cpu" for b in range(0x204,0x208))
    assert all(result["owner"][b][0] == "dma" and result["owner"][b][1] == 1 for b in list(range(0x200,0x204))+list(range(0x208,0x210)))

    req2 = result["request_effects"][2]
    req3 = result["request_effects"][3]
    assert [x["span"] for x in req2] == [list(range(0x300,0x308)), list(range(0x308,0x310))]
    assert [x["span"] for x in req3] == [list(range(0x300,0x308)), list(range(0x308,0x310))]
    assert all(result["owner"][b][1] == 3 for b in range(0x300,0x310))

    req4 = result["request_effects"][4]
    assert req4[0]["span"] == list(range(0xff8,0x1000))
    assert req4[1]["span"] == list(range(0x000,0x008))
    assert result["completed"] == [1,2,3,4,5,6]
    return result


def adversarial_checks(doc):
    failures = []
    bad = deepcopy(doc)
    sink = next(e for e in bad["events"] if e["kind"] == "dma_sink" and e["request"] == 3)
    sink["request"] = 2
    try:
        replay(bad["events"])
    except VerificationError:
        failures.append("wrong-active-request")

    bad = deepcopy(doc)
    promote = [e for e in bad["events"] if e["kind"] == "promote"][1]
    promote["request"] = 1
    try:
        replay(bad["events"])
    except VerificationError:
        failures.append("reused-request-id")

    bad = deepcopy(doc)
    idx = max(i for i,e in enumerate(bad["events"]) if e["kind"] == "complete")
    del bad["events"][idx]
    for i,e in enumerate(bad["events"],1):
        e["seq"] = i
    try:
        replay(bad["events"])
    except VerificationError:
        failures.append("missing-completion")

    assert failures == ["wrong-active-request","reused-request-id","missing-completion"]
    return failures
