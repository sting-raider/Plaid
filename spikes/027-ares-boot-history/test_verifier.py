"""Adversarial wire/context checks; these synthetic rows are not CPU evidence."""
from pathlib import Path
import copy
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    spec = importlib.util.spec_from_file_location("history",Path(__file__).with_name("run.py"))
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    fetch_header = {"record":"header","format":"plaid-ares-fetch-research-v5","revision":model.REV,
        "rom_sha256":model.ROM_SHA,"budget":1,"initial_state":"cpu_power_pif_entry",
        "mapped_cartridge_size":2742280,"source_policy":"delegated_rom_halves_before_prologue",
        "boot_inputs":model.PROFILE,"cache_policy":"selected_icache_line_at_prologue"}
    header = {"record":"header","format":"plaid-ares-access-history-v0","revision":model.REV,
        "rom_sha256":model.ROM_SHA,"budget":1,"mapped_cartridge_size":2742280,
        "firmware_sha256":model.FW_SHA,"policy":"identity_ram_successful_access_and_fetch_boundaries",
        "lifecycle_policy":"single_run_no_host_restore","paired_fetch_format":"plaid-ares-fetch-research-v5"}
    pc = 0xffffffffa0001000
    scalar = {"record":"scalar","ordinal":1,"context":0,"pc":pc,"write":False,
              "address":0x2000,"aligned_address":0x2000,"bytes":4,"device":3,"value":0}
    begin = {"record":"fetch_begin","ordinal":2,"context":2,"pc":pc,"vaddr":pc,
             "translated":0x1000,"bus":0x1000,"cached":False,"value":0}
    read = dict(scalar,ordinal=3,context=2,address=0x1000,aligned_address=0x1000)
    end = dict(begin,record="fetch_end",ordinal=4)
    fetch = {"record":"fetch","ordinal":5,"context":0,"pc":pc,"fetch_context":2,
             "fetch_seq":0,"word":0,"physical":0x1000,"cached":False}
    footer = {"record":"end","record_count":5,"fetch_count":1,"reason":"instruction_call_budget"}
    rows = [header,scalar,begin,read,end,fetch,footer]
    original = [fetch_header,{"record":"fetch","seq":0,"pc":pc,"word":0,"physical":0x1000,
                             "cached":False,"delay_slot":False,"source":{"kind":"unknown"}},
                {"record":"end","fetch_count":1,"reason":"instruction_call_budget"}]
    with tempfile.TemporaryDirectory(prefix="boot-history-check-",dir=ROOT/"target") as directory:
        history = Path(directory)/"history.ndjson"
        trace = Path(directory)/"fetch.ndjson"
        def write(path,records):
            path.write_text(''.join(json.dumps(row,separators=(",",":"))+"\n" for row in records),encoding="utf-8")
        write(trace,original)
        write(history,rows)
        receipt = model.verify(history,trace,1)
        assert receipt["scalar_fetch_witnesses"] == 1 and receipt["outside_uncached_cpu_reads"] == 1
        # An equal-valued second eligible read inside the access is ambiguity,
        # even when its address does not match. It must remove the witness.
        ambiguous = copy.deepcopy(rows)
        ambiguous.insert(4,dict(scalar,ordinal=4,context=2))
        for ordinal,row in enumerate(ambiguous[1:-1],1): row["ordinal"] = ordinal
        ambiguous[-1]["record_count"] = 6
        write(history,ambiguous)
        assert model.verify(history,trace,1)["scalar_fetch_witnesses"] == 0
        variants = []
        for index,field,value in ((2,"context",1),(3,"ordinal",2),(4,"bus",0x2000),
                                  (5,"fetch_context",1),(5,"word",4),(6,"record_count",4),
                                  (0,"policy","unverified"),(3,"extra",1)):
            altered = copy.deepcopy(rows)
            altered[index][field] = value
            variants.append(altered)
        variants.extend((rows[:-1],rows+[scalar]))
        for variant in variants:
            write(history,variant)
            try: model.verify(history,trace,1)
            except (AssertionError,StopIteration): continue
            raise AssertionError("malformed history accepted")
        write(history,rows)
        history.write_text(history.read_text(encoding="utf-8").replace('"ordinal":3','"ordinal":3,"ordinal":3'),encoding="utf-8")
        try: model.verify(history,trace,1)
        except AssertionError: pass
        else: raise AssertionError("duplicate wire key accepted")
    print("PASS: scalar decoy/context ambiguity and eleven malformed history variants; wire checks only")


if __name__ == "__main__": main()
