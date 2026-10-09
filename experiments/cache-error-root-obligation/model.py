#!/usr/bin/env python3
import hashlib, json

EVIDENCE = {
    "target": "NEC VR4300",
    "manual": "U10504EJ7V0UM00 Appendix B.1.7 / Table B-1",
    "manual_cache_error_exception": "does_not_occur",
    "ares_pin": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "n64_systemtest_pin": "196f5421173220eb2f63a7a99c64795dc0ea0698",
}

def decide(evidence):
    # Fail closed: emulator silence alone never deletes a root obligation.
    if evidence.get("manual_cache_error_exception") == "does_not_occur" and evidence.get("target") == "NEC VR4300":
        return {"cache_error_root": "EXCLUDED_BY_TARGET_HARDWARE", "closed": True}
    return {"cache_error_root": "UNRESOLVED", "closed": False}

def main():
    positive = decide(EVIDENCE)
    assert positive == {"cache_error_root": "EXCLUDED_BY_TARGET_HARDWARE", "closed": True}

    forged = dict(EVIDENCE)
    forged.pop("manual_cache_error_exception")
    assert decide(forged) == {"cache_error_root": "UNRESOLVED", "closed": False}

    wrong_cpu = dict(EVIDENCE, target="generic MIPS III")
    assert decide(wrong_cpu) == {"cache_error_root": "UNRESOLVED", "closed": False}

    report = {
        "evidence": EVIDENCE,
        "valid_vr4300_certificate": positive,
        "emulator_silence_only": decide(forged),
        "generic_mips3": decide(wrong_cpu),
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print(raw)
    print("sha256=" + hashlib.sha256(raw.encode()).hexdigest())
    print("PASS: cache-error root exclusion is target-hardware-scoped and fails closed without that evidence")

if __name__ == "__main__":
    main()
