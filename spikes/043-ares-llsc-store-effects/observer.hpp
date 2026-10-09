/* SPDX-License-Identifier: ISC */
struct LlscScalarEvent {
  u32 caseId, stage, ordinal;
  bool write;
  u32 address, bytes, device;
  u64 value;
};
struct LlscBurstEvent {
  u32 caseId, stage, ordinal;
  bool write;
  u32 address, bytes, device, count;
  u32 words[8]{};
};
static std::vector<LlscScalarEvent> llscScalarEvents;
static std::vector<LlscBurstEvent> llscBurstEvents;
static u32 llscCaseId = 0, llscStage = 0, llscOrdinal = 0;

static void llsc_scalar_observer(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  if(device != (u32)RBusDevice::VR4300_UNCACHED) return;
  llscScalarEvents.push_back({llscCaseId,llscStage,++llscOrdinal,write,address,bytes,device,value});
}
static void llsc_burst_observer(bool write, u32 address, u32 bytes, u32 device, const u32* value) {
  if(device != (u32)RBusDevice::VR4300_DCACHE) return;
  LlscBurstEvent event{};
  event.caseId=llscCaseId; event.stage=llscStage; event.ordinal=++llscOrdinal;
  event.write=write; event.address=address; event.bytes=bytes; event.device=device;
  event.count=bytes/4 > 8 ? 8 : bytes/4;
  for(u32 i=0;i<event.count;i++) event.words[i]=value[i];
  llscBurstEvents.push_back(event);
}
static void llsc_print_events() {
  std::printf("\"scalar_events\":[");
  for(size_t i=0;i<llscScalarEvents.size();i++) {
    auto& e=llscScalarEvents[i];
    std::printf("%s{\"case\":%u,\"stage\":%u,\"ordinal\":%u,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"value\":%llu}",
      i?",":"",e.caseId,e.stage,e.ordinal,e.write?"true":"false",e.address,e.bytes,e.device,(unsigned long long)e.value);
  }
  std::printf("],\"burst_events\":[");
  for(size_t i=0;i<llscBurstEvents.size();i++) {
    auto& e=llscBurstEvents[i];
    std::printf("%s{\"case\":%u,\"stage\":%u,\"ordinal\":%u,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"words\":[",
      i?",":"",e.caseId,e.stage,e.ordinal,e.write?"true":"false",e.address,e.bytes,e.device);
    for(u32 j=0;j<e.count;j++) std::printf("%s%u",j?",":"",e.words[j]);
    std::printf("]}");
  }
  std::printf("]");
}
