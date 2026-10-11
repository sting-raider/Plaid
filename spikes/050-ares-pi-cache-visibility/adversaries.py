"""Forge measured records rather than inferring a certificate from final bits."""
import copy
from verify import verify


def check(data):
    verify(data)
    rejected=[]
    mutations=(
        ('wrong_source_tail','pi_source_half',2,'value',0xffff,1),
        ('wrong_source_offset','pi_source_half',8,'offset',0x1000,0),
        ('shifted_write_tail','pi_rdram_write',2,'address',0x4040,4),
        ('wrong_write_tail','pi_rdram_write',8,'value',255,4),
        ('wrong_fetch_physical','fetch_end',1,'translated',0x8000,0),
        ('uncached_fetch_claim','fetch_end',4,'cached',False,0),
        ('completion_promotes_stale','fetch_end',4,'value',0x34081111,0),
        ('backing_promotes_stale','fetch_end',9,'value',0x34083333,0),
        ('wrong_fill_tail','icache_fill',6,'words',[0x34081111]+[1]*7,0),
        ('wrong_completion_label','pi_completion',3,'transfer',2,0))
    for name,kind,stage,key,value,index in mutations:
        forged=copy.deepcopy(data)
        selected=[e for e in forged['events'] if e['kind']==kind and e['stage']==stage]
        selected[index][key]=value
        try: verify(forged)
        except AssertionError: rejected.append(name)
        else: raise AssertionError('accepted measured forgery: '+name)
    return rejected
