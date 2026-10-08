/* SPDX-License-Identifier: ISC
 * Original streamed PI boundaries alongside successful backing chronology.
 */
#ifndef PLAID_ACCESS_BOOT_FORMAT
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v1"
#endif
#ifndef PLAID_ACCESS_BOOT_POLICY
#define PLAID_ACCESS_BOOT_POLICY "identity_ram_fetch_and_buffered_pi_contexts"
#endif
#ifndef PLAID_PI_BOOT_START
#define PLAID_PI_BOOT_START access_boot_start
#endif
#ifndef PLAID_PI_BOOT_FINISH
#define PLAID_PI_BOOT_FINISH access_boot_finish
#endif
#define access_boot_start base_access_boot_start
#define access_boot_finish base_access_boot_finish
#include "../027-ares-boot-history/observer.hpp"
#undef access_boot_start
#undef access_boot_finish

static u64 bootPiTransfer = 0;
static u64 bootPiPending = 0;
static u32 bootPiBlock = 0;
static bool bootPiCopying = false, bootPiAttempt = false;
static u32 bootPiLane = 0, bootPiDestination = 0, bootPiValue = 0;

static void access_boot_pi(u32 event,u32 dram,u32 pbus,u32 length,u32 lane,u32 value) {
  if(!accessBootTrace) return;
  if(event == 1) {
    if(bootPiCopying || bootPiAttempt) std::abort();
    ++bootPiTransfer; bootPiBlock = 0; bootPiCopying = true;
    bootPiPending = bootPiTransfer;
  }
  if(event == 2) ++bootPiBlock;
  if(event == 4) {
    if(bootPiAttempt || !bootPiCopying) std::abort();
    bootPiAttempt = true; bootPiLane = lane; bootPiDestination = dram; bootPiValue = value;
  }
  access_boot_record("pi_dma");
  std::fprintf(accessBootTrace,",\"event\":%u,\"transfer\":%llu,\"block\":%u,\"dram\":%u,\"pbus\":%u,\"length\":%u,\"lane\":%u,\"value\":%u}\n",
    event,(unsigned long long)(event == 8 ? bootPiPending : bootPiTransfer),bootPiBlock,dram,pbus,length,lane,value);
  if(event == 5) {
    if(!bootPiAttempt || dram != bootPiDestination || lane != bootPiLane || value != bootPiValue) std::abort();
    bootPiAttempt = false;
  }
  if(event == 7) bootPiCopying = false;
  if(event == 8) bootPiPending = 0;
}
static void access_boot_rom_half(u32 offset,u16 value) {
  if(!accessBootTrace || !bootPiCopying) return;
  access_boot_record("pi_rom_half");
  std::fprintf(accessBootTrace,",\"transfer\":%llu,\"block\":%u,\"offset\":%u,\"value\":%u}\n",
    (unsigned long long)bootPiTransfer,bootPiBlock,offset,(u32)value);
}
static void access_boot_pi_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(write && device == (u32)RBusDevice::PI_DMA) {
    if(!bootPiAttempt || bytes != Byte || address != bootPiDestination || value != bootPiValue) std::abort();
    access_boot_record("scalar");
    std::fprintf(accessBootTrace,",\"write\":true,\"address\":%u,\"aligned_address\":%u,\"bytes\":%u,\"device\":%u,\"value\":%llu,\"pi\":{\"transfer\":%llu,\"block\":%u,\"lane\":%u}}\n",
      address,address,bytes,device,(unsigned long long)value,(unsigned long long)bootPiTransfer,bootPiBlock,bootPiLane);
  } else access_boot_scalar(write,address,bytes,device,value);
}
static void PLAID_PI_BOOT_START(const char* tracePath,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  base_access_boot_start(tracePath,romHash,budget,mappedSize,firmwareHash);
  plaidPiDmaObserver = access_boot_pi;
  plaidRomHalfObserver = access_boot_rom_half;
  plaidRdramScalarObserver = access_boot_pi_scalar;
}
static void PLAID_PI_BOOT_FINISH(u64 fetches) {
  // A budget may end while scheduled DMA completion is still pending. Every
  // synchronous copy call/byte attempt must have returned; no completion invented.
  if(bootPiCopying || bootPiAttempt) std::abort();
  plaidPiDmaObserver = nullptr; plaidRomHalfObserver = nullptr;
  base_access_boot_finish(fetches);
}
