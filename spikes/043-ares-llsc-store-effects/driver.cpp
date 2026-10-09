/* SPDX-License-Identifier: ISC
 * Plaid exact-pin ares conditional-store mutation experiment.
 */
#ifndef PLAID_LLSC_SENSOR
#define PLAID_LLSC_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_LLSC_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 DataPhys = 0x2000;
static constexpr u32 CodePhys = 0x6000;
static constexpr u64 CachedData = 0xffffffff80002000ull;
static constexpr u64 UncachedData = 0xffffffffa0002000ull;
static constexpr u64 CachedCode = 0xffffffff80006000ull;
static constexpr u32 WordPayload = 0x11223344u;
static constexpr u64 DualPayload = 0x1122334455667788ull;

struct CaseFact {
  u32 id;
  const char* name;
  u32 width;
  bool cached, same, failed, fault;
  u64 rt;
  u32 exception;
  u64 badva;
  u32 dirtyBefore, dirtyAfter;
  std::vector<u8> initial, beforeWriteback, resident, after;
  string digest;
};

static void set_observers(bool enabled) {
#if PLAID_LLSC_SENSOR
  plaidRdramScalarObserver = enabled ? llsc_scalar_observer : nullptr;
  plaidRdramBurstObserver = enabled ? llsc_burst_observer : nullptr;
#else
  (void)enabled;
#endif
}
static void put_word(u32 address, u32 value) {
#if PLAID_LLSC_SENSOR
  auto scalar = plaidRdramScalarObserver;
  auto burst = plaidRdramBurstObserver;
  plaidRdramScalarObserver=nullptr; plaidRdramBurstObserver=nullptr;
#endif
  rdram.ram.write<Word>(address,value,RBusDevice::ARES_DEBUGGER);
#if PLAID_LLSC_SENSOR
  plaidRdramScalarObserver=scalar; plaidRdramBurstObserver=burst;
#endif
}
static std::vector<u8> backing(u32 count) {
#if PLAID_LLSC_SENSOR
  auto scalar = plaidRdramScalarObserver;
  auto burst = plaidRdramBurstObserver;
  plaidRdramScalarObserver=nullptr; plaidRdramBurstObserver=nullptr;
#endif
  std::vector<u8> out;
  for(u32 i=0;i<count;i++) out.push_back(rdram.ram.read<Byte>(DataPhys+i,RBusDevice::ARES_DEBUGGER));
#if PLAID_LLSC_SENSOR
  plaidRdramScalarObserver=scalar; plaidRdramBurstObserver=burst;
#endif
  return out;
}
static std::vector<u8> resident(u32 count) {
  std::vector<u8> out;
  auto& line=cpu.dcache.line(CachedData);
  for(u32 word:line.words) {
    out.push_back(word>>24); out.push_back(word>>16); out.push_back(word>>8); out.push_back(word);
  }
  out.resize(count);
  return out;
}
static void append_u64(std::vector<u8>& out,u64 value) {
  for(int i=7;i>=0;i--) out.push_back(value>>(i*8));
}
static string machine_digest() {
  std::vector<u8> bytes;
  for(auto& r:cpu.ipu.r) append_u64(bytes,r.u64);
  append_u64(bytes,cpu.ipu.hi.u64); append_u64(bytes,cpu.ipu.lo.u64); append_u64(bytes,cpu.ipu.pc);
  append_u64(bytes,cpu.effectiveCount()); append_u64(bytes,cpu.scc.ll); append_u64(bytes,cpu.scc.llbit);
  append_u64(bytes,cpu.scc.cause.exceptionCode); append_u64(bytes,cpu.scc.badVirtualAddress);
  for(const auto& line:cpu.dcache.lines) {
    append_u64(bytes,line.tagKey); append_u64(bytes,line.dirty); append_u64(bytes,line.index);
    for(u32 w:line.words) append_u64(bytes,w);
  }
  bytes.insert(bytes.end(),rdram.ram.data,rdram.ram.data+rdram.ram.size);
  return nall::Hash::SHA256(std::span<const u8>{bytes.data(),bytes.size()}).digest();
}
static u32 encode_i(u32 op,u32 rs,u32 rt,u16 imm) { return op<<26 | rs<<21 | rt<<16 | imm; }

static CaseFact run_case(u32 id,const char* name,u32 width,bool cached,bool same,bool failed,bool fault,bool traced) {
  set_observers(false);
  cpu.dcache.power(false); cpu.icache.power(false);
  cpu.scc.status.errorLevel=0; cpu.scc.status.exceptionLevel=0; cpu.scc.cause.exceptionCode=0; cpu.scc.badVirtualAddress=0;
  cpu.context.setMode(); cpu.context.endian=CPU::Context::Big; cpu.scc.llbit=0; cpu.scc.ll=0;
  for(auto& r:cpu.ipu.r) r.u64=0;

  u64 payload = width==4 ? WordPayload : DualPayload;
  u32 hi = width==4 ? (u32)payload : (u32)(payload>>32);
  u32 lo = width==4 ? 0xa5a6a7a8u : (u32)payload;
  put_word(DataPhys+0, same ? hi : 0xa1a2a3a4u);
  put_word(DataPhys+4, same && width==8 ? lo : 0xb1b2b3b4u);
  put_word(DataPhys+8,0xc1c2c3c4u); put_word(DataPhys+12,0xd1d2d3d4u);

  u32 pc=CodePhys;
  if(!failed) {
    put_word(pc,encode_i(width==4?0x30:0x34,16,8,0)); pc+=4;
  }
  put_word(pc,encode_i(width==4?0x38:0x3c,16,9,fault?1:0)); pc+=4;
  if(cached && !failed && !fault) put_word(pc,0xbe190000u);

  cpu.ipu.r[16].u64=cached ? CachedData : UncachedData;
  cpu.ipu.r[9].u64=payload;
  cpu.pipeline.setPc(CachedCode);
#if PLAID_LLSC_SENSOR
  llscCaseId=id; llscStage=1;
#endif
  set_observers(traced);
  auto initial=backing(width);
  u32 instructions = failed ? 1 : 2;
  for(u32 i=0;i<instructions;i++) if(cpu.instruction()) cpu.synchronize();
  auto before=backing(width);
  u32 dirtyBefore = cached ? cpu.dcache.line(CachedData).dirty : 0;
  auto residentBytes = cached ? resident(width) : std::vector<u8>{};
  u64 rt=cpu.ipu.r[9].u64;
  u32 exception=cpu.scc.cause.exceptionCode;
  u64 badva=cpu.scc.badVirtualAddress;
  if(cached && !failed && !fault) {
#if PLAID_LLSC_SENSOR
    llscStage=2;
#endif
    if(cpu.instruction()) cpu.synchronize();
  }
  auto after=backing(width);
  u32 dirtyAfter = cached ? cpu.dcache.line(CachedData).dirty : 0;
  set_observers(false);
  return {id,name,width,cached,same,failed,fault,rt,exception,badva,dirtyBefore,dirtyAfter,initial,before,residentBytes,after,machine_digest()};
}
static void print_bytes(const std::vector<u8>& v) {
  std::printf("["); for(size_t i=0;i<v.size();i++) std::printf("%s%u",i?",":"",(u32)v[i]); std::printf("]");
}
int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  Headless frontend; platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid LL/SC store effects"); frontend.cartPak->setAttribute("region","NTSC"); frontend.cartPak->setAttribute("cic","CIC-NUS-6102"); frontend.cartPak->append("program.rom",8192);
  Node::System root; if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true"); option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect(); ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data=hidden.data(); rdram.mapIdentity=1;

  std::vector<CaseFact> facts;
  u32 id=0;
  for(u32 width:{4u,8u}) {
    const char* p=width==4?"sc":"scd";
    string n;
    n=string(p)+"_fail_uncached"; facts.push_back(run_case(++id,strdup(n.data()),width,false,false,true,false,traced));
    n=string(p)+"_fault_uncached"; facts.push_back(run_case(++id,strdup(n.data()),width,false,false,false,true,traced));
    n=string(p)+"_uncached_changed"; facts.push_back(run_case(++id,strdup(n.data()),width,false,false,false,false,traced));
    n=string(p)+"_uncached_same"; facts.push_back(run_case(++id,strdup(n.data()),width,false,true,false,false,traced));
    n=string(p)+"_cached_changed"; facts.push_back(run_case(++id,strdup(n.data()),width,true,false,false,false,traced));
    n=string(p)+"_cached_same"; facts.push_back(run_case(++id,strdup(n.data()),width,true,true,false,false,traced));
  }

  std::printf("{");
#if PLAID_LLSC_SENSOR
  llsc_print_events();
#else
  std::printf("\"scalar_events\":[],\"burst_events\":[]");
#endif
  std::printf(",\"facts\":[");
  for(size_t i=0;i<facts.size();i++) { auto& f=facts[i];
    std::printf("%s{\"id\":%u,\"name\":\"%s\",\"width\":%u,\"cached\":%s,\"same\":%s,\"failed\":%s,\"fault\":%s,\"rt\":%llu,\"exception\":%u,\"badva\":%llu,\"dirty_before\":%u,\"dirty_after\":%u,\"initial\":",
      i?",":"",f.id,f.name,f.width,f.cached?"true":"false",f.same?"true":"false",f.failed?"true":"false",f.fault?"true":"false",(unsigned long long)f.rt,f.exception,(unsigned long long)f.badva,f.dirtyBefore,f.dirtyAfter);
    print_bytes(f.initial); std::printf(",\"before_writeback\":"); print_bytes(f.beforeWriteback); std::printf(",\"resident\":"); print_bytes(f.resident); std::printf(",\"after\":"); print_bytes(f.after); std::printf(",\"digest\":\"%s\"}",f.digest.data());
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload(); return 0;
}
