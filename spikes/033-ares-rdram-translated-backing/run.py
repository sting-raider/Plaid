"""Build pinned ares and validate translated/degraded scalar-RDRAM backing witnesses."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import types

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-rdram-translated-backing-spike"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_patched_builder():
    """Patch a copy of the existing research builder in memory; canonical tooling stays untouched."""
    path = ROOT / "spikes/003-ares-oracle/run.py"
    source = path.read_text()
    anchor = '                ram = "// Project-owned successful identity-mapped ordinary RAM callbacks.'
    assert source.count(anchor) == 1
    insert_at = source.index("                destination.parent.mkdir(parents=True,exist_ok=True)", source.index(anchor))
    injection = r'''                plaidTranslatedOld = """        u32 chipIndex = mapped() / 2_MiB;
        u64 value = Memory::Writable::read<Size>(mapped());
        return degrade(mapped(), value, chipIndex);"""
                plaidTranslatedNew = """        u32 chipIndex = mapped() / 2_MiB;
        u32 plaidMapped = mapped();
        auto& plaidChip = self.chips[chipIndex];
        u64 value = Memory::Writable::read<Size>(plaidMapped);
        u32 plaidCci = plaidChip.cci;
        u32 plaidCcLow = plaidChip.ccLow;
        u32 plaidCcHigh = plaidChip.ccHigh;
        u64 plaidDelivered = degrade(plaidMapped, value, chipIndex);
        if(plaidRdramTranslatedObserver) plaidRdramTranslatedObserver(address, plaidMapped, Size, (u32)device, chipIndex, value, plaidDelivered, plaidCci, plaidCcLow, plaidCcHigh);
        return plaidDelivered;"""
                assert ram.count(plaidTranslatedOld) == 1
                ram = ram.replace(plaidTranslatedOld, plaidTranslatedNew)
                ram = "// Project-owned completed translated ordinary RAM read callback.\nusing PlaidRdramTranslatedObserver = void (*)(u32, u32, u32, u32, u32, u64, u64, u32, u32, u32);\ninline PlaidRdramTranslatedObserver plaidRdramTranslatedObserver = nullptr;\n" + ram
'''
    patched = source[:insert_at] + injection + source[insert_at:]
    module = types.ModuleType("plaid_patched_ares_builder")
    module.__file__ = str(path)
    exec(compile(patched, str(path), "exec"), module.__dict__)
    return module, source, patched


def source_guard(ref):
    header = (ref / "ares/n64/rdram/rdram.hpp").read_text()
    implementation = (ref / "ares/n64/rdram/rdram.cpp").read_text()
    scalar = """        u32 chipIndex = mapped() / 2_MiB;
        u64 value = Memory::Writable::read<Size>(mapped());
        return degrade(mapped(), value, chipIndex);"""
    assert header.count(scalar) == 1
    assert header.count("u32 word = self.hidden.nibble(mapped & ~3);") == 1
    assert implementation.count("auto RDRAM::Writable::translate(u32 address) -> maybe<u32>") == 1
    assert implementation.count("return n * 2_MiB + (address & 0x1f'ffff);") == 1
    assert implementation.count("auto RDRAM::Writable::degrade(u32 address, u64 value, u32 chipIndex) -> u64") == 1
    assert implementation.count("if(chip.cci >= chip.ccHigh) return value;") == 1
    assert implementation.count("if(chip.cci <= chip.ccLow) return 0;") == 1


def worker():
    builder, original_builder, patched_builder = load_patched_builder()
    assert builder.REV == PIN
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=builder.REF, text=True).strip() == PIN
    source_guard(builder.REF)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    driver = Path(__file__).with_name("driver.cpp")
    baseline = builder.build(
        driver.with_name("baseline.cpp"), OUTPUT / "baseline",
        raw_fetch_access=True, physical_fetch_access=True, extra_sources=(driver,)
    )
    original_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    original = json.loads(original_raw)

    exe = builder.build(
        driver, OUTPUT / "sensor",
        raw_fetch_access=True, physical_fetch_access=True,
        rdram_scalar_access=True,
        extra_sources=(Path(__file__).with_name("observer.hpp"),)
    )
    raws = [subprocess.check_output([str(exe), mode], text=True, timeout=30) for mode in ("plain", "traced", "traced")]
    plain, traced, repeat = [json.loads(raw) for raw in raws]

    assert raws[1] == raws[2]
    assert original["results"] == plain["results"] == traced["results"] == repeat["results"]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert plain["translated_reads"] == []

    results = traced["results"]
    assert len(results) == 10
    assert results[0] == 0xF0F0AA55
    assert results[1] == 0x11223344
    assert results[2] == 0xDEADBEEF
    assert results[3] == 0
    assert 0 < results[4] < 0xFFFFFFFF
    assert 0 < results[5] < 0xFFFFFFFF
    assert results[6] == 0 and results[7] == 0
    assert results[8] == 0x11223344

    events = traced["translated_reads"]
    assert len(events) == 6
    expected = [
        (0x000000, 0x200000, 1, 0xF0F0AA55, 0xF0F0AA55, 63),
        (0x200000, 0x000000, 0, 0x11223344, 0x11223344, 63),
        (0x000004, 0x200004, 1, 0xDEADBEEF, 0xDEADBEEF, 63),
        (0x000008, 0x200008, 1, 0xFFFFFFFF, 0x00000000, 8),
    ]
    for event, want in zip(events[:4], expected):
        request, mapped, chip, raw, delivered, cci = want
        assert (event["request"], event["mapped"], event["chip"], event["raw"], event["delivered"], event["cci"]) == want
        assert event["bytes"] == 4 and event["cc_low"] == 8 and event["cc_high"] == 16
    partial = events[4]
    assert (partial["request"], partial["mapped"], partial["chip"], partial["raw"], partial["cci"], partial["cc_low"], partial["cc_high"]) == (
        0x00000C, 0x20000C, 1, 0xFFFFFFFF, 12, 8, 16
    )
    assert partial["delivered"] == results[4]
    assert 0 < partial["delivered"] < partial["raw"]
    partial2 = events[5]
    assert (partial2["request"], partial2["mapped"], partial2["chip"], partial2["raw"], partial2["cci"], partial2["cc_low"], partial2["cc_high"]) == (
        0x000010, 0x200010, 1, 0xFFFFFFFF, 12, 8, 16
    )
    assert partial2["delivered"] == results[5]
    assert 0 < partial2["delivered"] < partial2["raw"]

    # A second stochastic degradation makes observer-induced RNG consumption externally visible.
    # Baseline/plain/traced state+results equality above therefore checks RNG neutrality too.

    # Equal payload cannot identify the source: both request-address backing and mapped backing hold DEADBEEF.
    backing_request_decoy = 0xDEADBEEF
    assert events[2]["raw"] == backing_request_decoy == results[2]
    assert events[2]["mapped"] != events[2]["request"]

    assert traced["state"]["count"] == 0
    assert traced["state"]["ri_error"] == 1

    manifest = {
        "pin": PIN,
        "original_builder_sha256": hashlib.sha256(original_builder.encode()).hexdigest(),
        "patched_builder_sha256": hashlib.sha256(patched_builder.encode()).hexdigest(),
        "driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
        "observer_sha256": hashlib.sha256(Path(__file__).with_name("observer.hpp").read_bytes()).hexdigest(),
        "results_sha256": hashlib.sha256(raws[1].encode()).hexdigest(),
        "event_count": len(events),
        "partial_delivered": partial["delivered"],
        "second_partial_delivered": partial2["delivered"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(traced, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(traced, indent=2, sort_keys=True))
    print("PASS: successful translated scalar reads identify mapped backing bytes separately from post-CCI delivered values; failures, identity reads, and EBus reads do not fabricate this witness")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
