#!/usr/bin/env python3
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib, json

WORD = 0x34081234

def be_bytes(v:int): return [(v >> s) & 0xff for s in (24,16,8,0)]
def be_word(mem, addr):
    return (mem[addr]<<24)|(mem[addr+1]<<16)|(mem[addr+2]<<8)|mem[addr+3]

class ReplayError(AssertionError): pass

@dataclass
class Cell:
    value:int
    writer:str
    origin:str|None

@dataclass
class Reg:
    value:int
    definition:str
    source_writers:tuple[str,...]|None
    origins:tuple[str|None,...]|None


def history(active_source=0x2000):
    return [
      {"ordinal":1,"kind":"rdram_read","request":"dmaA","addr":0x1000,"value":WORD,"success":True},
      {"ordinal":2,"kind":"dma_sink","request":"dmaA","source_addr":0x1000,"source_read":1,"dest":0x100,"value":WORD},
      {"ordinal":3,"kind":"rdram_read","request":"dmaB","addr":active_source,"value":WORD,"success":True},
      {"ordinal":4,"kind":"dma_sink","request":"dmaB","source_addr":active_source,"source_read":3,"dest":0x100,"value":WORD},
      # equal-valued source read that is real but belongs to no sink in this chain
      {"ordinal":5,"kind":"rdram_read","request":"decoy","addr":0x3000,"value":WORD,"success":True},
      {"ordinal":6,"kind":"cpu_seed_word","producer":"copy-decoy","dest":0x300,"value":WORD},
      {"ordinal":7,"kind":"rsp_lw","reg":"r2","addr":0x100,"value":WORD},
      {"ordinal":8,"kind":"rsp_sw","reg":"r2","dest":0x200,"value":WORD},
      {"ordinal":9,"kind":"cpu_lw","reg":"t0","addr":0x200,"value":WORD},
      {"ordinal":10,"kind":"cpu_lw","reg":"t1","addr":0x300,"value":WORD},
      {"ordinal":11,"kind":"cpu_sw_imem","reg":"t0","dest":0x000,"value":WORD},
      {"ordinal":12,"kind":"rsp_fetch","pc":0x000,"value":WORD},
      # same-value RSP store: fresh destination generation, same ultimate source
      {"ordinal":13,"kind":"rsp_sw","reg":"r2","dest":0x200,"value":WORD},
      {"ordinal":14,"kind":"cpu_lw","reg":"t0","addr":0x200,"value":WORD},
      {"ordinal":15,"kind":"cpu_sw_imem","reg":"t0","dest":0x004,"value":WORD},
      {"ordinal":16,"kind":"rsp_fetch","pc":0x004,"value":WORD},
      # same-value direct overwrite of one DMEM byte cuts only that lane's DMA origin
      {"ordinal":17,"kind":"cpu_dmem_byte","producer":"cpu-patch","dest":0x102,"value":0x12},
      {"ordinal":18,"kind":"rsp_lw","reg":"r2","addr":0x100,"value":WORD},
      {"ordinal":19,"kind":"rsp_sw","reg":"r2","dest":0x204,"value":WORD},
      {"ordinal":20,"kind":"cpu_lw","reg":"t0","addr":0x204,"value":WORD},
      {"ordinal":21,"kind":"cpu_sw_imem","reg":"t0","dest":0x008,"value":WORD},
      {"ordinal":22,"kind":"rsp_fetch","pc":0x008,"value":WORD},
      # completed sink with no successful backing read: content known, origin unknown
      {"ordinal":23,"kind":"dma_sink","request":"dmaOOB","source_addr":0x800000,"source_read":None,"dest":0x108,"value":0},
      {"ordinal":24,"kind":"rsp_lw","reg":"r3","addr":0x108,"value":0},
      {"ordinal":25,"kind":"rsp_sw","reg":"r3","dest":0x208,"value":0},
      {"ordinal":26,"kind":"cpu_lw","reg":"t0","addr":0x208,"value":0},
      {"ordinal":27,"kind":"cpu_sw_imem","reg":"t0","dest":0x00c,"value":0},
      {"ordinal":28,"kind":"rsp_fetch","pc":0x00c,"value":0},
      # same-value whole-GPR writer severs the RSP load ancestry
      {"ordinal":29,"kind":"rsp_lw","reg":"r4","addr":0x100,"value":WORD},
      {"ordinal":30,"kind":"rsp_reg_write","reg":"r4","op":"ori_same_value","value":WORD},
      {"ordinal":31,"kind":"rsp_sw","reg":"r4","dest":0x20c,"value":WORD},
      {"ordinal":32,"kind":"cpu_lw","reg":"t0","addr":0x20c,"value":WORD},
      {"ordinal":33,"kind":"cpu_sw_imem","reg":"t0","dest":0x010,"value":WORD},
      {"ordinal":34,"kind":"rsp_fetch","pc":0x010,"value":WORD},
    ]


def replay(events):
    ords=[e['ordinal'] for e in events]
    if ords != list(range(1,len(events)+1)): raise ReplayError('non-contiguous chronology')
    dmem={}
    imem={i:Cell(0,f'initial-imem:{i}',None) for i in range(0x20)}
    reads={}
    rsp_regs={}
    cpu_regs={}
    rsp_stores=[]; copies=[]; fetches=[]; dma=[]
    for e in events:
        o=e['ordinal']; k=e['kind']
        if k=='rdram_read':
            if not e['success']: raise ReplayError('fixture only records successful read facts')
            reads[o]=e
        elif k=='dma_sink':
            vals=be_bytes(e['value']); sr=e['source_read']
            origins=[None]*4
            if sr is not None:
                r=reads.get(sr)
                if r is None or sr>=o: raise ReplayError('missing/late DMA source read')
                if (r['request'],r['addr'],r['value']) != (e['request'],e['source_addr'],e['value']):
                    raise ReplayError('DMA source/sink causal mismatch')
                origins=[f"rdram:{sr}:{e['source_addr']+i:08x}" for i in range(4)]
            writer=f'dma-sink:{o}'
            for i,b in enumerate(vals): dmem[e['dest']+i]=Cell(b,writer,origins[i])
            dma.append({'ordinal':o,'writer':writer,'source_read':sr,'origins':origins.copy()})
        elif k=='cpu_seed_word':
            writer=f"cpu-dmem:{e['producer']}:{o}"
            for i,b in enumerate(be_bytes(e['value'])): dmem[e['dest']+i]=Cell(b,writer,writer)
        elif k=='cpu_dmem_byte':
            old=dmem.get(e['dest'])
            if old is None or old.value!=e['value']: raise ReplayError('same-value CPU patch precondition failed')
            lab=f"cpu-dmem:{e['producer']}:{o}"
            dmem[e['dest']]=Cell(e['value'],lab,lab)
        elif k=='rsp_lw':
            try: cells=[dmem[e['addr']+i] for i in range(4)]
            except KeyError as ex: raise ReplayError('RSP load from unknown DMEM') from ex
            v=sum(c.value << s for c,s in zip(cells,(24,16,8,0)))
            if v!=e['value']: raise ReplayError('RSP load payload mismatch')
            rsp_regs[e['reg']]=Reg(v,f'rsp-load:{o}',tuple(c.writer for c in cells),tuple(c.origin for c in cells))
        elif k=='rsp_reg_write':
            rsp_regs[e['reg']]=Reg(e['value'],f"rsp-{e['op']}:{o}",None,None)
        elif k=='rsp_sw':
            r=rsp_regs.get(e['reg'])
            if r is None or r.value!=e['value']: raise ReplayError('RSP store register mismatch')
            writer=f'rsp-store:{o}'
            origins=r.origins if r.origins is not None else (None,)*4
            for i,b in enumerate(be_bytes(e['value'])): dmem[e['dest']+i]=Cell(b,writer,origins[i])
            rsp_stores.append({'ordinal':o,'writer':writer,'source_definition':r.definition,'source_writers':list(r.source_writers) if r.source_writers else None,'origins':list(origins)})
        elif k=='cpu_lw':
            try: cells=[dmem[e['addr']+i] for i in range(4)]
            except KeyError as ex: raise ReplayError('CPU load from unknown DMEM') from ex
            v=sum(c.value << s for c,s in zip(cells,(24,16,8,0)))
            if v!=e['value']: raise ReplayError('CPU load payload mismatch')
            cpu_regs[e['reg']]=Reg(v,f'cpu-load:{o}',tuple(c.writer for c in cells),tuple(c.origin for c in cells))
        elif k=='cpu_sw_imem':
            r=cpu_regs.get(e['reg'])
            if r is None or r.value!=e['value']: raise ReplayError('CPU IMEM store register mismatch')
            resident=f'imem-write:{o}'
            origins=r.origins if r.origins is not None else (None,)*4
            for i,b in enumerate(be_bytes(e['value'])): imem[e['dest']+i]=Cell(b,resident,origins[i])
            copies.append({'ordinal':o,'source_definition':r.definition,'source_writers':list(r.source_writers) if r.source_writers else None,'resident':resident,'origins':list(origins)})
        elif k=='rsp_fetch':
            cells=[imem[e['pc']+i] for i in range(4)]
            v=sum(c.value << s for c,s in zip(cells,(24,16,8,0)))
            if v!=e['value']: raise ReplayError('RSP fetch payload mismatch')
            fetches.append({'ordinal':o,'pc':e['pc'],'value':v,'residents':[c.writer for c in cells],'origins':[c.origin for c in cells]})
        else: raise ReplayError(k)
    return {'dma':dma,'rsp_stores':rsp_stores,'copies':copies,'fetches':fetches}


def verify(r):
    f={x['ordinal']:x for x in r['fetches']}
    # Pure chain must root in second, same-value DMA reload, not the old reload or decoy read.
    assert f[12]['origins']==[f'rdram:3:{0x2000+i:08x}' for i in range(4)]
    # Same-value RSP rewrite changes storage generation while retaining ultimate ancestry.
    c11=next(c for c in r['copies'] if c['ordinal']==11); c15=next(c for c in r['copies'] if c['ordinal']==15)
    assert c11['source_writers']==['rsp-store:8']*4 and c15['source_writers']==['rsp-store:13']*4
    assert f[16]['origins']==f[12]['origins']
    # Partial same-value CPU overwrite cuts only byte lane 2 upstream.
    assert f[22]['origins'][:2]==f[12]['origins'][:2]
    assert f[22]['origins'][2]=='cpu-dmem:cpu-patch:17'
    assert f[22]['origins'][3]==f[12]['origins'][3]
    # Missing source read remains UNKNOWN through both transforms/copies.
    assert f[28]['origins']==[None]*4
    # Same-value RSP register writer cuts ancestry rather than repairing it by value.
    assert f[34]['origins']==[None]*4


def downstream_projection(r):
    return {
      'rsp_stores':[{'ordinal':x['ordinal'],'writer':x['writer']} for x in r['rsp_stores']],
      'copies':[{'ordinal':x['ordinal'],'resident':x['resident']} for x in r['copies']],
      'fetches':[{'ordinal':x['ordinal'],'pc':x['pc'],'value':x['value'],'residents':x['residents']} for x in r['fetches']],
    }


def rejects(mut):
    try:
        rr=replay(mut); verify(rr); return False
    except (ReplayError,AssertionError,KeyError): return True


def main():
    base=history(); r=replay(base); verify(r)
    # Second valid history: identical downstream writer/resident identities/payloads, different RDRAM origin.
    alt=replay(history(0x4000)); verify_alt=alt['fetches'][0]['origins']==[f'rdram:3:{0x4000+i:08x}' for i in range(4)]
    assert verify_alt
    assert downstream_projection(r)==downstream_projection(alt)
    assert r['fetches'][0]['origins']!=alt['fetches'][0]['origins']

    forged=[]
    m=deepcopy(base); m[3]['source_read']=1; forged.append(('stale_equal_dma_source',rejects(m)))
    m=deepcopy(base); m[3]['source_read']=5; forged.append(('future_equal_decoy_source',rejects(m)))
    m=deepcopy(base); m[2]['addr']=0x2004; forged.append(('dma_read_address_drift',rejects(m)))
    m=deepcopy(base); del m[2];
    for i,e in enumerate(m,1): e['ordinal']=i
    # Renumbering also leaves source_read pointer stale/mismatched and must fail.
    forged.append(('deleted_dma_source_read',rejects(m)))
    m=deepcopy(base); m[9]['reg']='t0'; forged.append(('equal_cpu_decoy_clobbers_source_reg',rejects(m)))
    m=deepcopy(base); m[29]['reg']='r5'; forged.append(('missing_same_value_rsp_clobber',rejects(m)))
    m=deepcopy(base); m[16]['dest']=0x103; forged.append(('partial_overwrite_wrong_lane',rejects(m)))
    m=deepcopy(base); m[18]['reg']='r3'; forged.append(('rsp_store_wrong_live_generation',rejects(m)))
    assert all(ok for _,ok in forged), forged

    flat = deepcopy(r['fetches'][0]); flat['origins']=[r['fetches'][0]['origins'][0]]*4
    assert flat['origins'] != r['fetches'][0]['origins'] or len(set(r['fetches'][0]['origins']))==1
    # The pure first chain has four lane-distinct RDRAM byte origins, so flattening loses identity even though one read produced them.
    assert len(set(r['fetches'][0]['origins']))==4

    out={
      'status':'VALIDATED_BOUNDED_COMPOSITION',
      'event_count':len(base),
      'first_fetch_origins':r['fetches'][0]['origins'],
      'same_value_rsp_rewrite_origins':next(x for x in r['fetches'] if x['ordinal']==16)['origins'],
      'partial_overwrite_origins':next(x for x in r['fetches'] if x['ordinal']==22)['origins'],
      'unknown_ingress_origins':next(x for x in r['fetches'] if x['ordinal']==28)['origins'],
      'rsp_clobber_cut_origins':next(x for x in r['fetches'] if x['ordinal']==34)['origins'],
      'projection_collision':True,
      'alternate_first_fetch_origins':alt['fetches'][0]['origins'],
      'forged_histories_rejected':[name for name,ok in forged if ok],
    }
    blob=json.dumps(out,sort_keys=True,separators=(',',':')).encode()
    print(json.dumps(out,sort_keys=True))
    print('RESULT_SHA256='+hashlib.sha256(blob).hexdigest())
    print('PASS: exact causal ancestry survives DMA->RSP load/store->CPU copy->IMEM; UNKNOWN and same-value generation cuts remain explicit')

if __name__=='__main__': main()
