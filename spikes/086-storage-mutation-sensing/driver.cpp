/* SPDX-License-Identifier: ISC
 * Original storage census fixture. No ROM, scheduler or broad coverage claim.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstring>
using namespace ares;
using namespace ares::Nintendo64;
namespace Storage = ares::Nintendo64::Memory;
#ifndef PLAID_STORAGE_SENSOR
#define PLAID_STORAGE_SENSOR 1
#endif
struct Effect { u32 kind, address, bytes; u64 value; };
static std::vector<Effect> effects;
#if PLAID_STORAGE_SENSOR
static void observe(const void* memory,u32 kind,u32 address,u32 bytes,u64 value) {
  if(memory == static_cast<Storage::Writable*>(&rdram.ram)) effects.push_back({kind,address,bytes,value});
}
#endif
static void snapshot(const char* name,bool first=false) {
  std::printf("%s{\"name\":\"%s\",\"ram\":[",first ? "" : ",",name);
  for(u32 n=0;n<rdram.ram.size;n++) std::printf("%s%u",n ? "," : "",(u32)static_cast<Storage::Writable&>(rdram.ram).read<Byte>(n));
  std::printf("],\"hidden\":[");
  for(u32 n=0;n<128;n++) std::printf("%s%u",n ? "," : "",rdram.hidden.data[n]);
  std::printf("],\"ri_error\":%u,\"pc\":%llu,\"gpr\":[",(u32)ri.io.error,(unsigned long long)cpu.ipu.pc);
  for(u32 n=0;n<32;n++) std::printf("%s%llu",n ? "," : "",(unsigned long long)cpu.ipu.r[n].u64);
  std::printf("],\"cause\":%u,\"epc\":%llu,\"count\":%llu}",(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,(unsigned long long)cpu.scc.count);
}
int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  rdram.ram.allocate(256,0);
  std::vector<u8> hidden(128,0); rdram.hidden.data=hidden.data();
  rdram.mapIdentity=1;
  std::printf("{\"states\":["); snapshot("initial",true);
#if PLAID_STORAGE_SENSOR
  if(!strcmp(argv[1],"traced")) Storage::plaidMemoryMutationObserver=observe;
#endif
  rdram.ram.write<Word>(0x13,0xf1234567,RBusDevice::VR4300_UNCACHED); snapshot("word");
  rdram.ram.write<Word>(0x13,0xf1234567,RBusDevice::VR4300_UNCACHED); snapshot("equal");
  static_cast<Storage::Writable&>(rdram.ram).write<Word>(0x14,0x10203040); snapshot("base");
  rdram.ram.ebusWrite<Word>(0x18,0x11223344); snapshot("ebus");
  ri.io.currentLoaded=1;ri.io.select=0x14;
  for(auto& chip : rdram.chips) chip={};
  rdram.chips[0].present=1;rdram.chips[0].enable=1;rdram.chips[0].deviceID=2;
  rdram.mapIdentity=0;
  rdram.ram.write<Word>(0x20001c,0x55667788,RBusDevice::SI_DMA); snapshot("translated");
  rdram.ram.write<Word>(0x400020,0xffffffff,RBusDevice::SI_DMA); snapshot("translation_failed");
  rdram.mapIdentity=1;
  rdram.ram.write<Word>(256,0xffffffff,RBusDevice::PI_DMA); snapshot("outside");
  rdram.ram.write<Dual>(0x20,0x0123456789abcdefull,RBusDevice::SP_DMA); snapshot("dual");
  u32 words[]={0x01020304,0x05060708,0x090a0b0c,0x0d0e0f10};
  rdram.ram.writeBurst<DCache>(0x30,words,RBusDevice::VR4300_DCACHE); snapshot("burst");
  static_cast<Storage::Writable&>(rdram.ram).writeUnaligned<Word>(0x41,0xa1b2c3d4); snapshot("unaligned");
  // Different backend requestors all reach this same storage primitive.
  for(auto device : {RBusDevice::PI_DMA,RBusDevice::SI_DMA,RBusDevice::SP_DMA,RBusDevice::DP_DRAW})
    rdram.ram.write<Byte>(0x50+(u32)device,0x100+(u32)device,device);
  snapshot("requestors");
  serializer saved; saved.setWriting(); static_cast<Storage::Writable&>(rdram.ram).serialize(saved); snapshot("saved");
  rdram.ram.write<Half>(0x70,0x12345,RBusDevice::ARES_DEBUGGER); snapshot("after_save");
  saved.setReading(); static_cast<Storage::Writable&>(rdram.ram).serialize(saved); snapshot("restored");
  rdram.ram.fill(0x89abcdef); snapshot("filled");
  auto file=vfs::memory::create(8);file->writem(0x76543210,4);file->writem(0xfedcba98,4);file->seek(0);
  rdram.ram.load(file); snapshot("loaded");
  rdram.ram.reset(); snapshot("retired");
  rdram.ram.allocate(64,0); snapshot("reallocated");
  // Other writable banks must not be mistaken for RDRAM.
  Storage::Writable other;other.allocate(64,0);other.write<Word>(0,1);other.reset();snapshot("foreign");
#if PLAID_STORAGE_SENSOR
  Storage::plaidMemoryMutationObserver=nullptr;
#endif
  std::printf("],\"effects\":[");
  for(size_t n=0;n<effects.size();n++) { const auto& e=effects[n];
    std::printf("%s{\"ordinal\":%zu,\"kind\":%u,\"address\":%u,\"bytes\":%u,\"value\":%llu}",
      n ? "," : "",n+1,e.kind,e.address,e.bytes,(unsigned long long)e.value);
  }
  std::printf("]}\n"); rdram.ram.reset(); return 0;
}
