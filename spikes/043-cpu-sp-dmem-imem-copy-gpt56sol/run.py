"""Execute the exact-pinned ares CPU-mediated SP DMEM -> IMEM copy experiment."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from prepare import generate

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-cpu-sp-dmem-imem-copy-spike"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

TRACKED = (8, 9, 10, 16)
SOURCE = 0x34081234


def load_builder():
    spec = importlib.util.spec_from_file_location("copy_builder", ROOT / "spikes/003-ares-oracle/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sensor(builder):
    inputs = (HERE / "driver.cpp", HERE / "observer.hpp", HERE / "prepare.py", Path(builder.__file__))
    key = hashlib.sha256(b"".join(p.read_bytes() for p in inputs)).hexdigest()
    out = OUTPUT / ("sensor-" + key[:12])
    exe = out / "oracle-traced"
    if exe.exists():
        return exe

    builder.build(HERE / "baseline.cpp", out, extra_sources=inputs)
    generate(REF, out)

    flags = [
        "-O1", "-std=c++20", "-msse4.1",
        "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1",
        "-DPLAID_COPY_SP_SENSOR=1",
    ]
    includes = [out / "include", *(REF / p for p in (
        "ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system"
    ))]
    include_flags = [part for p in includes for part in ("-I", str(p))]
    sources = [
        HERE / "driver.cpp",
        out / "core.cpp",
        out / "n64.cpp",
        REF / "ares/component/processor/sm5k/sm5k.cpp",
        REF / "ares/ares/memory/fixed-allocator.cpp",
        REF / "nall/nall/nall.cpp",
        REF / "thirdparty/sljitAllocator.cpp",
    ]
    with (out / "sensor-build.log").open("w", encoding="utf-8") as log:
        try:
            subprocess.run(
                ["g++", *flags, *include_flags, *map(str, sources),
                 str(out / "sljit.o"), str(out / "libco.o"),
                 "-pthread", "-ldl", "-o", str(exe)],
                check=True, stdout=log, stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            print("\n".join((out / "sensor-build.log").read_text(encoding="utf-8").splitlines()[-80:]), flush=True)
            raise
    return exe


def sign32(value):
    value &= 0xffffffff
    return value | 0xffffffff00000000 if value & 0x80000000 else value


def simm16(word):
    value = word & 0xffff
    return value - 0x10000 if value & 0x8000 else value


def decode(word):
    op = word >> 26
    rs = (word >> 21) & 31
    rt = (word >> 16) & 31
    if op == 0x23:
        return {"kind": "lw", "rs": rs, "rt": rt, "imm": simm16(word), "writes": rt}
    if op == 0x2b:
        return {"kind": "sw", "rs": rs, "rt": rt, "imm": simm16(word), "writes": None}
    if op == 0x0d:
        return {"kind": "ori", "rs": rs, "rt": rt, "imm": word & 0xffff, "writes": rt}
    if op == 0 and (word & 0x3f) == 0x21:
        rd = (word >> 11) & 31
        return {"kind": "addu", "rs": rs, "rt": rt, "rd": rd, "writes": rd}
    raise AssertionError(f"unsupported fixture instruction {word:08x}")


def reg_value(step, which, reg):
    assert reg in TRACKED, f"untracked fixture register r{reg}"
    return step[which][TRACKED.index(reg)]


def expected_sp_address(step, insn):
    base = reg_value(step, "before", insn["rs"])
    vaddr = (base + insn["imm"]) & 0xffffffffffffffff
    assert (vaddr & 0xffffffffe0000000) == 0xffffffffa0000000
    return vaddr & 0x1fffffff


def validate_register_effect(step, insn, phase_events):
    before = dict(zip(TRACKED, step["before"]))
    after = dict(zip(TRACKED, step["after"]))
    kind = insn["kind"]

    if kind == "lw":
        reads = [e for e in phase_events if e["kind"] == "sp_read"]
        assert len(reads) == 1
        event = reads[0]
        assert event["cpu"] and event["bytes"] == 4
        assert event["address"] == expected_sp_address(step, insn)
        assert event["bank"] == ((event["address"] >> 12) & 1)
        assert event["offset"] == (event["address"] & 0xffc)
        assert after[insn["rt"]] == sign32(event["value"])
        for reg in TRACKED:
            if reg != insn["rt"]:
                assert after[reg] == before[reg]
        return

    if kind == "sw":
        writes = [e for e in phase_events if e["kind"] == "sp_write"]
        assert len(writes) == 1
        event = writes[0]
        assert event["cpu"] and event["bytes"] == 4
        assert event["address"] == expected_sp_address(step, insn)
        assert event["bank"] == ((event["address"] >> 12) & 1)
        assert event["offset"] == (event["address"] & 0xffc)
        assert event["value"] == (before[insn["rt"]] & 0xffffffff)
        assert after == before
        return

    assert not phase_events
    if kind == "ori":
        rs_value = 0 if insn["rs"] == 0 else before[insn["rs"]]
        expected = (rs_value | insn["imm"]) & 0xffffffffffffffff
        assert after[insn["rt"]] == expected
        for reg in TRACKED:
            if reg != insn["rt"]:
                assert after[reg] == before[reg]
        return

    if kind == "addu":
        rs_value = 0 if insn["rs"] == 0 else before[insn["rs"]]
        rt_value = 0 if insn["rt"] == 0 else before[insn["rt"]]
        expected = sign32((rs_value + rt_value) & 0xffffffff)
        assert after[insn["rd"]] == expected
        for reg in TRACKED:
            if reg != insn["rd"]:
                assert after[reg] == before[reg]
        return

    raise AssertionError(kind)


def analyze(data):
    events = data["events"]
    steps = data["steps"]
    assert [e["ordinal"] for e in events] == list(range(1, len(events) + 1))
    assert [s["phase"] for s in steps] == [1,2,3,4,5,6,7,8,9,10,11,13,14,15]
    assert all(events[n]["phase"] <= events[n+1]["phase"] for n in range(len(events)-1))

    by_phase = {}
    for e in events:
        assert e["kind"] in ("sp_read", "sp_write")
        assert e["bytes"] == 4 and e["cpu"]
        assert 0x04000000 <= e["address"] <= 0x0403ffff
        assert e["bank"] == ((e["address"] >> 12) & 1)
        assert e["offset"] == (e["address"] & 0xffc)
        assert 0 <= e["value"] < 1 << 32
        by_phase.setdefault(e["phase"], []).append(e)

    decoded = {}
    for step in steps:
        insn = decode(step["word"])
        decoded[step["phase"]] = insn
        validate_register_effect(step, insn, by_phase.get(step["phase"], []))

    step_phases = {s["phase"] for s in steps}
    out_of_context = [e for e in events if e["phase"] not in step_phases]

    certificates = []
    rejected = []
    for pos, step in enumerate(steps):
        insn = decoded[step["phase"]]
        if insn["kind"] != "sw":
            continue
        event = by_phase[step["phase"]][0]

        if event["bank"] != 1:
            rejected.append({"store_phase": step["phase"], "reason": "destination_not_imem"})
            continue

        source_reg = insn["rt"]
        writer_step = None
        writer_insn = None
        for previous in reversed(steps[:pos]):
            candidate = decoded[previous["phase"]]
            if candidate["writes"] == source_reg:
                writer_step, writer_insn = previous, candidate
                break

        if writer_step is None or writer_insn["kind"] != "lw":
            rejected.append({"store_phase": step["phase"], "reason": "last_writer_not_lw"})
            continue

        reads = [e for e in by_phase.get(writer_step["phase"], []) if e["kind"] == "sp_read"]
        assert len(reads) == 1
        read = reads[0]
        if read["bank"] != 0:
            rejected.append({"store_phase": step["phase"], "reason": "source_not_dmem"})
            continue

        assert writer_insn["rt"] == source_reg
        assert reg_value(writer_step, "after", source_reg) == reg_value(step, "before", source_reg)
        assert (reg_value(step, "before", source_reg) & 0xffffffff) == event["value"]
        assert event["value"] == read["value"]

        certificates.append({
            "load_phase": writer_step["phase"],
            "read_ordinal": read["ordinal"],
            "store_phase": step["phase"],
            "write_ordinal": event["ordinal"],
            "source_reg": source_reg,
            "source_bank": read["bank"],
            "source_offset": read["offset"],
            "destination_bank": event["bank"],
            "destination_offset": event["offset"],
            "value": event["value"],
        })

    return {
        "certificates": certificates,
        "rejected": rejected,
        "out_of_context": out_of_context,
        "mutation_coverage_certified": False,
        "executable_lifetime_certified": False,
        "rsp_origin_certified": False,
        "native_complete": False,
    }


def verify_fixture(data):
    resolved = analyze(data)
    certs = resolved["certificates"]
    assert [c["store_phase"] for c in certs] == [2, 5, 15]
    assert [c["load_phase"] for c in certs] == [1, 3, 14]
    assert certs[1]["load_phase"] != 4
    assert certs[0]["destination_offset"] == certs[2]["destination_offset"] == 0
    assert certs[0]["value"] == certs[2]["value"] == SOURCE
    assert certs[0]["write_ordinal"] != certs[2]["write_ordinal"]
    assert {(r["store_phase"], r["reason"]) for r in resolved["rejected"]} == {
        (8, "last_writer_not_lw"),
        (11, "last_writer_not_lw"),
        (13, "destination_not_imem"),
    }
    assert len(resolved["out_of_context"]) == 1
    external = resolved["out_of_context"][0]
    assert external["phase"] == 12 and external["kind"] == "sp_write"
    assert external["bank"] == 1 and external["offset"] == 0x20 and external["value"] == SOURCE
    return resolved


def expect_reject(data, label):
    try:
        verify_fixture(data)
    except (AssertionError, KeyError, IndexError):
        return
    raise AssertionError("forged history accepted: " + label)


def negative(data):
    cases = []

    forged = copy.deepcopy(data)
    next(e for e in forged["events"] if e["phase"] == 3 and e["kind"] == "sp_read")["phase"] = 4
    cases.append(("move causal read onto equal-value decoy phase", forged))

    forged = copy.deepcopy(data)
    next(s for s in forged["steps"] if s["phase"] == 4)["word"] = 0x8e080004
    cases.append(("rewrite equal-value decoy instruction to fake t0 writer", forged))

    forged = copy.deepcopy(data)
    next(s for s in forged["steps"] if s["phase"] == 10)["word"] = 0x8e080000
    cases.append(("rewrite same-value arithmetic clobber as a load", forged))

    forged = copy.deepcopy(data)
    next(e for e in forged["events"] if e["phase"] == 11 and e["kind"] == "sp_write")["bank"] = 0
    cases.append(("forge IMEM sink bank", forged))

    forged = copy.deepcopy(data)
    next(e for e in forged["events"] if e["phase"] == 12)["phase"] = 11
    cases.append(("hide out-of-context sink inside executed store phase", forged))

    forged = copy.deepcopy(data)
    forged["events"][1]["ordinal"] = forged["events"][0]["ordinal"]
    cases.append(("duplicate storage ordinal", forged))

    forged = copy.deepcopy(data)
    next(e for e in forged["events"] if e["phase"] == 14 and e["kind"] == "sp_read")["value"] ^= 1
    cases.append(("change completed source read under unchanged register result", forged))

    forged = copy.deepcopy(data)
    sink = next(e for e in forged["events"] if e["phase"] == 15 and e["kind"] == "sp_write")
    sink["address"] += 4
    sink["offset"] += 4
    cases.append(("move same-value rewrite sink", forged))

    for label, forged in cases:
        expect_reject(forged, label)
    print(f"PASS {len(cases)} forged dataflow/storage histories rejected", flush=True)


def parse(raw):
    lines = raw.splitlines()
    assert len(lines) == 1, lines
    return json.loads(lines[0])


def worker():
    builder = load_builder()
    assert builder.REV == PIN
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == PIN
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)

    source_receipt = {
        "ares_revision": PIN,
        "rsp_io_sha256": sha(REF / "ares/n64/rsp/io.cpp"),
        "cpu_interpreter_ipu_sha256": sha(REF / "ares/n64/cpu/interpreter-ipu.cpp"),
        "rsp_header_sha256": sha(REF / "ares/n64/rsp/rsp.hpp"),
    }

    baseline = builder.build(HERE / "baseline.cpp", OUTPUT / "baseline", extra_sources=(HERE / "driver.cpp",))
    traced_exe = sensor(builder)

    baseline_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    plain_raw = subprocess.check_output([str(traced_exe), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(traced_exe), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(traced_exe), "traced"], text=True, timeout=30)

    baseline_data, plain_data, traced_data, repeat_data = map(parse, (
        baseline_raw, plain_raw, traced_raw, repeat_raw
    ))
    assert traced_raw == repeat_raw
    assert baseline_data["state"] == plain_data["state"] == traced_data["state"] == repeat_data["state"]
    assert baseline_data["steps"] == plain_data["steps"] == traced_data["steps"] == repeat_data["steps"]
    assert not baseline_data["events"] and not plain_data["events"]
    assert traced_data["events"] == repeat_data["events"]

    resolved = verify_fixture(traced_data)
    negative(traced_data)

    event_bytes = json.dumps(traced_data["events"], sort_keys=True, separators=(",", ":")).encode()
    cert_bytes = json.dumps(resolved["certificates"], sort_keys=True, separators=(",", ":")).encode()
    result = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "source_receipt": source_receipt,
        "raw": traced_data,
        "resolved": resolved,
        "baseline_equal": True,
        "observer_plain_equal": True,
        "repeat_equal": True,
        "event_sha256": hashlib.sha256(event_bytes).hexdigest(),
        "certificate_sha256": hashlib.sha256(cert_bytes).hexdigest(),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "results.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print("EVENT_SHA256=" + result["event_sha256"], flush=True)
    print("CERTIFICATE_SHA256=" + result["certificate_sha256"], flush=True)
    print("RESULT_SHA256=" + digest, flush=True)
    print("PASS exact CPU SP DMEM->IMEM copy dataflow; equal-value/clobber/out-of-context adversaries fail closed", flush=True)


def main():
    if os.name == "nt":
        path = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", path], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
