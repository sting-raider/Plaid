/* SPDX-License-Identifier: ISC
 * Original-clock ordinary RDRAM storage effects; no additional guest accesses.
 */
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v5"
#define PLAID_ACCESS_BOOT_POLICY "observed_ordinary_storage_mutations_and_pi_queue_sp_backing"
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
static void access_boot_start(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  storage_base_start(path,romHash,budget,mappedSize,firmwareHash);
  ares::Nintendo64::Memory::plaidMemoryMutationObserver=storage_boot_effect;
}
static void access_boot_finish(u64 fetches) {
  ares::Nintendo64::Memory::plaidMemoryMutationObserver=nullptr;
  storage_base_finish(fetches);
}
