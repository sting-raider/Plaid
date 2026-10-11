"""Finite actual-decoder composition; storage generations are not ROM ancestry."""
import copy

FIELDS = {'kind','ordinal','context','pc','phase','word','address','bank','offset',
    'bytes','value','cpu','next','halted','vector_byte','gpr','rgpr'}
CPU_WORDS = {2:0x8e080000,3:0xae081000,5:0x8e080000,6:0xae081004,
    7:0xae090000,11:0x8e080000,12:0x8e090004,13:0xae081008,
    14:0x01404021,15:0xae08100c}
RSP_STORES = {1:(0xac220000,0,0x11223344,0),4:(0xac220000,0,0x11223344,0),
    9:((58<<26)|(1<<21)|(2<<16),2,0,0x77),10:(0xa0220000,3,0x22,0)}
CODE_PC = 0xffffffffa0006000
MASK64 = (1<<64)-1


def integer(value, bits):
    assert type(value) is int and 0 <= value < 1<<bits


def sign32(value):
    return (value if value < 1<<31 else value-(1<<32)) & MASK64


def fixture_events():
    """Independent instruction/effect census for these sixteen controlled phases."""
    events = []
    gpr = [0]*32
    gpr[16],gpr[9],gpr[10] = 0xffffffffa4000000,0xaabbccdd,0xaaee7722
    cpu_index = 0
    context = pc = word = 0
    rgpr = [0]*32

    def add(kind, phase, **changes):
        event = dict(kind=kind,ordinal=len(events)+1,context=context,pc=pc,
            phase=phase,word=word,address=0,bank=0,offset=0,bytes=0,value=0,
            cpu=kind.startswith('cpu_') or kind.startswith('sp_'),
            next=0,halted=False,vector_byte=0,gpr=[],rgpr=[])
        event.update(changes)
        events.append(event)
        return event

    for phase in range(1,17):
        if phase in RSP_STORES:
            word,base,scalar,vbyte = RSP_STORES[phase]
            rgpr[1],rgpr[2] = base,scalar
            pc,context = 0x100,len(events)+1
            add('rsp_begin',phase,next=pc,rgpr=rgpr[:],vector_byte=vbyte)
            payload = scalar.to_bytes(4,'big') if word>>26 == 0x2b else bytes([vbyte if word>>26==58 else scalar & 255])
            for index,value in enumerate(payload):
                add('rsp_sink',phase,address=base+index,offset=base+index,bytes=1,value=value)
            add('rsp_end',phase,next=0x104,rgpr=rgpr[:],vector_byte=vbyte)
            pc,word,context = 0x104,13,len(events)+1
            add('rsp_begin',phase,next=pc,rgpr=rgpr[:],vector_byte=vbyte)
            add('rsp_end',phase,next=0x108,halted=True,rgpr=rgpr[:],vector_byte=vbyte)
            context=word=0
        elif phase in CPU_WORDS:
            pc,word,context = CODE_PC+cpu_index*4,CPU_WORDS[phase],len(events)+1
            add('cpu_begin',phase,gpr=gpr[:])
            opcode,rt = word>>26,(word>>16)&31
            offset = word & 0xfff
            if opcode == 0x23:
                value = 0x11223344 if phase in (2,5) else 0xaaee7722
                add('sp_read',phase,address=0x04000000+offset,offset=offset,bytes=4,value=value)
                gpr[rt] = sign32(value)
            elif opcode == 0x2b:
                bank = (word>>12)&1
                value = gpr[rt] & 0xffffffff
                if bank == 0:
                    add('foreign_sink',phase,cpu=False,address=offset,offset=offset,bytes=4,value=value)
                add('sp_write',phase,address=0x04000000+(word & 0xffff),bank=bank,
                    offset=offset,bytes=4,value=value)
            else:
                assert phase==14
                gpr[8] = sign32(gpr[10]&0xffffffff)
            add('cpu_end',phase,gpr=gpr[:])
            cpu_index+=1
            context=word=0
            pc+=4
        elif phase==8:
            add('foreign_sink',phase,address=1,offset=1,bytes=1,value=0xee)
        else:
            assert phase==16
            add('sp_write',phase,address=0x04001010,bank=1,offset=16,bytes=4,value=0xaaee7722)
    assert len(events)==58
    return events


def replay(events, initial_dmem, initial_imem):
    assert type(events) is list and len(events)==58
    required = fixture_events()
    dmem,imem = bytearray(initial_dmem),bytearray(initial_imem)
    dorig,iorig = [None]*len(dmem),[None]*len(imem)
    register = {}
    active = None
    certificates = []
    previous_gpr = None
    for event,expected in zip(events,required):
        assert type(event) is dict and set(event)==FIELDS
        assert type(event['kind']) is str
        for field in FIELDS-{'kind','cpu','halted','gpr','rgpr'}:
            integer(event[field],64 if field in ('pc','value') else 32)
        for field in ('cpu','halted'):
            assert type(event[field]) is bool
        for field,bits in (('gpr',64),('rgpr',32)):
            assert type(event[field]) is list
            for value in event[field]:
                integer(value,bits)
        assert event==expected,(event,expected)
        kind,offset = event['kind'],event['offset']
        if kind=='cpu_begin':
            assert active is None
            if previous_gpr is not None:
                assert event['gpr']==previous_gpr
            active = dict(begin=event,read=None,write=None)
        elif kind=='rsp_sink' or kind=='foreign_sink':
            size = event['bytes']
            assert 0<=offset<offset+size<=len(dmem)
            dmem[offset:offset+size] = event['value'].to_bytes(size,'big')
            origin = dict(kind='rsp',context=event['context'],ordinal=event['ordinal']) if kind=='rsp_sink' else None
            dorig[offset:offset+size] = [origin]*size
        elif kind in ('sp_read','sp_write'):
            address = event['address']
            assert 0x04000000<=address<=0x0403ffff and address%4==0
            assert event['bank']==(address>>12)&1 and offset==address & 0xffc
            if active:
                begin = active['begin']
                assert all(event[f]==begin[f] for f in ('context','pc','word','phase'))
                word = begin['word']
                base,rt = (word>>21)&31,(word>>16)&31
                immediate = word & 0xffff
                if immediate & 0x8000:
                    immediate-=0x10000
                virtual = (begin['gpr'][base]+immediate) & MASK64
                assert 0xffffffffa4000000<=virtual<=0xffffffffa403ffff
                assert virtual & 0x1fffffff==address
                if kind=='sp_read':
                    assert word>>26==0x23 and event['bank']==0 and rt!=0
                    assert event['value']==int.from_bytes(dmem[offset:offset+4],'big')
                    assert active['read'] is None
                    active['read'] = dict(context=begin['context'],read_ordinal=event['ordinal'],
                        register=rt,bits=sign32(event['value']),ancestry=copy.deepcopy(dorig[offset:offset+4]))
                else:
                    assert word>>26==0x2b and event['value']==begin['gpr'][rt] & 0xffffffff
                    assert active['write'] is None
                    active['write'] = event
            else:
                assert kind=='sp_write' and event['context']==0
            if kind=='sp_write':
                backing,orig = (imem,iorig) if event['bank'] else (dmem,dorig)
                assert offset+4<=len(backing)
                backing[offset:offset+4] = event['value'].to_bytes(4,'big')
                origin = dict(kind='cpu',context=event['context'],ordinal=event['ordinal']) if active else None
                orig[offset:offset+4] = [origin]*4
                if active and event['bank'] and rt in register:
                    source = register[rt]
                    assert begin['gpr'][rt]==source['bits']
                    certificates.append(dict(phase=event['phase'],sink_context=begin['context'],
                        sink_ordinal=event['ordinal'],offset=offset,value=event['value'],source=copy.deepcopy(source)))
        elif kind=='cpu_end':
            assert active
            begin = active['begin']
            after = begin['gpr'][:]
            word = begin['word']
            if word>>26==0x23:
                source = active['read']
                assert source and active['write'] is None
                after[source['register']] = source['bits']
                register[source['register']] = source
            elif word>>26==0x2b:
                assert active['write'] and active['read'] is None
            else:
                assert word==0x01404021 and active['read'] is active['write'] is None
                after[8] = sign32(after[10]&0xffffffff)
                register.pop(8,None)  # A same-value definition cuts the old copy.
            assert event['gpr']==after
            previous_gpr = after
            active = None
    assert active is None
    assert [c['phase'] for c in certificates]==[3,6,13]
    first,second,mixed = certificates
    assert first['value']==second['value'] and first['source']['ancestry']!=second['source']['ancestry']
    assert [None if x is None else x['kind'] for x in mixed['source']['ancestry']]==['cpu',None,'rsp','rsp']
    assert mixed['source']['context']==44 and mixed['sink_context']==50
    assert iorig[16:20]==[None]*4
    naive = max(e['ordinal'] for e in events if e['kind']=='sp_read'
        and e['ordinal']<mixed['sink_ordinal'] and e['value']==mixed['value'])
    assert naive==48 and naive!=mixed['source']['read_ordinal']
    return dict(scope='finite_actual_rsp_dmem_cpu_imem_composition',records=len(events),
        certificates=certificates,final_dmem=list(dmem),final_imem=list(imem),
        naive_latest_equal_read_ordinal=naive,
        resident_writer_ordinals=[None if x is None else x['ordinal'] for x in iorig],
        source_ancestry_certified=False,mutation_coverage_certified=False,
        executable_lifetime_certified=False,native_complete=False)


def verify(data):
    assert set(data)=={'initial_dmem','initial_imem','events','steps','state','checkpoints','final_dmem','final_imem'}
    for field,length in (('initial_dmem',8),('final_dmem',8),('initial_imem',20),('final_imem',20)):
        assert type(data[field]) is list and len(data[field])==length
        for value in data[field]:
            integer(value,8)
    assert data['initial_dmem']==list(bytes.fromhex('340800aaaaee7722'))
    assert data['initial_imem']==list(bytes.fromhex('deadbeef')*5)
    assert type(data['checkpoints']) is list and len(data['checkpoints'])==16
    assert all(type(x) is str for x in data['checkpoints'])
    summary = replay(data['events'],data['initial_dmem'],data['initial_imem'])
    assert data['final_dmem']==summary.pop('final_dmem')==list(bytes.fromhex('aaee7722aaee7722'))
    assert data['final_imem']==summary.pop('final_imem')==list(bytes.fromhex('1122334411223344aaee7722aaee7722aaee7722'))
    # Independent baseline step snapshots project onto actual decoder snapshots.
    begins = [e for e in data['events'] if e['kind']=='cpu_begin']
    ends = [e for e in data['events'] if e['kind']=='cpu_end']
    assert len(data['steps'])==len(begins)==len(ends)==10
    for index,(step,begin,end) in enumerate(zip(data['steps'],begins,ends)):
        assert set(step)=={'phase','index','word','pc','before','after'}
        for f in ('phase','index','word','pc'):
            integer(step[f],64 if f=='pc' else 32)
        for f in ('before','after'):
            assert type(step[f]) is list and len(step[f])==32
            for value in step[f]:
                integer(value,64)
        assert step==dict(phase=begin['phase'],index=index,word=begin['word'],pc=begin['pc'],before=begin['gpr'],after=end['gpr'])
    return summary


def reject_forgeries(data):
    histories = []
    for field,value in [('address',0x04001080),('bank',0),('offset',4096),('context',0),
            ('word',0),('cpu',False),('ordinal',True),('bytes',1),('extra',0)]:
        forged = copy.deepcopy(data)
        next(e for e in forged['events'] if e['kind']=='sp_write' and e['phase']==3)[field]=value
        histories.append(forged)
    for phase,register,value in ((3,8,1<<40),(2,16,0xffffffff84000000),(13,8,0xaaee7722)):
        forged = copy.deepcopy(data)
        event = next(e for e in forged['events'] if e['kind']=='cpu_begin' and e['phase']==phase)
        event['gpr'][register] = value
        histories.append(forged)
    for phase,kind,field,value in ((4,'rsp_sink','context',0),(9,'rsp_begin','vector_byte',0),
            (8,'foreign_sink','offset',4),(12,'cpu_begin','word',0x8e080004),
            (14,'cpu_begin','word',0),(16,'sp_write','context',50)):
        forged = copy.deepcopy(data)
        next(e for e in forged['events'] if e['kind']==kind and e['phase']==phase)[field]=value
        histories.append(forged)
    forged = copy.deepcopy(data)
    forged['events'].pop(15)
    histories.append(forged)
    forged = copy.deepcopy(data)
    forged['final_imem'][8]^=1
    histories.append(forged)
    for forged in histories:
        try:
            verify(forged)
        except AssertionError:
            continue
        raise AssertionError('forged composition accepted')
    return len(histories)
