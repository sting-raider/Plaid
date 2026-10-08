#!/usr/bin/env python3
"""Build exact pinned ares and exhaustively check SD/SDL/SDR mutation semantics."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / "target/ares-64bit-store-spike"

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mspec = importlib.util.spec_from_file_location("store_model", HERE / "model.py")
model = importlib.util.module_from_spec(mspec); mspec.loader.exec_module(model)

def invoke(exe, mode, op, endian, offset):
    raw = subprocess.check_output([str(exe),mode,op,endian,str(offset)], text=True, timeout=20)
    again = subprocess.check_output([str(exe),mode,op,endian,str(offset)], text=True, timeout=20)
    assert raw == again, (mode,op,endian,offset)
    return json.loads(raw)

def apply_expected(before, op, endian, offset):
    out = bytearray(before)
    model.apply(out, 0, model.subwrites(op,endian,offset), endian)
    return list(out)

def main():
    exe = mod.build(HERE / "driver.cpp", OUTPUT)
    results=[]
    for endian in ("big","little"):
      for op in ("SD","SDL","SDR"):
        for offset in range(8):
          for mode in ("uncached","cached"):
            state=invoke(exe,mode,op,endian,offset); results.append(state)
            before=state["before_guest"]
            expected=apply_expected(before,op,endian,offset)
            if op=="SD" and offset:
                assert state["exception"] == 5
                assert state["after_guest"] == before
                assert state["after_raw"] == state["before_raw"]
                assert state["dirty"] == 0
                continue
            assert state["exception"] == 0, state
            assert state["after_guest"] == expected, state
            if mode=="uncached":
                assert state["alias_after"] == expected
                assert state["dirty"] == 0
                assert state["after_raw"] != state["before_raw"]
            else:
                assert state["alias_after"] == before
                assert state["after_raw"] == state["before_raw"]
                assert state["dirty"] != 0

      for op in ("SD","SDL","SDR"):
        for offset in range(8):
          state=invoke(exe,"tlbmiss",op,endian,offset); results.append(state)
          assert state["after_raw"] == state["before_raw"] and state["dirty"] == 0
          if op=="SD" and offset:
              assert state["exception"] == 5
          else:
              assert state["exception"] == 3, state

      for target in range(1,8):
        state=invoke(exe,"pair","SDL",endian,target); results.append(state)
        assert state["exception"] == 0
        expected=model.DATA.to_bytes(8,endian)
        assert bytes(state["after_guest"][target:target+8]) == expected, state
        assert state["after_guest"][target-1] == state["before_guest"][target-1]
        assert state["after_guest"][target+8] == state["before_guest"][target+8]

    for endian in ("big","little"):
      for op in ("SDL","SDR"):
        for offset in range(8):
          lanes=[]
          for kind,off,_ in model.subwrites(op,endian,offset):
            n=model.SIZES[kind]; lanes += list(range(off,off+n))
          assert lanes and min(lanes)>=0 and max(lanes)<8 and len(lanes)==len(set(lanes))

    encoded=(json.dumps(results,sort_keys=True,separators=(",",":"))+"\n").encode()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest=hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {len(results)} repeated pinned-ares SD/SDL/SDR cases")
    print(f"results_sha256={digest}")

if __name__ == "__main__": main()
