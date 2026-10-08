#!/usr/bin/env python3
from dataclasses import dataclass
import copy, hashlib, json, random

PI_DMA_READ = 0
PI_DMA_WRITE = 1
DUMMY = 99
CAPACITY = 512

@dataclass
class Entry:
    clock: int
    event: int
    valid: bool = True
    token: int = 0

class Queue:
    """Behavioral model of pinned nall priority_queue<u32[512]>."""
    def __init__(self, obs):
        self.clock = 0
        self.heap = []
        self.obs = obs
    @staticmethod
    def ge(x, y):
        return ((x - y) & 0xffffffff) < 0x7fffffff
    def insert(self, event, clocks):
        if len(self.heap) >= CAPACITY:
            self.obs.rejected(event, clocks)
            return False
        child = len(self.heap)
        self.heap.append(Entry(0, event, True, 0))
        clock = (clocks + self.clock) & 0xffffffff
        while child:
            parent = (child - 1) >> 1
            if self.ge(clock, self.heap[parent].clock): break
            self.heap[child] = copy.copy(self.heap[parent])
            self.obs.move(child, parent, self.heap[child])
            child = parent
        token = self.obs.inserted(child, event, clock)
        self.heap[child] = Entry(clock, event, True, token)
        return True
    def remove_first(self):
        assert self.heap
        event = self.heap[0].event
        valid = self.heap[0].valid
        token = self.obs.removing(0, self.heap[0])
        size = len(self.heap) - 1
        tail = self.heap[size]
        parent = 0
        while True:
            child = (parent << 1) + 1
            if child >= size: break
            if child + 1 < size and self.ge(self.heap[child].clock, self.heap[child+1].clock): child += 1
            if self.ge(self.heap[child].clock, tail.clock): break
            self.heap[parent] = copy.copy(self.heap[child])
            self.obs.move(parent, child, self.heap[parent])
            parent = child
        if size:
            self.heap[parent] = copy.copy(tail)
            self.obs.move(parent, size, self.heap[parent])
        self.heap.pop()
        return (event, token) if valid else None
    def remove_event(self, event):
        cycles = 0
        for i, e in enumerate(self.heap):
            if e.event == event:
                self.obs.cancel(i, e)
                e.valid = False
                cycles = max(cycles, (e.clock - self.clock) & 0xffffffff)
        return cycles
    def step(self, clocks, callback):
        self.clock = (self.clock + clocks) & 0xffffffff
        while self.heap and self.ge(self.clock, self.heap[0].clock):
            out = self.remove_first()
            if out is not None:
                event, token = out
                callback(event, token)
    def serialize_boundary(self):
        self.obs.serialize()
        for e in self.heap: e.token = 0

class Observer:
    def __init__(self):
        self.next_token = 0
        self.current_request = None
        self.records = []
        self.request_by_token = {}
        self.certified = []
        self.unknown_completions = []
        self.canceled = set()
        self.epoch = 0
    def rec(self, kind, **kw): self.records.append(dict(n=len(self.records)+1, kind=kind, epoch=self.epoch, **kw))
    def begin_request(self, rid, event):
        assert self.current_request is None
        self.current_request = (rid, event)
        self.rec('request', rid=rid, event=event)
    def end_request(self): self.current_request = None
    def inserted(self, slot, event, clock):
        self.next_token += 1
        token = self.next_token
        self.rec('insert', token=token, event=event, slot=slot, clock=clock)
        if self.current_request:
            rid, expected = self.current_request
            assert expected == event
            self.request_by_token[token] = (rid, event, self.epoch)
            self.rec('request_insert', rid=rid, token=token, event=event)
        return token
    def rejected(self, event, clocks):
        rid = self.current_request[0] if self.current_request else None
        self.rec('reject', rid=rid, event=event, clocks=clocks)
    def move(self, dst, src, e): self.rec('move', token=e.token, event=e.event, dst=dst, src=src, valid=e.valid)
    def removing(self, slot, e):
        self.rec('remove', token=e.token, event=e.event, slot=slot, valid=e.valid)
        return e.token
    def cancel(self, slot, e):
        self.rec('cancel', token=e.token, event=e.event, slot=slot, valid=e.valid)
        if e.token: self.canceled.add(e.token)
    def serialize(self):
        self.rec('serialize')
        self.epoch += 1
        self.request_by_token.clear()
    def dispatch(self, event, token):
        self.rec('dispatch', token=token, event=event)
        req = self.request_by_token.get(token)
        if token and token not in self.canceled and req and req[1] == event and req[2] == self.epoch:
            return req
        return None
    def completion(self, event, token, req):
        self.rec('completion', token=token, event=event, rid=req[0] if req else None)
        if req:
            self.certified.append(dict(rid=req[0], token=token, event=event))
        else:
            self.unknown_completions.append(dict(token=token, event=event))

class PI:
    def __init__(self):
        self.obs = Observer(); self.queue = Queue(self.obs)
        self.busy = False; self.interrupt = False; self.error = False
        self.next_rid = 0; self.copy_effects = []
    def request(self, event, clocks=10):
        # Mirrors pinned PI ioWrite ordering: busy/context -> queueInsert -> data copy.
        if self.busy:
            self.error = True; return None
        self.next_rid += 1; rid = self.next_rid
        self.busy = True
        self.obs.begin_request(rid, event)
        ok = self.queue.insert(event, clocks)
        self.obs.end_request()
        self.copy_effects.append(dict(rid=rid, event=event, scheduled=ok))
        return rid
    def reset_dma(self):
        self.busy = False; self.error = False
        self.queue.remove_event(PI_DMA_READ)
        self.queue.remove_event(PI_DMA_WRITE)
    def dispatch(self, event, token):
        req = self.obs.dispatch(event, token)
        if event in (PI_DMA_READ, PI_DMA_WRITE):
            self.busy = False; self.interrupt = True
            self.obs.completion(event, token, req)
    def step(self, clocks): self.queue.step(clocks, self.dispatch)
    def serialize(self): self.queue.serialize_boundary()

def verify_records(records):
    inserts = {}; request_tokens = {}; canceled = set(); dispatched = set(); completions = set(); epoch = 0
    for r in records:
        k = r['kind']
        if k == 'serialize':
            epoch += 1; request_tokens.clear()
        elif k == 'insert':
            t = r['token']; assert t and t not in inserts; inserts[t]=(r['event'], epoch)
        elif k == 'request_insert':
            t=r['token']; assert t in inserts and inserts[t][0]==r['event']; request_tokens[t]=(r['rid'],r['event'],epoch)
        elif k == 'cancel':
            if r['token']: canceled.add(r['token'])
        elif k == 'dispatch':
            t=r['token']
            if t:
                assert t in inserts and inserts[t][0]==r['event']
                assert t not in dispatched
                dispatched.add(t)
        elif k == 'completion':
            t=r['token']
            if r['rid'] is not None:
                assert t in dispatched and t not in canceled and t in request_tokens
                rid,event,e=request_tokens[t]
                assert (rid,event,e)==(r['rid'],r['event'],epoch)
                assert t not in completions; completions.add(t)
    return dict(certified_tokens=sorted(completions), epochs=epoch+1)

def scenarios():
    out={}
    for name,event in [('write_to_rdram',PI_DMA_WRITE),('read_from_rdram',PI_DMA_READ)]:
        p=PI(); rid=p.request(event,7); p.step(7)
        assert p.obs.certified == [dict(rid=rid,token=1,event=event)]
        out[name]=dict(certified=p.obs.certified, unknown=p.obs.unknown_completions, copies=p.copy_effects)
    p=PI()
    for _ in range(CAPACITY): assert p.queue.insert(DUMMY, 1000)
    rid=p.request(PI_DMA_WRITE,7)
    assert p.copy_effects[-1]==dict(rid=rid,event=PI_DMA_WRITE,scheduled=False)
    p.step(7); assert not p.obs.certified and p.busy
    out['full_queue_reject']=dict(certified=p.obs.certified,copies=p.copy_effects[-1:],busy=p.busy)
    p=PI(); r1=p.request(PI_DMA_WRITE,10); p.reset_dma(); r2=p.request(PI_DMA_WRITE,10); p.step(10)
    assert p.obs.certified == [dict(rid=r2,token=2,event=PI_DMA_WRITE)]
    assert all(c['rid']!=r1 for c in p.obs.certified)
    out['cancel_then_same_event']=dict(certified=p.obs.certified,canceled=sorted(p.obs.canceled))
    p=PI(); p.request(PI_DMA_READ,5); p.serialize(); p.step(5)
    assert not p.obs.certified and len(p.obs.unknown_completions)==1 and not p.busy and p.interrupt
    out['serialize_loses_identity']=dict(certified=p.obs.certified,unknown=p.obs.unknown_completions,busy=p.busy,interrupt=p.interrupt)
    p=PI()
    p.obs.begin_request(100,PI_DMA_WRITE); p.queue.insert(PI_DMA_WRITE,5); p.obs.end_request()
    p.obs.begin_request(101,PI_DMA_WRITE); p.queue.insert(PI_DMA_WRITE,5); p.obs.end_request()
    p.step(5)
    assert {c['token'] for c in p.obs.certified}=={1,2}
    out['equal_deadline_distinct_tokens']=dict(certified=p.obs.certified)
    p=PI(); rid=p.request(PI_DMA_WRITE,4); p.step(4)
    base=copy.deepcopy(p.obs.records); verify_records(base)
    def reject(mut):
        f=copy.deepcopy(base); mut(f)
        try: verify_records(f)
        except AssertionError: return True
        return False
    attacks=[
        reject(lambda rs: next(r for r in rs if r['kind']=='completion').__setitem__('rid',rid+99)),
        reject(lambda rs: next(r for r in rs if r['kind']=='dispatch').__setitem__('event',PI_DMA_READ)),
        reject(lambda rs: next(r for r in rs if r['kind']=='completion').__setitem__('token',999)),
        reject(lambda rs: next(r for r in rs if r['kind']=='request_insert').__setitem__('event',PI_DMA_READ)),
        reject(lambda rs: next(r for r in rs if r['kind']=='dispatch').__setitem__('token',999)),
    ]
    assert all(attacks); out['forgeries_rejected']=sum(attacks)
    return out

def fuzz(seed=0x504c414944, cases=2000, actions=80):
    rng=random.Random(seed); certified=unknown=effects=0
    for _ in range(cases):
        p=PI()
        for _ in range(actions):
            a=rng.randrange(8)
            if a==0: p.request(PI_DMA_READ,rng.randrange(1,20))
            elif a==1: p.request(PI_DMA_WRITE,rng.randrange(1,20))
            elif a==2: p.reset_dma()
            elif a==3: p.step(rng.randrange(0,20))
            elif a==4: p.serialize()
            elif a==5 and len(p.queue.heap)<CAPACITY: p.queue.insert(DUMMY,rng.randrange(1,30))
            elif a==6: p.step(0)
            verify_records(p.obs.records)
        certified += len(p.obs.certified); unknown += len(p.obs.unknown_completions); effects += len(p.copy_effects)
    return dict(seed=seed,cases=cases,actions=actions,certified=certified,unknown=unknown,copy_effects=effects)

def main():
    report=dict(scenarios=scenarios(),fuzz=fuzz())
    raw=json.dumps(report,sort_keys=True,separators=(',',':')).encode()
    report['sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=='__main__': main()
