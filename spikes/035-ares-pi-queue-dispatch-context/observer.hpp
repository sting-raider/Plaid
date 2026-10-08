/* SPDX-License-Identifier: ISC
 * Original component chronology joining actual request/queue/CPU/status scopes.
 */
#include "../032-ares-queue-identity/observer.hpp"
struct PiQueueRecord {
  u32 ordinal, phase, kind, subkind, slot, other, event, clock;
  bool valid;
  u64 token, call;
  u32 dram, pbus, length, lane, value;
};
inline std::vector<PiQueueRecord> piQueueRecords;
inline u64 piQueueNextCall=0, piQueueCall=0, piQueueRemoved=0, piQueueDispatch=0;
inline u32 piQueueRemovedEvent=0;
inline bool piQueueDispatchActive=false;
inline void pi_queue_emit(PiQueueRecord e) {
  e.ordinal=piQueueRecords.size()+1; e.phase=queueIdentityPhase;
  piQueueRecords.push_back(e);
}
inline void pi_queue_container(u32 kind,const void* owner,u32 slot,u32 other,u32 event,u32 clock,bool valid) {
  queue_identity(kind,owner,slot,other,event,clock,valid);
  auto token=queueIdentityRecords.back().token;
  if(kind==5) { piQueueRemoved=valid ? token : 0; piQueueRemovedEvent=event; }
  if(kind==1 || kind==9) piQueueRemoved=0;
  pi_queue_emit({0,0,kind,0,slot,other,event,clock,valid,token,piQueueCall,0,0,0,0,0});
}
inline void pi_queue_io(bool begin,u32 direction,u32 dram,u32 pbus,u32 length) {
  if(begin) { assert(!piQueueCall); piQueueCall=++piQueueNextCall; }
  else assert(piQueueCall);
  pi_queue_emit({0,0,begin ? 10u : 11u,0,0,0,direction,0,true,0,piQueueCall,dram,pbus,length,0,0});
  if(!begin) piQueueCall=0;
}
inline void pi_queue_dispatch(bool begin,u32 event) {
  if(begin) {
    assert(!piQueueDispatchActive && piQueueRemovedEvent==event);
    piQueueDispatchActive=true; piQueueDispatch=piQueueRemoved;
  } else assert(piQueueDispatchActive);
  pi_queue_emit({0,0,begin ? 12u : 13u,0,0,0,event,0,true,piQueueDispatch,0,0,0,0,0,0});
  if(!begin) { piQueueDispatchActive=false; piQueueDispatch=piQueueRemoved=0; }
}
inline void pi_queue_dma(u32 kind,u32 dram,u32 pbus,u32 length,u32 lane,u32 value) {
  pi_queue_emit({0,0,14,kind,0,0,0,0,true,piQueueDispatchActive ? piQueueDispatch : 0,
    piQueueCall,dram,pbus,length,lane,value});
}
inline void pi_queue_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(write && device==5) {
    assert(bytes==1 && value<256 && piQueueCall);
    pi_queue_emit({0,0,15,0,0,0,0,0,true,0,piQueueCall,address,0,bytes,0,(u32)value});
  }
}
inline void print_pi_queue() {
  std::printf("\"events\":[");
  for(size_t i=0;i<piQueueRecords.size();i++) {
    const auto& e=piQueueRecords[i];
    std::printf("%s{\"ordinal\":%u,\"phase\":%u,\"kind\":%u,\"subkind\":%u,\"slot\":%u,\"other\":%u,\"event\":%u,\"clock\":%u,\"valid\":%s,\"token\":%llu,\"call\":%llu,\"dram\":%u,\"pbus\":%u,\"length\":%u,\"lane\":%u,\"value\":%u}",
      i ? "," : "",e.ordinal,e.phase,e.kind,e.subkind,e.slot,e.other,e.event,e.clock,
      e.valid ? "true" : "false",(unsigned long long)e.token,(unsigned long long)e.call,
      e.dram,e.pbus,e.length,e.lane,e.value);
  }
  std::printf("]");
}
