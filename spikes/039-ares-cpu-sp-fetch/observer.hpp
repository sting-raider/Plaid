/* SPDX-License-Identifier: ISC
 * Original completed-result observer, without guest reads or clock steps.
 */
struct SpEvent {
  const char* kind;
  u64 ordinal, context, pc, value;
  u32 phase, address, bank, offset, bytes, device, translated;
  bool cpu, cached;
};
static std::vector<SpEvent> spEvents;
static u32 spPhase=0;
static u64 spActive=0, spPending=0;
static bool spEnabled=false;
static void sp_record(const char* kind,u32 address,u32 bank,u32 offset,u32 bytes,u64 value,
                      bool originCpu,bool cached=false,u32 translated=0,u32 device=0) {
  if(!spEnabled) return;
  spEvents.push_back({kind,spEvents.size()+1,spActive,cpu.ipu.pc,value,spPhase,
    address,bank,offset,bytes,device,translated,originCpu,cached});
}
static void sp_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  sp_record(write ? "sp_write" : "sp_read",address,bank,offset,4,value,originCpu);
}
static void sp_dma(u32 dram,u32 bank,u32 offset,u32 bytes,u64 value) {
  sp_record("dma_store",dram,bank,offset,bytes,value,false);
}
static void sp_rdram(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(device==(u32)RBusDevice::SP_DMA && !write) sp_record("dma_read",address,0,0,bytes,value,false,false,0,device);
}
static void sp_boundary(bool begin,u64 vaddr,u32 translated,u32 bus,bool cached,u32 value) {
  if(!spEnabled) return;
  if(vaddr!=cpu.ipu.pc) std::abort();
  if(begin) { if(spActive || spPending) std::abort(); spActive=spEvents.size()+1; }
  if(!spActive) std::abort();
  sp_record(begin ? "begin" : "end",bus,0,0,4,value,true,cached,translated);
  if(!begin) { spPending=spActive; spActive=0; }
}
static void sp_fetch() {
  if(!spEnabled) return;
  if(spActive || !spPending) std::abort();
  sp_record("fetch",plaidFetchAccess.physical,0,0,4,cpu.disassembler.fetchedWord(),true,plaidFetchAccess.cached);
  spEvents.back().context=spPending;spPending=0;
}
static void sp_print() {
  std::printf("\"events\":[");
  for(size_t n=0;n<spEvents.size();n++) {
    const auto& e=spEvents[n];
    std::printf("%s{\"kind\":\"%s\",\"ordinal\":%llu,\"context\":%llu,\"pc\":%llu,\"phase\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu,\"device\":%u,\"translated\":%u,\"cpu\":%s,\"cached\":%s}",
      n ? "," : "",e.kind,(unsigned long long)e.ordinal,(unsigned long long)e.context,
      (unsigned long long)e.pc,e.phase,e.address,e.bank,e.offset,e.bytes,(unsigned long long)e.value,
      e.device,e.translated,e.cpu ? "true" : "false",e.cached ? "true" : "false");
  }
  std::printf("]");
}
