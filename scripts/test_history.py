"""CLI inspection/rechecking boundaries using original synthetic source rows."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build",action="store_true",help="use an already built CLI while Windows has its executable open")
    options = parser.parse_args()
    cargo = os.environ.get("CARGO") or shutil.which("cargo") or str(Path.home()/".cargo/bin/cargo.exe")
    if not options.no_build:
        subprocess.run([cargo,"build","-p","plaid"],cwd=ROOT,check=True)
    exe = ROOT/("target/debug/plaid.exe" if os.name == "nt" else "target/debug/plaid")
    with tempfile.TemporaryDirectory(prefix="history-cli-",dir=ROOT/"target") as temporary:
        directory = Path(temporary)
        firmware = directory/"firmware.bin"
        firmware.write_bytes(bytes(1984))
        data = bytes.fromhex("80371240")+bytes(4092)
        revision = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
        rom_hash = hashlib.sha256(data).hexdigest()
        fw_hash = hashlib.sha256(firmware.read_bytes()).hexdigest()
        original = [{"record":"header","format":"plaid-ares-fetch-research-v5","revision":revision,
            "rom_sha256":rom_hash,"budget":2,"initial_state":"cpu_power_pif_entry","mapped_cartridge_size":4096,
            "source_policy":"delegated_rom_halves_before_prologue","cache_policy":"selected_icache_line_at_prologue",
            "boot_inputs":{"firmware_sha256":fw_hash,"firmware_size":1984,"region":"ntsc","cic":"CIC-NUS-6102",
                "rdram_size":8388608,"deterministic_entropy":True,"pif_processor":"reference_hle","pif_checksum_enforced":True}},
            {"record":"fetch","seq":0,"pc":0xffffffffbfc00000,"word":0,"delay_slot":False,
                "physical":0x1fc00000,"cached":False,"source":{"kind":"unknown"}},
            {"record":"fetch","seq":1,"pc":0xffffffffa0001000,"word":7,"delay_slot":False,
                "physical":0x1000,"cached":False,"source":{"kind":"unknown"}},
            {"record":"end","fetch_count":2,"reason":"instruction_call_budget"}]
        rows = [{"record":"header","format":"plaid-ares-access-history-v0","revision":revision,
            "rom_sha256":rom_hash,"budget":2,"mapped_cartridge_size":4096,"firmware_sha256":fw_hash,
            "policy":"identity_ram_successful_access_and_fetch_boundaries","lifecycle_policy":"single_run_no_host_restore",
            "paired_fetch_format":"plaid-ares-fetch-research-v5"}]
        for seq,context in ((0,1),(1,5)):
            fetch = original[seq+1]
            pc,pa,word = fetch["pc"],fetch["physical"],fetch["word"]
            if seq:
                rows.append(dict(record="scalar",ordinal=4,context=0,pc=pc,write=False,address=0x2000,
                    aligned_address=0x2000,bytes=4,device=3,value=word))
            begin = dict(record="fetch_begin",ordinal=context,context=context,pc=pc,vaddr=pc,
                         translated=pa,bus=pa,cached=False,value=0)
            rows.append(begin)
            if seq:
                rows.append(dict(record="scalar",ordinal=6,context=context,pc=pc,write=False,address=pa,
                    aligned_address=pa,bytes=4,device=3,value=word))
            rows.append(dict(begin,record="fetch_end",ordinal=len(rows),value=word))
            rows.append(dict(record="fetch",ordinal=len(rows),context=0,pc=pc,fetch_context=context,
                fetch_seq=seq,word=word,physical=pa,cached=False))
        rows.append(dict(record="end",record_count=8,fetch_count=2,reason="instruction_call_budget"))
        trace = directory/"fetch.ndjson"
        history = directory/"history.ndjson"
        def write(path,records):
            path.write_text(''.join(json.dumps(row)+"\n" for row in records),encoding="utf-8")
        write(trace,original)
        write(history,rows)
        def run(command,*args):
            return subprocess.run([str(exe),command,*map(str,args)],capture_output=True,text=True)
        reports = []
        for order in ("z64","v64","n64"):
            encoded = data if order == "z64" else b''.join(data[i:i+(2 if order == "v64" else 4)][::-1]
                for i in range(0,len(data),2 if order == "v64" else 4))
            rom = directory/f"original.{order}"
            rom.write_bytes(encoded)
            output = directory/f"{order}-report.json"
            inputs = (rom,firmware,trace,history)
            result = run("inspect-boot-history",*inputs,output)
            assert result.returncode == 0,result.stderr
            assert run("verify-boot-history",*inputs,output).returncode == 0
            report = json.loads(output.read_text())
            assert report["records"] == 8 and report["fetches"] == 2 and report["scalar_fetch_witnesses"] == 1
            assert report["outside_uncached_cpu_reads"] == 1 and report["scope"] == "finite_reference_access_inspection"
            reports.append(output.read_bytes())
            before = rom.read_bytes()
            assert run("inspect-boot-history",*inputs,rom).returncode != 0
            assert rom.read_bytes() == before
        assert reports[0] == reports[1] == reports[2]
        report["records"] += 1
        output.write_text(json.dumps(report),encoding="utf-8")
        assert run("verify-boot-history",*inputs,output).returncode != 0
        output.write_bytes(reports[-1])
        rows[4]["value"] = 123  # unused data payload; hash must still bind it
        write(history,rows)
        assert run("verify-boot-history",*inputs,output).returncode != 0
        write(history,rows[:-1])
        rejected = directory/"rejected.json"
        assert run("inspect-boot-history",*inputs,rejected).returncode != 0
        assert not rejected.exists()
        write(history,rows)
        changed_firmware = bytearray(firmware.read_bytes())
        changed_firmware[15] = 1
        firmware.write_bytes(changed_firmware)
        assert run("inspect-boot-history",*inputs,rejected).returncode != 0
        assert not rejected.exists()
    print("History CLI: canonical orders, causal/source rechecking, tamper/truncation/input gates and overwrite protection passed")


if __name__ == "__main__": main()
