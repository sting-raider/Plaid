/* SPDX-License-Identifier: ISC
 * Exact performed-code receipts and opaque initial scalar operand roots.
 */
#ifndef PLAID_ACCESS_BOOT_FORMAT
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v9"
#endif
#ifndef PLAID_ACCESS_BOOT_POLICY
#define PLAID_ACCESS_BOOT_POLICY "observed_storage_sp_execution_and_rooted_scalar_operands_with_pi_queue_sp_backing"
#endif
#ifndef PLAID_SCALAR_OPERAND_BOOT_START
#define PLAID_SCALAR_OPERAND_BOOT_START access_boot_start
#endif
#ifndef PLAID_SCALAR_OPERAND_BOOT_FINISH
#define PLAID_SCALAR_OPERAND_BOOT_FINISH access_boot_finish
#endif
#define PLAID_IMEM_STORAGE_BOOT_START scalar_storage_base_start
#define PLAID_IMEM_STORAGE_BOOT_FINISH scalar_storage_base_finish
#include "../092-imem-storage-cuts/observer.hpp"
static bool scalarOperandRooted=false;
static void scalar_registers() {
  std::fprintf(accessBootTrace,",\"registers\":[");
  for(u32 n=0;n<32;n++) std::fprintf(accessBootTrace,"%s%u",n ? "," : "",(u32)rsp.ipu.r[n].u32);
  std::fprintf(accessBootTrace,"]}");
}
static void scalar_boot_instruction(bool begin,u32 pc,u64 read,u32 word,u32 next,bool halted) {
  if(!accessBootTrace) return;
  if(accessBootActive || accessBootPending) std::abort();
  if(!scalarOperandRooted) {
    if(!begin) std::abort();
    access_boot_record("rsp_operand_root");
    std::fprintf(accessBootTrace,",\"epoch\":1,\"rsp_pc\":%u",pc);
    scalar_registers();std::fprintf(accessBootTrace,"\n");scalarOperandRooted=true;
  }
  access_boot_record("rsp_instruction");
  std::fprintf(accessBootTrace,",\"begin\":%s,\"rsp_pc\":%u,\"read_ordinal\":%llu,\"word\":%u,\"next_pc\":%u,\"halted\":%s",
    begin ? "true" : "false",pc,(unsigned long long)read,word,next,halted ? "true" : "false");
  scalar_registers();std::fprintf(accessBootTrace,"\n");
}
static void PLAID_SCALAR_OPERAND_BOOT_START(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  scalarOperandRooted=false;
  scalar_storage_base_start(path,romHash,budget,mappedSize,firmwareHash);
  plaidRspInstructionFetchObserver=scalar_boot_instruction;
}
static void PLAID_SCALAR_OPERAND_BOOT_FINISH(u64 fetches) {
  scalar_storage_base_finish(fetches);scalarOperandRooted=false;
}
