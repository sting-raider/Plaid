"""Original fail-closed replay of request, insertion, dispatch and status scopes."""
from pathlib import Path
import copy
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
FIELDS={"ordinal","phase","kind","subkind","slot","other","event","clock","valid","token","call","dram","pbus","length","lane","value"}
QUEUE_FIELDS={"ordinal","phase","kind","slot","other","event","clock","valid","token"}


def verify(events):
    spec=importlib.util.spec_from_file_location("plaid_queue_replay",ROOT/"spikes/032-ares-queue-identity/verify.py")
    queue=importlib.util.module_from_spec(spec); spec.loader.exec_module(queue)
    queue_events=[]
    for ordinal,e in enumerate(events,1):
        assert set(e)==FIELDS and type(e["valid"]) is bool
        assert all(type(e[k]) is int and e[k]>=0 for k in FIELDS-{"valid"})
        assert e["ordinal"]==ordinal and 1<=e["phase"]<=5 and 1<=e["kind"]<=15
        if e["kind"]<=9:
            q={k:e[k] for k in QUEUE_FIELDS}; q["ordinal"]=len(queue_events)+1
            queue_events.append(q)
    queue_summary=queue.verify(queue_events)
    calls={}; token_calls={}; canceled=set(); last=None; active=None; dispatch=None
    next_call=0; pending=None; statuses=[]; direct=0; unbound=0; attempt=None
    for e in events:
        kind=e["kind"]
        if last is not None: assert kind in (6,7,12), "valid removal was not consumed by the immediate dispatch"
        if dispatch is not None: assert kind==13 or (kind==14 and e["subkind"]==8)
        if kind==10:
            next_call+=1
            assert active is None and e["call"]==next_call and e["event"] in (0,1)
            active=e["call"]
            calls[active]=dict(direction=e["event"],inserted=None,token=None,writes=0)
        elif kind==11:
            assert active==e["call"] and calls[active]["direction"]==e["event"]
            assert calls[active]["inserted"] is not None and attempt is None
            active=None
        elif kind<=9:
            assert e["call"]==(active or 0)
            if kind in (2,4) and active:
                c=calls[active]
                assert c["inserted"] is None and c["direction"]==e["event"]
                c["inserted"]=kind==4
                if kind==4: c["token"]=e["token"]; token_calls[e["token"]]=active
            if kind==8 and e["token"]: canceled.add(e["token"])
            if kind==5:
                last=(e["token"],e["event"]) if e["valid"] else None
                pending=e["other"]  # Remaining heap repair follows before dispatch.
            if kind in (1,9): last=pending=None
        elif kind==12:
            assert active is None and dispatch is None and last==(e["token"],e["event"])
            assert e["token"] not in canceled and e["event"] in (0,1)
            dispatch=dict(token=e["token"],event=e["event"],statuses=0)
            pending=last=None
        elif kind==13:
            assert dispatch is not None and e["token"]==dispatch["token"] and e["event"]==dispatch["event"]
            assert dispatch["statuses"]==1
            dispatch=None
        elif kind==14:
            assert 1<=e["subkind"]<=8
            if e["subkind"]==8:
                assert e["lane"]==0 and e["value"]==1
                assert e["token"]==(dispatch["token"] if dispatch else 0)
                if dispatch:
                    dispatch["statuses"]+=1
                    call=token_calls.get(e["token"])
                    if call:
                        assert calls[call]["direction"]==dispatch["event"]
                        statuses.append(dict(call=call,token=e["token"],direction=dispatch["event"]))
                    else: unbound+=1
                else: direct+=1
            else:
                assert active==e["call"] and calls[active]["direction"]==1 and not e["token"]
                if e["subkind"]==4:
                    assert attempt is None
                    attempt=dict(call=active,dram=e["dram"],value=e["value"],lane=e["lane"],written=False)
                elif e["subkind"]==5:
                    assert attempt is not None and attempt["written"]
                    assert all(e[k]==attempt[k] for k in ("call","dram","value","lane"))
                    attempt=None
        else:
            assert kind==15 and active==e["call"] and calls[active]["direction"]==1
            assert e["length"]==1 and not e["token"] and e["dram"]<8388608 and e["value"]<256
            assert attempt is not None and not attempt["written"]
            assert all(e[k]==attempt[k] for k in ("call","dram","value"))
            attempt["written"]=True; calls[active]["writes"]+=1
    assert active is dispatch is attempt is None and next_call==5
    assert statuses==[dict(call=1,token=1,direction=1),dict(call=3,token=3,direction=0)]
    assert calls[2]["token"] in canceled and calls[4]["inserted"] is False
    assert [calls[i]["writes"] for i in range(1,6)]==[8,8,0,8,8]
    assert direct==1 and unbound==2
    return dict(requests=5,request_status_dispatch_links=statuses,
                canceled_request=2,rejected_request_with_byte_effects=4,
                successful_pi_byte_writes=32,unbound_cpu_status_callbacks=unbound,
                direct_status_calls_without_dispatch=direct,
                byte_transfer_occurs_at_dispatch=False,queue=queue_summary)


def counterexamples(events):
    for predicate,key,value in (
        (lambda e:e["kind"]==12,"token",9999),
        (lambda e:e["kind"]==12,"event",0),
        (lambda e:e["kind"]==14 and e["subkind"]==8,"token",0),
        (lambda e:e["kind"]==4 and e["call"]==1,"call",2),
        (lambda e:e["kind"]==15,"value",255),
        (lambda e:e["kind"]==10,"call",True),
    ):
        forged=copy.deepcopy(events)
        next(e for e in forged if predicate(e))[key]=value
        try: verify(forged)
        except AssertionError: pass
        else: raise AssertionError(("accepted forged dispatch join",key))
