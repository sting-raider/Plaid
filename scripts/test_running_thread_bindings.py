"""Optional SDK metadata can be restored only from its original declaration."""
import json


def run_contract(run, directory):
    for service, symbol, field in [
        ('osGetThreadPri', '__osRunningThread', 'runtime_running_thread'),
        ('osSetEventMesg', '__osEventStateTab', 'runtime_kernel_global'),
        ('osCreateMesgQueue', '__osThreadTail', 'runtime_kernel_global'),
    ]:
        _contract(run, directory, service, symbol, field)


def _contract(run, directory, service, symbol, field):
    raw=bytearray(0x1100);raw[:4]=bytes.fromhex('80371240');raw[8:12]=(0x80000400).to_bytes(4,'big')
    words=[0x0c000108,0,0x08000104,0,0x1000ffff,0,0,0,0x03e00008,0]
    raw[0x1000:0x1000+len(words)*4]=b''.join(w.to_bytes(4,'big') for w in words)
    rom,decl,mapped,legacy,out=(directory/name for name in ['binding.z64','binding.runtime.json','binding.map.json','binding.legacy.json','binding.restored.json'])
    rom.write_bytes(raw)
    document=dict(format='plaid-runtime-functions-v0',source='synthetic SDK binding',functions=[dict(entry='0x80000420',name=service,size=8,callbacks=[],data_bindings={symbol:'0x80003000'})])
    decl.write_text(json.dumps(document))
    run('discover',rom,'0x1000','0x80000400',hex(len(words)*4),'0x80000400',mapped,decl)
    original=json.loads(mapped.read_text());old=dict(original);old.pop(field);legacy.write_text(json.dumps(old))
    run('bind-runtime-globals',rom,legacy,decl,out)
    assert json.loads(out.read_text())==original
    run('bind-runtime-globals',rom,out,decl,out)
    assert json.loads(out.read_text())==original
    for key,value in [('size',4),('name','osStartThread'),('data_bindings',{symbol:'0x80003004'})]:
        damaged=json.loads(json.dumps(document));damaged['functions'][0][key]=value
        bad=directory/'binding.bad-runtime.json';bad.write_text(json.dumps(damaged))
        run('bind-runtime-globals',rom,legacy,bad,out,ok=False)
    for change in ['size','name','evidence','missing']:
        damaged=json.loads(json.dumps(old))
        function=damaged['runtime_functions'][0][1]
        if change=='size':function['source_size']=4
        elif change=='name':function['name']='osStartThread'
        elif change=='evidence':function['evidence']=[]
        else:damaged['runtime_functions']=[]
        bad=directory/'binding.bad-map.json';bad.write_text(json.dumps(damaged))
        run('bind-runtime-globals',rom,bad,decl,out,ok=False)
    assert json.loads(out.read_text())==original
    conflicting=json.loads(json.dumps(original))
    binding=conflicting[field][0]
    if isinstance(binding[1], dict):
        key=next(iter(binding[1]));binding[1][key]=0x80003004
    else:binding[1]=0x80003004
    bad=directory/'binding.conflicting-map.json';bad.write_text(json.dumps(conflicting))
    run('bind-runtime-globals',rom,bad,decl,out,ok=False)
    for value in [None,False,1234]:
        bad_document=json.loads(json.dumps(document));bad_document['functions'][0]['data_bindings'][symbol]=value
        bad=directory/'binding.invalid-declaration.json';bad.write_text(json.dumps(bad_document))
        run('discover',rom,'0x1000','0x80000400',hex(len(words)*4),'0x80000400',mapped,bad,ok=False)
    duplicate=json.loads(json.dumps(document));duplicate['functions'].append(duplicate['functions'][0]);bad.write_text(json.dumps(duplicate))
    run('discover',rom,'0x1000','0x80000400',hex(len(words)*4),'0x80000400',mapped,bad,ok=False)
    print('PASS runtime metadata restoration: exact original declaration/source/ABI, idempotence and stale/foreign binding refusals')
