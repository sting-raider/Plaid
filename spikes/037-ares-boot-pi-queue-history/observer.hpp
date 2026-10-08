/* SPDX-License-Identifier: ISC
 * Original streamed accepted PI request and actual queue/dispatch identities.
 * Pre-capture queue rows deliberately have unknown token/request identity.
 */
#include <map>
#include "../032-ares-queue-identity/observer.hpp"
#define PLAID_ACCESS_BOOT_FORMAT "plaid-ares-access-history-v2"
#define PLAID_ACCESS_BOOT_POLICY "identity_ram_buffered_pi_and_actual_queue_scopes"
#define PLAID_PI_BOOT_START pi_effect_boot_start
#define PLAID_PI_BOOT_FINISH pi_effect_boot_finish
#include "../030-ares-boot-pi-history/observer.hpp"

static u64 bootRequestNext=0, bootRequestActive=0, bootRequestToken=0;
static u32 bootRequestDirection=0, bootRequestDram=0, bootRequestPbus=0, bootRequestLength=0;
static bool bootRequestOutcome=false;
static std::map<u64,u64> bootTokenRequests;
static u64 bootRemovedToken=0, bootDispatchToken=0, bootDispatchRequest=0;
static u32 bootRemovedEvent=0, bootDispatchEvent=0;
static bool bootRemovedReady=false, bootDispatchActive=false;

static void queue_boot_record(const char* kind) {
  // Queue/request scheduling must not create an ordinary backing-fetch witness.
  if(accessBootActive || accessBootPending) std::abort();
  access_boot_record(kind);
}
static u64 queue_boot_request(u64 token) {
  auto it=bootTokenRequests.find(token);
  return it==bootTokenRequests.end() ? 0 : it->second;
}
static void queue_boot_container(u32 kind,const void* owner,u32 slot,u32 other,
                                  u32 event,u32 clock,bool valid) {
  if(!accessBootTrace) return;
  if(bootRemovedReady && kind!=6 && kind!=7) std::abort();
  queue_identity(kind,owner,slot,other,event,clock,valid);
  u64 token=queueIdentityRecords.back().token;
  if((kind==2 || kind==4) && bootRequestActive && event==bootRequestDirection) {
    if(bootRequestOutcome) std::abort();
    bootRequestOutcome=true;
    if(kind==4) { bootRequestToken=token; bootTokenRequests.emplace(token,bootRequestActive); }
  }
  if(kind==5) {
    bootRemovedReady=valid; bootRemovedToken=valid ? token : 0; bootRemovedEvent=event;
  }
  if(kind==1 || (kind==9 && valid)) {
    bootTokenRequests.clear(); bootRemovedReady=false; bootRemovedToken=0;
  }
  queue_boot_record("queue");
  std::fprintf(accessBootTrace,",\"kind\":%u,\"slot\":%u,\"other\":%u,\"event\":%u,\"clock\":%u,\"valid\":%s,\"token\":%llu,\"request\":%llu,\"active_request\":%llu}\n",
    kind,slot,other,event,clock,valid ? "true" : "false",(unsigned long long)token,
    (unsigned long long)queue_boot_request(token),(unsigned long long)bootRequestActive);
}
static void queue_boot_io(bool begin,u32 direction,u32 dram,u32 pbus,u32 length) {
  if(!accessBootTrace) return;
  if(begin) {
    if(bootRequestActive || bootDispatchActive || direction>1 || ++bootRequestNext==0) std::abort();
    bootRequestActive=bootRequestNext; bootRequestToken=0; bootRequestOutcome=false;
    bootRequestDirection=direction; bootRequestDram=dram; bootRequestPbus=pbus; bootRequestLength=length;
  } else if(!bootRequestActive || !bootRequestOutcome || direction!=bootRequestDirection) std::abort();
  queue_boot_record(begin ? "pi_request_begin" : "pi_request_end");
  std::fprintf(accessBootTrace,",\"request\":%llu,\"direction\":%u,\"token\":%llu,\"dram\":%u,\"pbus\":%u,\"length\":%u}\n",
    (unsigned long long)bootRequestActive,bootRequestDirection,(unsigned long long)bootRequestToken,
    bootRequestDram,bootRequestPbus,bootRequestLength);
  if(!begin) bootRequestActive=0;
}
static void queue_boot_dispatch(bool begin,u32 event) {
  if(!accessBootTrace) return;
  if(begin) {
    if(bootDispatchActive || bootRequestActive || !bootRemovedReady || bootRemovedEvent!=event) std::abort();
    bootDispatchActive=true; bootDispatchToken=bootRemovedToken;
    bootDispatchRequest=queue_boot_request(bootDispatchToken); bootDispatchEvent=event;
    bootRemovedReady=false;
  } else if(!bootDispatchActive || bootDispatchEvent!=event) std::abort();
  queue_boot_record(begin ? "dispatch_begin" : "dispatch_end");
  std::fprintf(accessBootTrace,",\"event\":%u,\"token\":%llu,\"request\":%llu}\n",
    bootDispatchEvent,(unsigned long long)bootDispatchToken,(unsigned long long)bootDispatchRequest);
  if(!begin) { bootDispatchActive=false; bootDispatchToken=bootDispatchRequest=0; }
}
static void queue_boot_pi(u32 event,u32 dram,u32 pbus,u32 length,u32 lane,u32 value) {
  if(!accessBootTrace) return;
  if(event==1) {
    if(!bootRequestActive || bootRequestDirection!=1 || !bootRequestOutcome) std::abort();
    queue_boot_record("pi_copy_request");
    std::fprintf(accessBootTrace,",\"transfer\":%llu,\"request\":%llu,\"token\":%llu}\n",
      (unsigned long long)(bootPiTransfer+1),(unsigned long long)bootRequestActive,(unsigned long long)bootRequestToken);
  }
  if(event==8) {
    queue_boot_record("pi_status_scope");
    std::fprintf(accessBootTrace,",\"dispatch\":%s,\"event\":%u,\"token\":%llu,\"request\":%llu}\n",
      bootDispatchActive ? "true" : "false",bootDispatchActive ? bootDispatchEvent : 0,
      (unsigned long long)bootDispatchToken,(unsigned long long)bootDispatchRequest);
  }
  // Preserve legacy v1 fields exactly. Its last-copy status context is metadata,
  // while the new record above supplies independently observed dispatch identity.
  access_boot_pi(event,dram,pbus,length,lane,value);
}
static void access_boot_start(const char* path,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  pi_effect_boot_start(path,romHash,budget,mappedSize,firmwareHash);
  queueIdentityOwner=&ares::Nintendo64::queue;
  nall::plaidQueueObserver=queue_boot_container;
  plaidPiIoDmaObserver=queue_boot_io;
  plaidCpuQueueDispatchObserver=queue_boot_dispatch;
  plaidPiDmaObserver=queue_boot_pi;
}
static void access_boot_finish(u64 fetches) {
  if(bootRequestActive || bootDispatchActive || bootRemovedReady) std::abort();
  nall::plaidQueueObserver=nullptr; plaidPiIoDmaObserver=nullptr; plaidCpuQueueDispatchObserver=nullptr;
  pi_effect_boot_finish(fetches);
}
