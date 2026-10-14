"""Independent rooted scalar replay, sharing no Rust verifier implementation."""
import hashlib
import json


def inspect(rows,stores=False):
    parents=[None]*32
    pending=None
    boundary=None
    epoch=0
    count=defined=opaque=roots=0
    samples=[]
    digest=hashlib.sha256()
    store_report=dict(instructions=0,effects=0,samples=[])
    store_pending=None
    scope_active=None
    def commit(value):digest.update(json.dumps(value,separators=(',',':')).encode())
    for row in rows:
        kind=row['record']
        if kind=='rsp_operand_root':
            assert pending is None and row['epoch']>epoch
            epoch=row['epoch'];parents=[None]*32
            boundary=(row['registers'],row['rsp_pc']);roots+=1
            commit(['root',row['ordinal'],epoch,row['rsp_pc'],row['registers']])
        elif kind=='rsp_scalar_store_scope':
            assert stores and pending and store_pending
            instruction=pending[0]['ordinal']
            assert row['instruction_context']==instruction and row['kind']==store_pending['kind'] and not store_pending['closed']
            if row['begin']:
                assert scope_active is None and row['store_scope']==row['ordinal'];scope_active=row['ordinal'];store_pending['sample']['scope_ordinal']=scope_active
            else:
                assert scope_active==row['store_scope'] and len(store_pending['sample']['effects'])==len(store_pending['lanes'])
                store_pending['closed']=True;store_pending['sample']['scope_end_ordinal']=row['ordinal'];scope_active=None
            commit(['store_scope',row['ordinal'],row['begin'],row['kind'],row['instruction_context'],row['store_scope']])
        elif kind=='rsp_dmem_effect' and stores and row['store_scope']:
            assert scope_active==row['store_scope'] and store_pending and not store_pending['closed']
            index=len(store_pending['sample']['effects']);assert row['bytes']==1
            assert (row['offset'],row['value'])==store_pending['lanes'][index]
            store_pending['sample']['effects'].append([row['ordinal'],row['offset'],row['value']])
            commit(['store_effect',row['ordinal'],row['store_scope'],row['offset'],row['bytes'],row['value']])
        elif kind=='rsp_instruction' and row['begin']:
            assert pending is None and epoch and boundary==(row['registers'],row['rsp_pc'])
            before=row['registers'];word=row['word'];rs=(word>>21)&31;rt=(word>>16)&31
            arithmetic=word>>26==13 or (word>>26==0 and word&63==33 and (word>>6)&31==0)
            store=stores and word>>26 in (0x28,0x29,0x2b)
            scalar=arithmetic or (stores and word==0) or store
            def parent(r):
                if r==0:return {'kind':'architectural_zero'}
                if parents[r] is not None:return {'kind':'definition','context':parents[r]}
                return {'kind':'captured_input','register':r,'value':before[r]}
            definition=None
            after=list(before) if scalar else None
            if arithmetic:
                destination=rt if word>>26==13 else (word>>11)&31
                if destination:
                    value=(before[rs]|(word&65535)) if word>>26==13 else ((before[rs]+before[rt])&0xffffffff)
                    expression={'kind':'ori','source':parent(rs),'immediate':word&65535} if word>>26==13 else {'kind':'addu','left':parent(rs),'right':parent(rt)}
                    definition=dict(context=row['ordinal'],phase=0,pc=row['rsp_pc'],word=word,register=destination,value=value,expression=expression)
                    after[destination]=value
            if store:
                width={0x28:1,0x29:2,0x2b:4}[word>>26];kind={1:0,2:1,4:2}[width]
                imm=word&65535;imm=imm-65536 if imm&32768 else imm
                address=(before[rs]+imm)&0xffffffff
                lanes=[((address+i)&4095,(before[rt]>>(8*(width-1-i)))&255) for i in range(width)]
                sample=dict(instruction_context=row['ordinal'],read_ordinal=row['read_ordinal'],epoch=epoch,scope_ordinal=0,scope_end_ordinal=0,register=rt,value_source=parent(rt),address_source=parent(rs),effects=[])
                store_pending=dict(kind=kind,lanes=lanes,sample=sample,closed=False)
            else:store_pending=None
            if not scalar:parents=[None]*32
            pending=(row,before,after,definition)
        elif kind=='rsp_instruction':
            begin,before,after,definition=pending;pending=None
            assert row['registers'][0]==0 and (after is None or after==row['registers'])
            if store_pending:
                assert store_pending['closed'] and scope_active is None
                store_report['instructions']+=1;store_report['effects']+=len(store_pending['sample']['effects'])
                if len(store_report['samples'])<64:store_report['samples'].append(store_pending['sample'])
                store_pending=None
            count+=1;opaque+=int(after is None)
            commit(['instruction',epoch,begin['ordinal'],begin['read_ordinal'],row['ordinal'],begin['word'],row['next_pc'],before,row['registers'],definition])
            if definition:
                parents[definition['register']]=definition['context'];defined+=1
                if len(samples)<64:samples.append(dict(epoch=epoch,read_ordinal=begin['read_ordinal'],end_ordinal=row['ordinal'],definition=definition))
            boundary=(row['registers'],row['next_pc'])
    assert pending is None
    result=dict(roots=roots,instructions=count,definitions=defined,opaque_instructions=opaque,samples=samples,ordered_producers_sha256=digest.hexdigest())
    if stores:result['stores']=store_report
    return result
