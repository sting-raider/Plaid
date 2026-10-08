"""Fail-closed verifier for the bounded pinned-ares PI/queue fixture."""
from copy import deepcopy

PI_DMA_WRITE = 1


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(payload):
    q = payload["queue_trace"]
    p = payload["pi_trace"]
    requests = payload["requests"]

    def qs(phase, kind=None, event=None, request=None, valid=None):
        out = [x for x in q if x["phase"] == phase]
        if kind is not None: out = [x for x in out if x["kind"] == kind]
        if event is not None: out = [x for x in out if x["event"] == event]
        if request is not None: out = [x for x in out if x["request"] == request]
        if valid is not None: out = [x for x in out if x["valid"] is valid]
        return out

    def ps(phase, kind=None, request=None):
        out = [x for x in p if x["phase"] == phase]
        if kind is not None: out = [x for x in out if x["kind"] == kind]
        if request is not None: out = [x for x in out if x["request"] == request]
        return out

    # Normal: request-bound insertion token survives heap removal into the
    # synchronous CPU dispatch callback and dmaFinished status transition.
    normal = requests["normal"]
    _require(normal != 0, "normal request missing")
    ni = qs(1, 4, PI_DMA_WRITE, normal, True)
    _require(len(ni) == 1 and ni[0]["token"] != 0, "normal insertion token missing")
    token = ni[0]["token"]
    nstart, nend = ps(1, 1, normal), ps(1, 7, normal)
    nr = [x for x in qs(1, 5, PI_DMA_WRITE, valid=True) if x["token"] == token]
    nc = ps(1, 8, normal)
    _require(len(nstart) == len(nend) == len(nr) == len(nc) == 1, "normal causal chain cardinality")
    _require(nc[0]["token"] == token, "normal completion token mismatch")
    _require(ni[0]["o"] < nstart[0]["o"] < nend[0]["o"] < nr[0]["o"] < nc[0]["o"], "normal chronology")

    # Cancellation: the exact token is invalidated by PI_STATUS reset and must
    # never produce a completion callback when the invalid heap entry drains.
    cancel = requests["cancel"]
    ci = qs(2, 4, PI_DMA_WRITE, cancel, True)
    _require(len(ci) == 1 and ci[0]["token"] != 0, "cancel insertion token missing")
    ctoken = ci[0]["token"]
    cc = [x for x in qs(2, 8, PI_DMA_WRITE, cancel, True) if x["token"] == ctoken]
    _require(len(cc) == 1, "exact cancellation token not observed")
    _require(len(ps(2, 8)) == 0, "canceled request fabricated completion")
    _require(ps(2, 7, cancel)[0]["o"] < cc[0]["o"], "cancel before transfer end")

    # Rejection: actual CPU queue insertion fails, but PI dmaWrite still runs.
    # There is deliberately no token to which a later completion may be joined.
    reject = requests["reject"]
    rj = qs(3, 2, PI_DMA_WRITE)
    _require(len(rj) == 1, "expected PI queue rejection")
    _require(len(qs(3, 4, PI_DMA_WRITE, reject, True)) == 0, "rejected request gained token")
    rs, re = ps(3, 1, reject), ps(3, 7, reject)
    _require(len(rs) == len(re) == 1 and rj[0]["o"] < rs[0]["o"] < re[0]["o"], "rejected request copy did not execute")
    _require(len(ps(3, 8)) == 0, "rejected request fabricated completion")

    # Equal deadline duplicate event values remain distinct queue identities.
    ei = qs(4, 4, PI_DMA_WRITE, 0, True)
    er = qs(4, 5, PI_DMA_WRITE, valid=True)
    ec = ps(4, 8, 0)
    itokens = [x["token"] for x in ei]
    _require(len(itokens) == 2 and len(set(itokens)) == 2, "equal-deadline insertion identities collapsed")
    _require(len(er) == len(ec) == 2, "equal-deadline dispatch cardinality")
    _require({x["token"] for x in er} == set(itokens), "equal-deadline removal tokens")
    _require({x["token"] for x in ec} == set(itokens), "equal-deadline completion tokens")
    _require(all(x["request"] == 0 for x in ec), "queue-only duplicate invented PI request")

    # Serialization boundary deliberately invalidates external identity. The
    # reference event can still dispatch, but provenance must remain unknown.
    restore = requests["restore"]
    ri = qs(5, 4, PI_DMA_WRITE, restore, True)
    _require(len(ri) == 1 and ri[0]["token"] != 0, "restore request insertion missing")
    _require(len(qs(5, 9)) >= 2, "save/restore boundaries missing")
    rr = qs(5, 5, PI_DMA_WRITE, valid=True)
    rc = ps(5, 8)
    _require(len(rr) == len(rc) == 1, "restored completion cardinality")
    _require(rr[0]["token"] == 0 and rc[0]["token"] == 0 and rc[0]["request"] == 0,
             "serialization must fail closed")

    return {
        "normal_token": token,
        "cancel_token": ctoken,
        "equal_tokens": sorted(itokens),
        "restore_original_token": ri[0]["token"],
        "queue_records": len(q),
        "pi_records": len(p),
    }


def adversarial_self_test(payload):
    mutations = []

    forged = deepcopy(payload)
    next(x for x in forged["pi_trace"] if x["phase"] == 1 and x["kind"] == 8)["token"] ^= 0x100000
    mutations.append(("normal_wrong_token", forged))

    forged = deepcopy(payload)
    exemplar = deepcopy(next(x for x in forged["pi_trace"] if x["phase"] == 1 and x["kind"] == 8))
    exemplar["phase"] = 2
    forged["pi_trace"].append(exemplar)
    mutations.append(("canceled_fake_completion", forged))

    forged = deepcopy(payload)
    exemplar = deepcopy(next(x for x in forged["pi_trace"] if x["phase"] == 1 and x["kind"] == 8))
    exemplar["phase"] = 3
    exemplar["request"] = forged["requests"]["reject"]
    forged["pi_trace"].append(exemplar)
    mutations.append(("rejected_fake_completion", forged))

    forged = deepcopy(payload)
    equal = [x for x in forged["pi_trace"] if x["phase"] == 4 and x["kind"] == 8]
    equal[1]["token"] = equal[0]["token"]
    mutations.append(("equal_identity_collapse", forged))

    forged = deepcopy(payload)
    old = next(x for x in forged["queue_trace"] if x["phase"] == 5 and x["kind"] == 4 and x["request"] == forged["requests"]["restore"])["token"]
    completion = next(x for x in forged["pi_trace"] if x["phase"] == 5 and x["kind"] == 8)
    completion["token"] = old
    completion["request"] = forged["requests"]["restore"]
    mutations.append(("restore_stale_token", forged))

    rejected = []
    for name, forged in mutations:
        try:
            verify(forged)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(f"forged trace accepted: {name}")
    return rejected
