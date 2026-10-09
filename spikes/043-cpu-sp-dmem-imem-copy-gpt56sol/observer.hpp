/* SPDX-License-Identifier: ISC
 * Project-owned completed SP Word observer for the bounded copy experiment.
 */
struct CopySpEvent {
  const char* kind;
  u64 ordinal, pc, value;
  u32 phase, address, bank, offset, bytes;
  bool cpu;
};
static std::vector<CopySpEvent> copySpEvents;
static u32 copyPhase=0;
static bool copySpEnabled=false;

static void copy_sp_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  if(!copySpEnabled) return;
  copySpEvents.push_back({
    write ? "sp_write" : "sp_read",
    copySpEvents.size()+1,
    cpu.ipu.pc,
    value,
    copyPhase,
    address,
    bank,
    offset,
    4,
    originCpu
  });
}

static void copy_sp_print() {
  std::printf("\"events\":[");
  for(size_t n=0;n<copySpEvents.size();n++) {
    const auto& e=copySpEvents[n];
    std::printf("%s{\"kind\":\"%s\",\"ordinal\":%llu,\"pc\":%llu,\"phase\":%u,"
      "\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu,\"cpu\":%s}",
      n ? "," : "",e.kind,(unsigned long long)e.ordinal,(unsigned long long)e.pc,e.phase,
      e.address,e.bank,e.offset,e.bytes,(unsigned long long)e.value,e.cpu ? "true" : "false");
  }
  std::printf("]");
}
