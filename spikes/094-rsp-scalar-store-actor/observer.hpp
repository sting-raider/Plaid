/* SPDX-License-Identifier: ISC
 * Direct scalar-method scopes distinguish actual RSP stores from other writers.
 */
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v10"
#define PLAID_ACCESS_BOOT_POLICY "observed_instruction_scoped_scalar_rsp_stores_with_rooted_operands_and_pi_queue_sp_backing"
#define PLAID_SCALAR_OPERAND_BOOT_START scalar_store_base_start
#define PLAID_SCALAR_OPERAND_BOOT_FINISH scalar_store_base_finish
#include "../093-rsp-scalar-executable/observer.hpp"
static u64 scalarInstructionContext=0,scalarStoreScope=0;
static u32 scalarStoreKind=0;
static void store_boot_instruction(bool begin,u32 pc,u64 read,u32 word,u32 next,bool halted) {
  scalar_boot_instruction(begin,pc,read,word,next,halted);
  if(!accessBootTrace) return;
  if(scalarStoreScope) std::abort();
  if(begin) {if(scalarInstructionContext) std::abort();scalarInstructionContext=accessBootOrdinal;}
  else {if(!scalarInstructionContext) std::abort();scalarInstructionContext=0;}
}
static void store_boot_scope(bool begin,u32 kind) {
  if(!accessBootTrace || !scalarInstructionContext) return;
  if(begin) {if(scalarStoreScope) std::abort();scalarStoreScope=accessBootOrdinal+1;scalarStoreKind=kind;}
  else if(!scalarStoreScope || kind!=scalarStoreKind) std::abort();
  access_boot_record("rsp_scalar_store_scope");
  std::fprintf(accessBootTrace,",\"begin\":%s,\"kind\":%u,\"instruction_context\":%llu,\"store_scope\":%llu}\n",
    begin ? "true" : "false",kind,(unsigned long long)scalarInstructionContext,(unsigned long long)scalarStoreScope);
  if(!begin) scalarStoreScope=0;
}
static void store_boot_effect(u32 offset,u32 bytes,u64 value) {
  if(!accessBootTrace) return;
  if(accessBootActive || accessBootPending) std::abort();
  access_boot_record("rsp_dmem_effect");
  std::fprintf(accessBootTrace,",\"offset\":%u,\"bytes\":%u,\"value\":%llu,\"store_scope\":%llu}\n",
    offset,bytes,(unsigned long long)value,(unsigned long long)scalarStoreScope);
}
static void access_boot_start(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  scalarInstructionContext=scalarStoreScope=0;
  scalar_store_base_start(path,romHash,budget,mappedSize,firmwareHash);
  plaidRspInstructionFetchObserver=store_boot_instruction;
  plaidRspScalarStoreObserver=store_boot_scope;
  plaidRspDmemObserver=store_boot_effect;
}
static void access_boot_finish(u64 fetches) {
  if(scalarInstructionContext || scalarStoreScope) std::abort();
  plaidRspScalarStoreObserver=nullptr;
  scalar_store_base_finish(fetches);
}
