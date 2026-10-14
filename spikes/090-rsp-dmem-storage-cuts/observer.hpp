/* SPDX-License-Identifier: ISC
 * Lower completed DMEM lanes on the existing clock, without producer ancestry.
 */
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v6"
#define PLAID_ACCESS_BOOT_POLICY "observed_ordinary_storage_and_dmem_mutations_with_pi_queue_sp_backing"
#define PLAID_STORAGE_BOOT_START dmem_storage_base_start
#define PLAID_STORAGE_BOOT_FINISH dmem_storage_base_finish
#include "../087-storage-writer-fetch-history/observer.hpp"

static void dmem_storage_effect(u32 offset,u32 bytes,u64 value) {
  if(!accessBootTrace) return;
  if(accessBootActive || accessBootPending) std::abort();
  access_boot_record("rsp_dmem_effect");
  std::fprintf(accessBootTrace,",\"offset\":%u,\"bytes\":%u,\"value\":%llu}\n",
    offset,bytes,(unsigned long long)value);
}
static void access_boot_start(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  dmem_storage_base_start(path,romHash,budget,mappedSize,firmwareHash);
  plaidRspDmemObserver=dmem_storage_effect;
}
static void access_boot_finish(u64 fetches) {
  plaidRspDmemObserver=nullptr;
  dmem_storage_base_finish(fetches);
}
