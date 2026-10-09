"""Reuse nine read adversaries and execute four no-effect PIF ROM write attempts."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
from run import load,ROOT,HERE

OUTPUT=ROOT/'target/ares-pif-word-component-spike'


def sources():
    path=ROOT/'experiments/pif-rom-backing/ares_driver.cpp'
    text=path.read_text(encoding='utf-8')
    text=text.replace('#include "../../spikes/003-ares-oracle/driver.cpp"',
        f'#include "{ROOT/"spikes/003-ares-oracle/driver.cpp"}"')
    marker='static u64 plaidBackingReads = 0;'
    assert text.count(marker)==1
    text=text.replace(marker,marker+'\nstatic u32 wordAttempts=0,attemptOffset=0,attemptValue=0;')
    marker='  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 5;'
    assert text.count(marker)==1
    injected='''  #if PLAID_PIF_WORD_SENSOR
  if(!std::getenv("PLAID_PIF_DISABLE")) {
    plaidCpuFetchObserver=plaidPifFetchBoundary;
    plaidPifWordObserver=[](bool write,u32 offset,u32 value) {
      if(write) { ++wordAttempts;attemptOffset=offset;attemptValue=value; }
      else plaidPifRomBackingRead(offset,value);
    };
  }
  #endif
'''
    text=text.replace(marker,marker+'\n'+injected)
    marker='  } else if(!strcmp(mode, "nonfetch_rom")) {'
    assert text.count(marker)==1
    extra='''  } else if(!strcmp(mode,"rom_equal_write") || !strcmp(mode,"rom_changed_write") || !strcmp(mode,"rom_mirror_write")) {
    pif.io.romLockout=0;
    u32 value=!strcmp(mode,"rom_equal_write") ? fw0 : fw0^0x10;
    pif.writeInt(!strcmp(mode,"rom_mirror_write") ? 0x1fcff803 : 0,value);
    returned=directFetch(0x1fc00000,false);
  } else if(!strcmp(mode,"locked_rom_write")) {
    pif.io.romLockout=1;pif.writeInt(0,fw0^0x10);pif.io.romLockout=0;
    returned=directFetch(0x1fc00000,false);
'''
    text=text.replace(marker,extra+marker)
    marker='  std::printf("{\\"mode\\":\\"%s\\",\\"returned\\":%u,\\"machine\\":{", mode, returned);'
    assert text.count(marker)==1
    text=text.replace(marker,'  auto romHash=nall::Hash::SHA256(std::span<const u8>{pif.rom.data,pif.rom.size}).digest();\n'+marker+
        '\n  std::printf("\\"pif_rom_sha256\\":\\"%s\\",",romHash.data());')
    marker='  std::printf("]}\\n");'
    assert text.count(marker)==1
    text=text.replace(marker,'  std::printf("],\\"write_attempts\\":%u,\\"attempt_offset\\":%u,\\"attempt_value\\":%u}\\n",wordAttempts,attemptOffset,attemptValue);')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    files=[]
    for enabled in (0,1):
        target=OUTPUT/('sensor.cpp' if enabled else 'baseline.cpp')
        target.write_text(f'#define PLAID_PIF_WORD_SENSOR {enabled}\n'+text,encoding='utf-8',newline='\n');files.append(target)
    return files,path


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True);return
    builder=load('pif_word_builder',ROOT/'spikes/003-ares-oracle/run.py')
    old=load('pif_word_previous',ROOT/'experiments/pif-rom-backing/run_ares.py')
    files,original=sources();extra=(original,Path(__file__))
    baseline=builder.build(files[0],OUTPUT/'baseline',extra_sources=extra)
    sensor=builder.build(files[1],OUTPUT/'sensor',raw_fetch_access=True,physical_fetch_access=True,
        fetch_boundary_access=True,pif_backing_access=True,extra_sources=extra)
    firmware=ROOT/'.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
    assert hashlib.sha256(firmware.read_bytes()).hexdigest()==old.KNOWN_NTSC_SHA256
    fw0=int.from_bytes(firmware.read_bytes()[:4],'big')
    modes=(*old.MODES,'rom_equal_write','rom_changed_write','rom_mirror_write','locked_rom_write')
    result={k:{} for k in ('baseline','disabled','instrumented','repeat')}
    for mode in modes:
        for key,exe in (('baseline',baseline),('disabled',sensor),('instrumented',sensor),('repeat',sensor)):
            env=dict(os.environ)
            if key=='disabled':env['PLAID_PIF_DISABLE']='1'
            else:env.pop('PLAID_PIF_DISABLE',None)
            raw=subprocess.check_output([str(exe),mode,str(firmware)],text=True,timeout=30,env=env)
            lines=raw.splitlines();records=[s for s in lines if s.startswith('{')]
            assert len(records)==1
            result[key][mode]=json.loads(records[0])
        a,b,c,d=(result[k][mode] for k in ('baseline','disabled','instrumented','repeat'))
        assert a['machine']==b['machine']==c['machine']==d['machine'] and a['returned']==b['returned']==c['returned']==d['returned']
        assert c==d and a['write_attempts']==b['write_attempts']==0
    old.verify(result,firmware=firmware)
    for mode in ('rom_equal_write','rom_changed_write','rom_mirror_write','locked_rom_write'):
        r=result['instrumented'][mode];changed=mode in ('rom_changed_write','rom_mirror_write')
        assert r['returned']==fw0
        assert r['machine']['pif_rom_sha256']==result['instrumented']['natural']['machine']['pif_rom_sha256']
        assert r['write_attempts']==(0 if mode=='locked_rom_write' else 1)
        assert r['attempt_offset']==0
        assert r['fetches'][0]['witness']==dict(kind='pif_rom',offset=0,word=r['returned'])
        if r['write_attempts']:assert r['attempt_value']==(fw0^0x10 if changed else fw0)
    path=OUTPUT/'results.json';path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS thirteen actual PIF read/write-attempt adversaries with independent baseline/disabled/repeat state',flush=True)


if __name__=='__main__':main()
