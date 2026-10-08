/* SPDX-License-Identifier: ISC
 * Existing results only: no guest read, translation, clock or decoder calls.
 */
#define print_history print_base_history
#include "../018-ares-ordered-history/history.hpp"
#undef print_history

struct AccessScalar {
  u64 pc, value;
  u32 address, bytes, device;
  bool write;
};
struct AccessBoundary {
  u64 pc, vaddr;
  u32 translated, bus, value;
  bool begin, cached;
};
static std::vector<AccessScalar> accessScalars;
static std::vector<AccessBoundary> accessBoundaries;

static void access_scalar_observer(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  accessScalars.push_back({cpu.ipu.pc,value,address,bytes,device,write});
  history_event("scalar",accessScalars.size());
}
static void access_boundary_observer(bool begin,u64 vaddr,u32 translated,u32 bus,bool cached,u32 value) {
  accessBoundaries.push_back({cpu.ipu.pc,vaddr,translated,bus,value,begin,cached});
  history_event("fetch_boundary",accessBoundaries.size());
}
static void print_history() {
  print_base_history();
  std::printf(",\"access_policy\":\"controlled_access_callbacks_v0\",\"scalars\":[");
  for(size_t i=0;i<accessScalars.size();i++) {
    const auto& e = accessScalars[i];
    std::printf("%s{\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"value\":%llu}",
      i ? "," : "",(unsigned long long)e.pc,e.write ? "true" : "false",e.address,e.bytes,e.device,(unsigned long long)e.value);
  }
  std::printf("],\"boundaries\":[");
  for(size_t i=0;i<accessBoundaries.size();i++) {
    const auto& e = accessBoundaries[i];
    std::printf("%s{\"pc\":%llu,\"vaddr\":%llu,\"translated\":%u,\"bus\":%u,\"cached\":%s,\"begin\":%s,\"value\":%u}",
      i ? "," : "",(unsigned long long)e.pc,(unsigned long long)e.vaddr,e.translated,e.bus,e.cached ? "true" : "false",e.begin ? "true" : "false",e.value);
  }
  std::printf("]");
}
