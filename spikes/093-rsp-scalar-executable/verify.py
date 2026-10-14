"""Independent rooted scalar replay, sharing no Rust verifier implementation."""
import hashlib
import json


def inspect(rows):
    parents=[None]*32
    pending=None
    boundary=None
    epoch=0
    count=defined=opaque=roots=0
    samples=[]
    digest=hashlib.sha256()
    def commit(value):digest.update(json.dumps(value,separators=(',',':')).encode())
    for row in rows:
        kind=row['record']
        if kind=='rsp_operand_root':
            assert pending is None and row['epoch']>epoch
            epoch=row['epoch'];parents=[None]*32
            boundary=(row['registers'],row['rsp_pc']);roots+=1
            commit(['root',row['ordinal'],epoch,row['rsp_pc'],row['registers']])
        elif kind=='rsp_instruction' and row['begin']:
            assert pending is None and epoch and boundary==(row['registers'],row['rsp_pc'])
            before=row['registers'];word=row['word'];rs=(word>>21)&31;rt=(word>>16)&31
            scalar=word>>26==13 or (word>>26==0 and word&63==33 and (word>>6)&31==0)
            def parent(r):
                if r==0:return {'kind':'architectural_zero'}
                if parents[r] is not None:return {'kind':'definition','context':parents[r]}
                return {'kind':'captured_input','register':r,'value':before[r]}
            definition=None
            after=list(before) if scalar else None
            if scalar:
                destination=rt if word>>26==13 else (word>>11)&31
                if destination:
                    value=(before[rs]|(word&65535)) if word>>26==13 else ((before[rs]+before[rt])&0xffffffff)
                    expression={'kind':'ori','source':parent(rs),'immediate':word&65535} if word>>26==13 else {'kind':'addu','left':parent(rs),'right':parent(rt)}
                    definition=dict(context=row['ordinal'],phase=0,pc=row['rsp_pc'],word=word,register=destination,value=value,expression=expression)
                    after[destination]=value
            else:parents=[None]*32
            pending=(row,before,after,definition)
        elif kind=='rsp_instruction':
            begin,before,after,definition=pending;pending=None
            assert row['registers'][0]==0 and (after is None or after==row['registers'])
            count+=1;opaque+=int(after is None)
            commit(['instruction',epoch,begin['ordinal'],begin['read_ordinal'],row['ordinal'],begin['word'],row['next_pc'],before,row['registers'],definition])
            if definition:
                parents[definition['register']]=definition['context'];defined+=1
                if len(samples)<64:samples.append(dict(epoch=epoch,read_ordinal=begin['read_ordinal'],end_ordinal=row['ordinal'],definition=definition))
            boundary=(row['registers'],row['next_pc'])
    assert pending is None
    return dict(roots=roots,instructions=count,definitions=defined,opaque_instructions=opaque,samples=samples,ordered_producers_sha256=digest.hexdigest())
