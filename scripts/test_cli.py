"""Exercise normalized ROM -> CFG/indirect targets -> map -> fail-closed report."""
from pathlib import Path
import json
import re
import hashlib
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    subprocess.run([cargo,"build","--quiet","-p","plaid"],cwd=ROOT,check=True)
    exe = ROOT / "target/debug" / ("plaid.exe" if os.name == "nt" else "plaid")
    with tempfile.TemporaryDirectory(prefix="cli-",dir=ROOT / "target") as directory:
        directory = Path(directory)
        canonical = bytearray(4096)
        canonical[:4] = bytes.fromhex("80371240")
        canonical[8:12] = (0x80000000).to_bytes(4,"big")
        words = [0x3c088000,0x35080020,0x01000008,0,0,0,0,0,0x08000008,0]
        canonical[64:104] = b"".join(w.to_bytes(4,"big") for w in words)
        v = b"".join(canonical[i:i+2][::-1] for i in range(0,len(canonical),2))
        n = b"".join(canonical[i:i+4][::-1] for i in range(0,len(canonical),4))
        def run(*args,ok=True):
            result = subprocess.run([str(exe),*map(str,args)],capture_output=True,text=True)
            assert (result.returncode == 0) == ok,(args,result.stdout,result.stderr)
            return result.stdout
        registers=[0]*32
        registers[16]=0xffffffffa0001000; registers[17]=0xffffffffa0002000
        loaded=registers.copy(); loaded[8]=0xffffffff89abcdef
        def instruction(begin,ordinal,context,pc,word,gpr):
            return dict(begin=begin,ordinal=ordinal,context=context,phase=1,pc=pc,word=word,gpr=gpr)
        pc=0xffffffffa0006000
        copy_history=dict(format='plaid-cpu-copy-history-v0',instruction_events=[
            instruction(True,1,1,pc,0x8e080000,registers),
            instruction(False,3,1,pc,0x8e080000,loaded),
            instruction(True,4,4,pc+4,0xae280000,loaded),
            instruction(False,6,4,pc+4,0xae280000,loaded)],scalar_events=[
                dict(ordinal=2,context=1,phase=1,pc=pc,write=False,address=0x1000,
                    bytes=4,uncached_cpu=True,value=0x89abcdef),
                dict(ordinal=5,context=4,phase=1,pc=pc+4,write=True,address=0x2000,
                    bytes=4,uncached_cpu=True,value=0x89abcdef)])
        source=directory/'copy-history.json'; source.write_bytes(json.dumps(copy_history).encode())
        source_bytes=source.read_bytes(); receipt=hashlib.sha256(source_bytes).hexdigest()
        copy_report=directory/'copy-report.json'
        run('inspect-cpu-copy-history',source,receipt,copy_report)
        run('verify-cpu-copy-history',source,receipt,copy_report)
        report=json.loads(copy_report.read_bytes())
        assert len(report['witnesses'])==1 and report['witnesses'][0]['read_ordinal']==2
        assert report['native_complete'] is False
        run('inspect-cpu-definitions',source,receipt,copy_report,ok=False)
        definition_source=directory/'definitions.json'
        copy_history['format']='plaid-cpu-word-definitions-v0'
        definition_source.write_bytes(json.dumps(copy_history).encode())
        definition_receipt=hashlib.sha256(definition_source.read_bytes()).hexdigest()
        definition_report=directory/'definitions-report.json'
        run('inspect-cpu-definitions',definition_source,definition_receipt,definition_report)
        run('verify-cpu-definitions',definition_source,definition_receipt,definition_report)
        run('inspect-cpu-copy-history',definition_source,definition_receipt,copy_report,ok=False)
        run('verify-cpu-copy-history',definition_source,definition_receipt,definition_report,ok=False)
        run('verify-cpu-definitions',source,receipt,copy_report,ok=False)
        run('inspect-cpu-copy-history',source,'f'*64,copy_report,ok=False)
        run('inspect-cpu-copy-history',source,receipt,source,ok=False)
        assert source.read_bytes()==source_bytes
        report['witnesses']=[]; copy_report.write_bytes(json.dumps(report).encode())
        run('verify-cpu-copy-history',source,receipt,copy_report,ok=False)
        source.write_bytes(b'{"format":"plaid-cpu-copy-history-v0","instruction_events":[],"scalar_events":[]}')
        run('inspect-cpu-copy-history',source,receipt,copy_report,ok=False)
        identities=[]; maps=[]
        for suffix,data in [("z64",canonical),("v64",v),("n64",n)]:
            rom = directory / ("synthetic." + suffix); rom.write_bytes(data)
            identities.append(json.loads(run("rom-info",rom))["identity"])
            output = directory / (suffix + ".json")
            run("discover",rom,"64","0x80000000","40","0x80000000",output)
            run("check-map",output)
            maps.append(output.read_bytes())
            report=json.loads(run("solve",rom,output))
            assert report["status"] == "open" and report["native_complete"] is False
            assert not any(b["kind"] in {"missing_instruction_source","unresolved_indirect_target","unresolved_indirect_site"} for b in report["blockers"])
            assert any(b["kind"] == "unproven_executable_universe" for b in report["blockers"])
        assert identities[0] == identities[1] == identities[2]
        assert maps[0] == maps[1] == maps[2]
        # Preserve expectations before submitting editable maps/sources. The CLI
        # must enforce the stronger installed-entry check as well as raw facts.
        header=dict(schema_version=0,rom=identities[0],engine='cli-source-test',
                    revision='r1',capabilities=[])
        trace_events=[
            dict(event='compile_begin',unit=1,start=0x80000000,
                 physical_start=None,delay_slot_entry=False),
            dict(event='entry_installed',unit=1,pc=0x80000000,register_mask=0),
            dict(event='unit_compiled',unit=1,start=0x80000000,words=words),
            dict(event='cpu_word_store_observed',site=0x80000000,
                 destination=0x80001000,value=0)]
        def save_trace(path,events):
            records=[dict(record='header',header=header)]
            records += [dict(record='event',seq=i,data=data) for i,data in enumerate(events)]
            records.append(dict(record='end',event_count=len(events)))
            path.write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
        traced=directory/'source.ndjson'; save_trace(traced,trace_events)
        trace_map=directory/'trace-map.json'
        expectations=directory/'expected.json'
        rom=directory/'synthetic.z64'
        run('create-trace-expectations',expectations,traced)
        preserved=expectations.read_bytes()
        run('create-trace-expectations',expectations,traced,ok=False)
        assert expectations.read_bytes()==preserved
        source_before=traced.read_bytes()
        run('create-trace-expectations',traced,traced,ok=False)
        assert traced.read_bytes()==source_before
        run('import-trace',rom,traced,trace_map)
        admitted=json.loads(run('solve-traces',rom,trace_map,expectations,traced))
        assert admitted['format']=='plaid-discovery-source-solve-v0'
        assert admitted['closure']['status']=='open'
        assert admitted['closure']['native_complete'] is False
        assert len(admitted['discovery_sources']['sessions'])==1
        run('solve-traces',rom,trace_map,expectations,ok=False)
        original_map=trace_map.read_bytes()
        edited=json.loads(original_map); edited['word_store_observations']=[]
        edited['executable_writes']=[]; edited['unresolved']=[]
        trace_map.write_text(json.dumps(edited),encoding='utf-8')
        run('solve-traces',rom,trace_map,expectations,traced,ok=False)
        edited=json.loads(original_map)
        # Map entries serialize as keyed pairs; remove the install event's use
        # while leaving its metadata and all primitive facts intact.
        for entry in edited['entries']:
            entry[1]=[ref for ref in entry[1] if not ref.endswith(':1')]
        trace_map.write_text(json.dumps(edited),encoding='utf-8')
        run('solve-traces',rom,trace_map,expectations,traced,ok=False)
        trace_map.write_bytes(original_map)
        shortened=directory/'edited-source.ndjson'; save_trace(shortened,trace_events[:-1])
        run('solve-traces',rom,trace_map,expectations,shortened,ok=False)
        unexpected=directory/'unexpected.ndjson'; save_trace(unexpected,trace_events[:-1])
        run('solve-traces',rom,trace_map,expectations,traced,unexpected,ok=False)
        assert expectations.read_bytes()==preserved
        no_install=directory/'no-install.ndjson'
        save_trace(no_install,[trace_events[0],trace_events[2]])
        compile_expected=directory/'compiled-expected.json'
        compile_map=directory/'compiled-map.json'
        run('create-trace-expectations',compile_expected,no_install)
        run('import-trace',rom,no_install,compile_map)
        run('solve-traces',rom,compile_map,compile_expected,no_install)
        deleted=json.loads(compile_map.read_bytes())
        for field in ('entries','blocks','regions','direct_edges','indirect_sites','unresolved'):
            deleted[field]=[]
        compile_map.write_text(json.dumps(deleted),encoding='utf-8')
        run('solve-traces',rom,compile_map,compile_expected,no_install,ok=False)
        # n64sym signature identification feeds runtime declarations (ADR-0133)
        import zlib
        # 12 bytes, over a 44-byte window: an 8-byte signature must also start
        # a plausible function, which `j .` after `jr t0` is not (ADR-0183)
        body=b"".join(w.to_bytes(4,"big") for w in words[8:10])+bytes(4)
        sig=directory/'lib.sig'
        sig.write_text(f"# sig_v1\n\nosGetCount 0xC 0x{zlib.crc32(body[:8]):08X} 0x{zlib.crc32(body):08X}\n",encoding='utf-8')
        found=json.loads(run('identify',rom,"64","0x80000000","44",sig))
        assert found['format']=='plaid-runtime-functions-v0' and found['ambiguous']==[]
        assert [(f['entry'],f['name']) for f in found['functions']]==[('0x80000020','osGetCount')]
        # identify scans the composite: a load copying the same relocation-free
        # body is the same function at a second address (ADR-0171)
        ident_loads=directory/'ident-loads.json'
        ident_loads.write_text(json.dumps(dict(format='plaid-loads-v0',source='cli test',
            loads=[dict(destination='0x8000002c',size='0xc',rom='96',encoding='raw')])),encoding='utf-8')
        both=json.loads(run('identify',rom,"64","0x80000000","44",sig,"--loads",ident_loads))
        assert [(f['entry'],f['name']) for f in both['functions']]==[('0x80000020','osGetCount'),
            ('0x8000002c','osGetCount')] and both['ambiguous']==[],both
        declared=directory/'runtime.json'; declared.write_text(json.dumps(found),encoding='utf-8')
        runtime_map=directory/'runtime-map.json'
        run("discover",rom,"64","0x80000000","40","0x80000000",runtime_map,declared)
        assert len(json.loads(runtime_map.read_bytes())['runtime_functions'])==1
        # heuristic data-pointer roots only add discovery roots (ADR-0152)
        rooted=directory/'rooted-map.json'
        run("discover",rom,"64","0x80000000","40","0x80000000",rooted,"--data-roots")
        assert len(json.loads(rooted.read_bytes())['blocks'])>=len(json.loads(runtime_map.read_bytes())['blocks'])
        # address-taken functions are recorded and select their own scope (ADR-0153)
        taken=directory/'taken-map.json'
        run("discover",rom,"64","0x80000000","40","0x80000000",taken,"--address-taken")
        assert len(json.loads(taken.read_bytes())['blocks'])>=len(json.loads(runtime_map.read_bytes())['blocks'])
        assert json.loads(run("solve",rom,taken,"--address-taken"))['status']=='closed'
        # the COP1 register mode is a declared map property (ADR-0160)
        fr0_map=directory/'fr0-map.json'
        run("discover",rom,"64","0x80000000","40","0x80000000",fr0_map,"--fr0")
        assert json.loads(fr0_map.read_bytes())['cop1_fr0'] is True
        assert 'cop1_fr0' not in json.loads(taken.read_bytes())
        # a closed ROM map lowers to C; an OPEN one is refused (ADR-0157)
        lowered=directory/'taken.c'
        run("lower-map",rom,taken,"0x80000000","0x80000f00",lowered)
        assert 'plaid_run' in lowered.read_text(encoding='utf-8')
        # --parts moves every function body out of the main unit; the units
        # link with the runtime into one program (ADR-0174)
        run("lower-map",rom,taken,"0x80000000","0x80000f00",directory/'split.c',"--parts","3")
        units=[directory/'split.c',*sorted(directory.glob('split.part*.c'))]
        body=re.compile(r'^(?:static )?int (F_[0-9a-f]{8})\(.*\{$',re.M)
        defined=[body.findall(u.read_text(encoding='utf-8')) for u in units]
        assert len(units)>1 and not defined[0]
        assert sorted(sum(defined[1:],[]))==sorted(body.findall(lowered.read_text(encoding='utf-8')))
        cc=os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
        if cc:
            objects=[]
            for u in units[1:]:
                objects.append(u.with_suffix('.o'))
                subprocess.run([cc,'-std=gnu11','-Wall','-Werror','-Wno-unused-label','-Wno-unused-function',
                                '-DPLAID_SAFEPOINTS','-c',str(u),'-o',str(objects[-1])],check=True)
            subprocess.run([cc,'-std=gnu11','-DPLAID_SAFEPOINTS','-DPLAID_LOWERED="split.c"','-I',str(directory),
                            str(ROOT/'runtime/plaid_rt.c'),*map(str,objects),'-pthread','-o',str(directory/'split.exe')],check=True)
        run("lower-map",rom,runtime_map,"0x80000000","0x80000f00",directory/'open.c',ok=False)
        # declared loads (ADR-0136): the composite is rebuilt by solve
        loads=directory/'loads.json'
        def declare(destination):
            loads.write_text(json.dumps(dict(format='plaid-loads-v0',source='cli test',
                loads=[dict(destination=destination,size='0x8',rom='64',encoding='raw')])),encoding='utf-8')
        declare('0x80000028')
        load_map=directory/'load-map.json'
        run("discover",rom,"64","0x80000000","40","0x80000000",load_map,"--loads",loads)
        assert len(json.loads(load_map.read_bytes())['load_images'])==1
        guarded=json.loads(run("solve",rom,load_map,"--guarded-ram"))
        assert any('declared load' in a for a in guarded['assumptions'])
        # a disjoint load leaves a hole in the composite (ADR-0150)
        declare('0x80000040')
        run("discover",rom,"64","0x80000000","40","0x80000000",load_map,"--loads",loads)
        assert len(json.loads(load_map.read_bytes())['load_images'])==1
        json.loads(run("solve",rom,load_map,"--guarded-ram"))
        run("solve",rom,load_map,"--loads",loads,ok=False)
        # a reference symbol map can name runtime functions instead (ADR-0148)
        symbol_ref=directory/'symbols.txt'
        symbol_ref.write_text("osGetCount = 0x80000020; // type:func\n"
            "osSendMesg = 0x80000008; // type:func\nosSendMesg = 0x80000010; // type:func\n",encoding='utf-8')
        named=json.loads(run('identify',rom,"64","0x80000000","40",symbol_ref,"--symbols"))
        assert [(f['entry'],f['name']) for f in named['functions']]==[('0x80000020','osGetCount')]
        assert named['ambiguous']==['osSendMesg'] and 'symbol map' in named['source'],named
        # the map completes signatures only where the ROM leaves a name open, and
        # the solver lists what rests on it (ADR-0171)
        symbol_ref.write_text("osGetCount = 0x80000020; // type:func\nosInitialize = 0x80000008; // type:func\n",
            encoding='utf-8')
        mixed=json.loads(run('identify',rom,"64","0x80000000","44",sig,"--reference-map",symbol_ref))
        assert [(f['entry'],f['name'],f['evidence']) for f in mixed['functions']]==[
            ('0x80000008','osInitialize','reference map'),('0x80000020','osGetCount','signature')],mixed
        declared.write_text(json.dumps(mixed),encoding='utf-8')
        mixed_map=directory/'mixed-map.json'
        run("discover",rom,"64","0x80000000","40","0x80000000",mixed_map,declared)
        notes=json.loads(run("solve",rom,mixed_map,"--guarded-ram"))['assumptions']
        assert any('reference symbol map' in a and '(osInitialize)' in a for a in notes),notes
        run('identify',rom,"64","0x80000000","40",symbol_ref,"--symbols","--reference-map",symbol_ref,ok=False)
        sig.write_text("osGetCount 0x8\n",encoding='utf-8')
        run('identify',rom,"64","0x80000000","44",sig,ok=False)
        # recall against a reference linker map (ADR-0144)
        ref=directory/'ref.map'
        ref.write_text(" .text          0x0000000080000000       0x28 main.o\n"
            "                0x0000000080000000                entry\n"
            "                0x0000000080000020                osGetCount\n"
            "                0x0000000080000024                never_called\n",encoding='utf-8')
        score=json.loads(run('recall',runtime_map,ref))
        assert score['format']=='plaid-recall-v0' and score['reference_functions']==3 and score['matched']==2,score
        assert [m['name'] for m in score['missed']]==['never_called'] and not score['meets_target']
        assert json.loads(run('recall',runtime_map,ref,'0x80000000','0x80000024'))['meets_target']
        run('recall',runtime_map,sig,ok=False)
        merged=directory / "merged.json"
        run("merge",directory/"z64.json",directory/"v64.json",merged)
        assert merged.read_bytes() == maps[0]
        m=json.loads(maps[0]); assert len(m["blocks"]) == 2
        assert m["indirect_sites"][0]["closed_proof"] is not None
        bad=directory/"malformed.z64"; bad.write_bytes(b"bad")
        run("rom-info",bad,ok=False)
        run("unknown-command",ok=False)
        changed=bytearray(canonical); changed[64] ^= 1
        bad.write_bytes(changed)
        run("solve",bad,directory/"z64.json",ok=False)
    from test_overlays import main as test_overlays
    test_overlays()
    from test_runtime_bindings import main as test_runtime_bindings
    test_runtime_bindings()
    print("CLI pipeline: all byte orders, deterministic maps, target traversal, identity gates and OPEN whole-ROM reports passed")

if __name__ == "__main__":
    main()
