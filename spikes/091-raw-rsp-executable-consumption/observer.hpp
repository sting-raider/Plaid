/* SPDX-License-Identifier: ISC
 * Performed RSP instruction words on the shared clock, without extra guest reads.
 */
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v7"
#define PLAID_ACCESS_BOOT_POLICY "observed_storage_dmem_and_performed_rsp_instructions_with_pi_queue_sp_backing"
#define PLAID_DMEM_STORAGE_BOOT_START rsp_storage_base_start
#define PLAID_DMEM_STORAGE_BOOT_FINISH rsp_storage_base_finish
#include "../090-rsp-dmem-storage-cuts/observer.hpp"

static u64 rsp_boot_read(u32 address,u32 offset,u32 word) {
  if(!accessBootTrace) return 0;
  if(accessBootActive || accessBootPending) std::abort();
  access_boot_record("rsp_imem_read");
  std::fprintf(accessBootTrace,",\"address\":%u,\"offset\":%u,\"word\":%u}\n",address,offset,word);
  return accessBootOrdinal;
}
static void rsp_boot_instruction(bool begin,u32 pc,u64 read,u32 word,u32 next,bool halted) {
  if(!accessBootTrace) return;
  if(accessBootActive || accessBootPending) std::abort();
  access_boot_record("rsp_instruction");
  std::fprintf(accessBootTrace,",\"begin\":%s,\"rsp_pc\":%u,\"read_ordinal\":%llu,\"word\":%u,\"next_pc\":%u,\"halted\":%s}\n",
    begin ? "true" : "false",pc,(unsigned long long)read,word,next,halted ? "true" : "false");
}
static void access_boot_start(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  rsp_storage_base_start(path,romHash,budget,mappedSize,firmwareHash);
  plaidRspImemReadObserver=rsp_boot_read;
  plaidRspInstructionFetchObserver=rsp_boot_instruction;
}
static void access_boot_finish(u64 fetches) {
  plaidRspImemReadObserver=nullptr;
  plaidRspInstructionFetchObserver=nullptr;
  rsp_storage_base_finish(fetches);
}
