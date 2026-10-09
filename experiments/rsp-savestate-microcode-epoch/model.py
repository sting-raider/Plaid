#!/usr/bin/env python3
"""Independent adversarial model for RSP executable-state restore epochs."""
from dataclasses import dataclass
import hashlib
import json
import random

@dataclass(frozen=True)
class RestoreRoot:
    snapshot: str
    epoch: int
    component: str

@dataclass(frozen=True)
class CapturedOrigin:
    snapshot: str
    install_generation: int
    writer_generation: int
    image: str

@dataclass(frozen=True)
class Certificate:
    root: RestoreRoot
    captured: CapturedOrigin

S0_ORIGIN = CapturedOrigin("S0", 1, 1, "A")
LIVE_ROOT = RestoreRoot("S0", 2, "rsp_imem")
GOOD = Certificate(LIVE_ROOT, S0_ORIGIN)


def verify(cert: Certificate) -> bool:
    return (
        cert.root == LIVE_ROOT
        and cert.captured == S0_ORIGIN
        and cert.root.snapshot == cert.captured.snapshot
    )


def compose_cpu_rsp(cpu_root: RestoreRoot, rsp_root: RestoreRoot) -> bool:
    return (
        cpu_root.snapshot == rsp_root.snapshot
        and cpu_root.epoch == rsp_root.epoch
        and cpu_root.component == "cpu_exec"
        and rsp_root.component == "rsp_imem"
    )

assert verify(GOOD)
forged = {
    "latest_equal_install": Certificate(LIVE_ROOT, CapturedOrigin("S0", 3, 3, "A")),
    "latest_equal_direct_writer": Certificate(LIVE_ROOT, CapturedOrigin("S0", 1, 4, "A")),
    "abandoned_distinct_install": Certificate(LIVE_ROOT, CapturedOrigin("S0", 2, 2, "B")),
    "wrong_restore_epoch": Certificate(RestoreRoot("S0", 1, "rsp_imem"), S0_ORIGIN),
    "wrong_snapshot": Certificate(RestoreRoot("S1", 2, "rsp_imem"), S0_ORIGIN),
    "missing_restore_boundary": Certificate(RestoreRoot("S0", 0, "rsp_imem"), S0_ORIGIN),
}
for name, cert in forged.items():
    assert not verify(cert), name
assert compose_cpu_rsp(RestoreRoot("S0", 2, "cpu_exec"), LIVE_ROOT)
assert not compose_cpu_rsp(RestoreRoot("S0", 1, "cpu_exec"), LIVE_ROOT)
assert not compose_cpu_rsp(RestoreRoot("S1", 2, "cpu_exec"), LIVE_ROOT)

# Falsification sweep: after capture, create random abandoned futures. Whenever a
# later equal-payload install exists, a naive "latest matching image" rule must
# disagree with the restored S0 causal ancestor even though the bytes match.
rng = random.Random(0x504C414944)
cases = 50000
naive_equal_false_joins = 0
naive_latest_false_joins = 0
for _ in range(cases):
    events = [(1, "A")]
    generation = 1
    for _ in range(rng.randrange(1, 9)):
        generation += 1
        events.append((generation, rng.choice(["A", "B", "C", "D"])))
    latest_any = events[-1][0]
    latest_equal = max(g for g, image in events if image == "A")
    if latest_any != 1:
        naive_latest_false_joins += 1
    if latest_equal != 1:
        naive_equal_false_joins += 1
        assert latest_equal > 1

assert naive_latest_false_joins == cases
assert naive_equal_false_joins > cases // 2
report = {
    "cases": cases,
    "forged_rejected": sorted(forged),
    "mixed_epoch_rejected": True,
    "naive_equal_false_joins": naive_equal_false_joins,
    "naive_latest_false_joins": naive_latest_false_joins,
    "rule": "post-restore RSP executable state is rooted at restore(snapshot,epoch,component); captured ancestry may be nested under that root but live generations cannot cross the load by value equality",
}
blob = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
print(json.dumps(report, sort_keys=True))
print("MODEL_SHA256=" + hashlib.sha256(blob).hexdigest())
