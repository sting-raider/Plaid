#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys

REV='9408cb43d4948fc3ea6e152a307a34348df3fe04'
ref=Path(sys.argv[1]) if len(sys.argv)>1 else Path('.refs/ares')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ref,text=True).strip()==REV
subprocess.run(['git','diff','--quiet','HEAD'],cwd=ref,check=True)
queue=(ref/'nall/nall/priority-queue.hpp').read_text()
cpu=(ref/'ares/n64/cpu/cpu.cpp').read_text()
io=(ref/'ares/n64/pi/io.cpp').read_text()
dma=(ref/'ares/n64/pi/dma.cpp').read_text()
n64=(ref/'ares/n64/n64.hpp').read_text()

checks={
'queue_valid_callback_only': 'if(auto event = remove()) callback(*event);' in queue,
'queue_silent_capacity_failure': 'if(size >= Size) return false;' in queue,
'queue_cancellation_invalidates_without_erasing': 'heap[i].valid = false;' in queue,
'queue_serializes_validity': 's(entry.valid);' in queue,
'queue_size_512': 'struct Queue : priority_queue<u32[512]>' in n64,
'cpu_queue_insert_silent_failure': 'if(!queue.insert(event, clocks)) return;' in cpu,
'cpu_read_dispatch_common_completion': 'case Queue::PI_DMA_Read:   return pi.dmaFinished();' in cpu,
'cpu_write_dispatch_common_completion': 'case Queue::PI_DMA_Write:  return pi.dmaFinished();' in cpu,
'pi_read_request_order': 'io.dmaBusy = 1;\n    io.originPc = cpu.ipu.pc;\n    cpu.queueInsert(Queue::PI_DMA_Read, dmaDuration(true));\n    dmaRead();' in io,
'pi_write_request_order': 'io.dmaBusy = 1;\n    io.originPc = cpu.ipu.pc;\n    cpu.queueInsert(Queue::PI_DMA_Write, dmaDuration(false));\n    dmaWrite();' in io,
'pi_reset_cancels_read': 'queue.remove(Queue::PI_DMA_Read);' in io,
'pi_reset_cancels_write': 'queue.remove(Queue::PI_DMA_Write);' in io,
'common_completion_clears_busy': 'auto PI::dmaFinished() -> void {\n  io.dmaBusy = 0;\n  io.interrupt = 1;' in dma,
}
assert all(checks.values()), [k for k,v in checks.items() if not v]
print('PASS', REV, len(checks), 'source contracts')
for k in sorted(checks): print(k)
