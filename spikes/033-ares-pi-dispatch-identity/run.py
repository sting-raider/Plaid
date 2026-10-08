#!/usr/bin/env python3
"""Adversarial model of pinned ares nall::priority_queue PI identity joining.

Semantics translated from ares 9408cb43d4948fc3ea6e152a307a34348df3fe04
nall/nall/priority-queue.hpp. This intentionally keeps provenance metadata in a
parallel sidecar, not in queue entries, and compares every visible queue state
against an uninstrumented baseline model.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, random

MASK = 0xffffffff
PI_READ = 0
PI_WRITE = 1
OTHER = 99
CAPACITY = 512

def u32(x): return x & MASK

def ge(x, y): return u32(x - y) < 0x7fffffff

@dataclass(eq=True)
class Entry:
    clock: int = 0
    event: int = 0
    valid: bool = False

class Baseline:
    def __init__(self):
        self.clock=0; self.size=0; self.heap=[Entry() for _ in range(CAPACITY)]
    def reset(self): self.clock=0; self.size=0
    def insert(self,event,delta):
        if self.size >= CAPACITY: return False
        child=self.size; self.size+=1; clock=u32(delta+self.clock)
        while child:
            parent=(child-1)>>1
            if ge(clock,self.heap[parent].clock): break
            self.heap[child]=Entry(self.heap[parent].clock,self.heap[parent].event,self.heap[parent].valid)
            child=parent
        self.heap[child]=Entry(clock,event,True); return True
    def pop(self):
        event=self.heap[0].event; valid=self.heap[0].valid
        self.size-=1; parent=0; clock=self.heap[self.size].clock
        while True:
            child=(parent<<1)+1
            if child>=self.size: break
            if child+1<self.size and ge(self.heap[child].clock,self.heap[child+1].clock): child+=1
            if ge(self.heap[child].clock,clock): break
            self.heap[parent]=Entry(self.heap[child].clock,self.heap[child].event,self.heap[child].valid); parent=child
        self.heap[parent]=Entry(clock,self.heap[self.size].event,self.heap[self.size].valid)
        return event if valid else None
    def remove_event(self,event):
        cycles=0
        for i in range(self.size):
            if self.heap[i].event==event:
                self.heap[i].valid=False; cycles=max(cycles,u32(self.heap[i].clock-self.clock))
        return cycles
    def step(self,clocks):
        self.clock=u32(self.clock+clocks); out=[]
        while self.size and ge(self.clock,self.heap[0].clock):
            event=self.pop()
            if event is not None: out.append(event)
        return out
    def visible(self): return (self.clock,self.size,tuple((e.clock,e.event,e.valid) for e in self.heap[:self.size]))

class Observed(Baseline):
    def __init__(self):
        super().__init__(); self.tokens=[0]*CAPACITY; self.next_token=0
        self.last_insert=None; self.removals=[]; self.cancellations=[]
    def reset(self): super().reset(); self.tokens=[0]*CAPACITY
    def insert(self,event,delta):
        self.last_insert=None
        if self.size >= CAPACITY: return False
        child=self.size; self.size+=1; clock=u32(delta+self.clock)
        while child:
            parent=(child-1)>>1
            if ge(clock,self.heap[parent].clock): break
            self.heap[child]=Entry(self.heap[parent].clock,self.heap[parent].event,self.heap[parent].valid)
            self.tokens[child]=self.tokens[parent]
            child=parent
        self.heap[child]=Entry(clock,event,True)
        self.next_token+=1; self.tokens[child]=self.next_token; self.last_insert=self.next_token
        return True
    def pop_with_token(self):
        event=self.heap[0].event; valid=self.heap[0].valid; token=self.tokens[0]
        self.removals.append((token,event,valid,self.heap[0].clock))
        self.size-=1; parent=0; clock=self.heap[self.size].clock
        while True:
            child=(parent<<1)+1
            if child>=self.size: break
            if child+1<self.size and ge(self.heap[child].clock,self.heap[child+1].clock): child+=1
            if ge(self.heap[child].clock,clock): break
            self.heap[parent]=Entry(self.heap[child].clock,self.heap[child].event,self.heap[child].valid)
            self.tokens[parent]=self.tokens[child]; parent=child
        self.heap[parent]=Entry(clock,self.heap[self.size].event,self.heap[self.size].valid)
        self.tokens[parent]=self.tokens[self.size]
        return (event if valid else None), token, valid
    def pop(self): return self.pop_with_token()[0]
    def remove_event(self,event):
        cycles=0
        for i in range(self.size):
            if self.heap[i].event==event:
                self.cancellations.append((self.tokens[i],event,self.heap[i].valid,self.heap[i].clock))
                self.heap[i].valid=False; cycles=max(cycles,u32(self.heap[i].clock-self.clock))
        return cycles
    def step(self,clocks):
        self.clock=u32(self.clock+clocks); out=[]
        while self.size and ge(self.clock,self.heap[0].clock):
            event,token,valid=self.pop_with_token()
            if event is not None: out.append((event,token))
        return out

def same(b,o):
    assert b.visible()==o.visible(), (b.visible(),o.visible())

def adversarial():
    results={}
    # Duplicate tuple: same event and absolute clock, distinct identity.
    b=Baseline(); o=Observed()
    assert b.insert(PI_WRITE,10)==o.insert(PI_WRITE,10); t1=o.last_insert; same(b,o)
    assert b.insert(PI_WRITE,10)==o.insert(PI_WRITE,10); t2=o.last_insert; same(b,o)
    assert t1!=t2
    base=b.step(10); obs=o.step(10); same(b,o)
    assert base==[PI_WRITE,PI_WRITE]
    assert [e for e,_ in obs]==base and [t for _,t in obs]==[t1,t2]
    results['duplicate_tuple']={'tuple':[10,PI_WRITE],'tokens':[t1,t2],'dispatch_tokens':[t for _,t in obs]}

    # Slot identity is unstable: a later earlier-deadline insertion displaces prior row.
    b=Baseline(); o=Observed();
    b.insert(OTHER,20); o.insert(OTHER,20); old=o.last_insert; old_slot=o.tokens.index(old)
    b.insert(PI_WRITE,5); o.insert(PI_WRITE,5); new=o.last_insert; same(b,o)
    new_old_slot=o.tokens.index(old)
    assert old_slot==0 and new_old_slot!=old_slot
    results['slot_reuse']={'first_token':old,'initial_slot':old_slot,'slot_after_earlier_insert':new_old_slot,'new_root_token':new}

    # Cancellation creates tombstones; exact token is observable at mark and later invalid pop.
    b=Baseline(); o=Observed()
    b.insert(PI_READ,7); o.insert(PI_READ,7); canceled=o.last_insert
    b.insert(OTHER,9); o.insert(OTHER,9); survivor=o.last_insert; same(b,o)
    assert b.remove_event(PI_READ)==o.remove_event(PI_READ); same(b,o)
    assert o.cancellations[-1][0]==canceled
    base=b.step(10); obs=o.step(10); same(b,o)
    assert base==[OTHER] and obs==[(OTHER,survivor)]
    invalid=[x for x in o.removals if x[0]==canceled]
    assert invalid and invalid[0][2] is False
    results['cancel_tombstone']={'canceled_token':canceled,'valid_dispatch_token':survivor,'invalid_root_observed':True}

    # Capacity failure must not fabricate request->queue identity.
    b=Baseline(); o=Observed()
    for i in range(CAPACITY): assert b.insert(OTHER,1000+i)==o.insert(OTHER,1000+i)
    same(b,o); assert b.insert(PI_WRITE,1) is False and o.insert(PI_WRITE,1) is False and o.last_insert is None
    results['capacity_failure']={'capacity':CAPACITY,'fabricated_token':o.last_insert}

    # Current spike-032 kind=9 behavior clears every token on *both* save and load.
    # N64 System::serialize calls s(queue), so merely saving state while PI is
    # pending severs request->completion identity even if emulation never loads it.
    b=Baseline(); o=Observed()
    b.insert(PI_WRITE,10); o.insert(PI_WRITE,10); pending=o.last_insert; same(b,o)
    o.tokens=[0]*CAPACITY  # observer.hpp: if(kind == 1 || kind == 9) fill(0)
    base=b.step(10); obs=o.step(10); same(b,o)
    assert base==[PI_WRITE] and obs==[(PI_WRITE,0)]
    results['serialization_counterexample']={
        'pending_request_token_before_save':pending,
        'dispatch_token_after_save_with_spike032_kind9':obs[0][1],
        'continuity_preserved':False,
    }
    return results

def fuzz(seed=0x504c414944, operations=200000):
    rng=random.Random(seed); b=Baseline(); o=Observed(); accepted=0; canceled=0; callbacks=0
    digest=hashlib.sha256()
    for n in range(operations):
        r=rng.random()
        if r<0.48:
            event=rng.choice([PI_READ,PI_WRITE,OTHER,7,13]); delta=rng.randrange(0,5000)
            rb=b.insert(event,delta); ro=o.insert(event,delta); assert rb==ro
            accepted+=rb
        elif r<0.65:
            event=rng.choice([PI_READ,PI_WRITE,OTHER,7,13])
            rb=b.remove_event(event); ro=o.remove_event(event); assert rb==ro; canceled+=1
        elif r<0.985:
            clocks=rng.randrange(0,10000)
            rb=b.step(clocks); ro=o.step(clocks)
            assert rb==[e for e,_ in ro]; callbacks+=len(rb)
        else:
            b.reset(); o.reset()
        same(b,o)
        # Exact live sidecar uniqueness invariant.
        live=o.tokens[:o.size]
        assert len([t for t in live if t])==len(set(t for t in live if t))
        digest.update(repr(b.visible()).encode())
    return {'seed':seed,'operations':operations,'accepted_inserts':accepted,'cancel_ops':canceled,'valid_callbacks':callbacks,'visible_trace_sha256':digest.hexdigest()}

def main():
    result={'ares_revision':'9408cb43d4948fc3ea6e152a307a34348df3fe04','adversarial':adversarial(),'fuzz':fuzz()}
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': main()
