/* SPDX-License-Identifier: ISC
 * Actual ordinary IMEM storage effects share the original executable clock.
 */
#ifndef PLAID_ACCESS_BOOT_FORMAT
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v8"
#endif
#ifndef PLAID_ACCESS_BOOT_POLICY
#define PLAID_ACCESS_BOOT_POLICY "observed_storage_dmem_imem_and_rsp_consumption_with_pi_queue_sp_backing"
#endif
#ifndef PLAID_IMEM_STORAGE_BOOT_START
#define PLAID_IMEM_STORAGE_BOOT_START access_boot_start
#endif
#ifndef PLAID_IMEM_STORAGE_BOOT_FINISH
#define PLAID_IMEM_STORAGE_BOOT_FINISH access_boot_finish
#endif
#define PLAID_RSP_EXECUTION_BOOT_START imem_storage_base_start
#define PLAID_RSP_EXECUTION_BOOT_FINISH imem_storage_base_finish
#include "../091-raw-rsp-executable-consumption/observer.hpp"

static void imem_storage_effect(const void* memory,u32 kind,u32 offset,u32 bytes,u64 value) {
  if(memory != static_cast<ares::Nintendo64::Memory::Writable*>(&rsp.imem)) {
    storage_boot_effect(memory,kind,offset,bytes,value);return;
  }
  if(!accessBootTrace) return;
  if(accessBootPending) std::abort();
  access_boot_record("imem_storage_effect");
  std::fprintf(accessBootTrace,",\"kind\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu}\n",
    kind,offset,bytes,(unsigned long long)value);
}
static void PLAID_IMEM_STORAGE_BOOT_START(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  imem_storage_base_start(path,romHash,budget,mappedSize,firmwareHash);
  ares::Nintendo64::Memory::plaidMemoryMutationObserver=imem_storage_effect;
}
static void PLAID_IMEM_STORAGE_BOOT_FINISH(u64 fetches) {
  imem_storage_base_finish(fetches);
}
