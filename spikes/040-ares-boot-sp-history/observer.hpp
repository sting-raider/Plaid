/* SPDX-License-Identifier: ISC
 * Original streamed SP backing results and normalized completed stores.
 */
#ifndef PLAID_ACCESS_BOOT_FORMAT
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v3"
#endif
#ifndef PLAID_ACCESS_BOOT_POLICY
#define PLAID_ACCESS_BOOT_POLICY "identity_ram_pi_queue_and_observed_sp_backing"
#endif
#ifndef PLAID_SP_BOOT_START
#define PLAID_SP_BOOT_START access_boot_start
#endif
#ifndef PLAID_SP_BOOT_FINISH
#define PLAID_SP_BOOT_FINISH access_boot_finish
#endif
#define PLAID_QUEUE_BOOT_START queue_effect_boot_start
#define PLAID_QUEUE_BOOT_FINISH queue_effect_boot_finish
#include "../037-ares-boot-pi-queue-history/observer.hpp"

static void sp_boot_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  if(!accessBootTrace) return;
  if(accessBootPending) std::abort();
  access_boot_record("sp_word");
  std::fprintf(accessBootTrace,",\"write\":%s,\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":4,\"value\":%u,\"cpu\":%s}\n",
    write ? "true" : "false",address,bank,offset,value,originCpu ? "true" : "false");
}
static void sp_boot_dma(u32 dram,u32 bank,u32 offset,u32 bytes,u64 value) {
  if(!accessBootTrace) return;
  if(accessBootActive || accessBootPending) std::abort();
  access_boot_record("sp_dma_store");
  std::fprintf(accessBootTrace,",\"dram\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu}\n",
    dram,bank,offset,bytes,(unsigned long long)value);
}
static void PLAID_SP_BOOT_START(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  queue_effect_boot_start(path,romHash,budget,mappedSize,firmwareHash);
  plaidSpWordObserver=sp_boot_word;plaidSpDmaStoreObserver=sp_boot_dma;
}
static void PLAID_SP_BOOT_FINISH(u64 fetches) {
  plaidSpWordObserver=nullptr;plaidSpDmaStoreObserver=nullptr;
  queue_effect_boot_finish(fetches);
}
