"""Independent byte replay; captured writers remain distinct from ROM roots."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def inspect(events):
    path=ROOT/'spikes/093-rsp-scalar-executable/verify.py'
    s=importlib.util.spec_from_file_location('scalar',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    scalar=m.inspect(events,stores=True);actors={}
    # This independent fixture oracle deliberately rejects sample truncation.
    assert scalar['stores']['instructions']==len(scalar['stores']['samples'])
    for store in scalar['stores']['samples']:
        source=store['value_source'];definition=source.get('context') if source['kind']=='definition' else None
        actor=dict(kind='rsp_scalar_sink',instruction_context=store['instruction_context'],read_ordinal=store['read_ordinal'],
            epoch=store['epoch'],scope_ordinal=store['scope_ordinal'],register=store['register'],source_definition=definition)
        for ordinal,offset,value in store['effects']:actors[ordinal]=actor
    sp={};ram={};pending={};samples=[];digest=hashlib.sha256();read_receipts=[]
    def backing(memory,address,values):
        result=[]
        for n,value in enumerate(values):
            if address+n in memory and memory[address+n][0]!=value:memory.pop(address+n)
            result.append(memory.get(address+n,(0,None))[1])
        return result
    for i,e in enumerate(events):
        kind=e['record'];ordinal=e.get('ordinal')
        if kind=='sp_word':
            start=e['bank']*4096+e['offset'];values=e['value'].to_bytes(4,'big')
            if e['write']:
                for n,value in enumerate(values):sp[start+n]=(value,dict(write_ordinal=ordinal,byte_index=n,kind=dict(kind='word_sink',cpu=e['cpu'])))
            else:backing(sp,start,values)
        elif kind=='sp_dma_store':
            matches=[r for r in read_receipts if (r.get('pc'),r['address'],r['bytes'],r['value'])==(e.get('pc'),e['dram'],e['bytes'],e['value'])]
            read=matches[0]['ordinal'] if len(matches)==1 else None
            if read is not None:read_receipts.remove(matches[0])
            for n,value in enumerate(e['value'].to_bytes(8,'big')[-e['bytes']:]):
                sp[e['bank']*4096+e['offset']+n]=(value,dict(write_ordinal=ordinal,byte_index=n,kind=dict(kind='dma_sink',dram=e['dram'],read_ordinal=read)))
        elif kind=='imem_storage_effect':
            start=4096+e['offset']
            for address in range(start,start+e['bytes']):sp.pop(address,None)
        elif kind=='rsp_dmem_effect':
            for n,value in enumerate(e['value'].to_bytes(8,'big')[-e['bytes']:]):
                address=e['offset']+n;sp.pop(address,None)
                if ordinal in actors:sp[address]=(value,dict(write_ordinal=ordinal,byte_index=n,kind=actors[ordinal]))
        elif kind=='sp_dma_egress_read':
            assert len(pending)<2 and ordinal not in pending
            assert (e['bank'],e['bytes']) in ((0,4),(1,8)) and e['offset']%e['bytes']==0 and e['offset']+e['bytes']<=4096
            assert e['dram']%e['bytes']==0 and e['dram']+e['bytes']<=8388608
            pending[ordinal]=(e,backing(sp,e['bank']*4096+e['offset'],e['value'].to_bytes(e['bytes'],'big')))
        elif kind=='sp_dma_egress_store':
            read,writers=pending.pop(e['read_ordinal']);write=events[i-1]
            assert write['ordinal']==e['write_ordinal']==ordinal-1 and write['record']=='scalar' and write['write'] and write['device']==4
            assert (write['address'],write.get('aligned_address',write['address']),write['bytes'],write['value'])==(read['dram'],read['dram'],read['bytes'],read['value'])
            receipt=dict(read_ordinal=read['ordinal'],write_ordinal=write['ordinal'],completion_ordinal=ordinal,
                dram=read['dram'],bank=read['bank'],offset=read['offset'],bytes=read['bytes'],value=read['value'],writers=writers)
            samples.append(receipt);digest.update(json.dumps(receipt,separators=(',',':')).encode()+b'\n')
            for n,(value,writer) in enumerate(zip(read['value'].to_bytes(read['bytes'],'big'),writers)):
                ram[read['dram']+n]=(value,None if writer is None else dict(read_ordinal=read['ordinal'],write_ordinal=write['ordinal'],
                    completion_ordinal=ordinal,bank=read['bank'],source_offset=read['offset']+n,writer=writer))
        elif kind=='scalar':
            if not e['write'] and e['device']==4:read_receipts.append(e)
            if e['write']:
                for address in range(e.get('aligned_address',e['address']),e.get('aligned_address',e['address'])+e['bytes']):ram.pop(address,None)
        elif kind=='storage_effect':
            if e['kind']==0:
                for address in range(e['address'],e['address']+e['bytes']):ram.pop(address,None)
            else:ram.clear()
        if kind not in ('storage_effect','sp_dma_store','rsp_dmem_effect','imem_storage_effect','rsp_operand_root','rsp_scalar_store_scope') and not (kind=='scalar' and not e['write'] and e['device']==4):
            read_receipts=[]
    assert not pending
    return dict(stores=len(samples),samples=samples[:64],ordered_stores_sha256=digest.hexdigest()),ram
