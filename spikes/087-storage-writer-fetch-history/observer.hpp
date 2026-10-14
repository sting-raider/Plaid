/* SPDX-License-Identifier: ISC
 * Original-clock ordinary RDRAM storage effects; no additional guest accesses.
 */
#ifndef PLAID_ACCESS_BOOT_FORMAT
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v5"
#endif
#ifndef PLAID_ACCESS_BOOT_POLICY
#define PLAID_ACCESS_BOOT_POLICY "observed_ordinary_storage_mutations_and_pi_queue_sp_backing"
#endif
#ifndef PLAID_STORAGE_BOOT_START
#define PLAID_STORAGE_BOOT_START access_boot_start
#endif
#ifndef PLAID_STORAGE_BOOT_FINISH
#define PLAID_STORAGE_BOOT_FINISH access_boot_finish
#endif
#define PLAID_SP_BOOT_START storage_base_start
#define PLAID_SP_BOOT_FINISH storage_base_finish
#include "../040-ares-boot-sp-history/observer.hpp"

static void storage_boot_effect(const void* memory,u32 kind,u32 address,u32 bytes,u64 value) {
  if(!accessBootTrace || memory != static_cast<ares::Nintendo64::Memory::Writable*>(&rdram.ram)) return;
  if(accessBootPending) std::abort();
  access_boot_record("storage_effect");
  std::fprintf(accessBootTrace,",\"kind\":%u,\"address\":%u,\"bytes\":%u,\"value\":%llu}\n",
    kind,address,bytes,(unsigned long long)value);
}
static void PLAID_STORAGE_BOOT_START(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  storage_base_start(path,romHash,budget,mappedSize,firmwareHash);
  ares::Nintendo64::Memory::plaidMemoryMutationObserver=storage_boot_effect;
}
static void PLAID_STORAGE_BOOT_FINISH(u64 fetches) {
  ares::Nintendo64::Memory::plaidMemoryMutationObserver=nullptr;
  storage_base_finish(fetches);
}
