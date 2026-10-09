/* SPDX-License-Identifier: ISC
 * Original PIF-ROM reads and delegated read-only write attempts.
 */
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v4"
#define PLAID_ACCESS_BOOT_POLICY "identity_ram_pi_queue_sp_and_observed_pif_backing"
#define PLAID_SP_BOOT_START sp_effect_boot_start
#define PLAID_SP_BOOT_FINISH sp_effect_boot_finish
#include "../040-ares-boot-sp-history/observer.hpp"

static void pif_boot_word(bool write,u32 offset,u32 value) {
  if(!accessBootTrace) return;
  if(accessBootPending) std::abort();
  access_boot_record(write ? "pif_rom_write_attempt" : "pif_rom_word");
  std::fprintf(accessBootTrace,",\"write\":%s,\"offset\":%u,\"bytes\":4,\"value\":%u}\n",
    write ? "true" : "false",offset,value);
}
static void access_boot_start(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  sp_effect_boot_start(path,romHash,budget,mappedSize,firmwareHash);
  plaidPifWordObserver=pif_boot_word;
}
static void access_boot_finish(u64 fetches) {
  plaidPifWordObserver=nullptr;sp_effect_boot_finish(fetches);
}
