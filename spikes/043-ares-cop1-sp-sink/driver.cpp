/* SPDX-License-Identifier: ISC
 * Plaid research harness for pinned ares COP1 stores into SP DMEM/IMEM.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>
using namespace ares;
using namespace ares::Nintendo64;

struct Headless : ares::Platform {
  std::shared_ptr<vfs::directory> systemPak = std::make_shared<vfs::directory>();
  std::shared_ptr<vfs::directory> cartPak = std::make_shared<vfs::directory>();
  auto pak(Node::Object node) -> std::shared_ptr<vfs::directory> override {
    return node->name() == "Nintendo 64 Cartridge" ? cartPak : systemPak;
  }
};

struct Sink { u32 address, bank, offset, value; bool cpu; };
static std::vector<Sink> sinks;
static void spWord(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  if(write) sinks.push_back({address,bank,offset,value,originCpu});
}

static constexpr u64 FPRS[4] = {
  0x1122334455667788ull, 0x99aabbccddeeff00ull,
  0x0123456789abcdefull, 0xfedcba9876543210ull,
};

static void resetCpu(bool fr, bool cu1) {
  cpu.dcache.power(false);
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.enable.coprocessor1 = cu1;
  cpu.scc.status.floatingPointMode = fr;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.coprocessorError = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Big;
  cpu.pipeline.setPc(0xffffffffa0001000ull);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  for(auto& r : cpu.fpu.r) r.u64 = 0;
  for(u32 i=0;i<4;i++) cpu.fpu.r[i].u64 = FPRS[i];
}

static void resetSp() {
  for(u32 i=0;i<32;i++) {
    rsp.dmem.write<Byte>(i,0x80+i);
    rsp.imem.write<Byte>(i,0xc0+i);
  }
}

static void printBank(const char* key, bool imem) {
  std::printf("\"%s\":[",key);
  auto& memory = imem ? rsp.imem : rsp.dmem;
  for(u32 i=0;i<16;i++) std::printf("%s%u",i ? "," : "",(u32)memory.read<Byte>(i));
  std::printf("]");
}

static void printSinks() {
  std::printf("\"sinks\":[");
  for(size_t i=0;i<sinks.size();i++) {
    const auto& s=sinks[i];
    std::printf("%s{\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u,\"cpu\":%s}",
      i ? "," : "",s.address,s.bank,s.offset,s.value,s.cpu ? "true" : "false");
  }
  std::printf("]");
}

int main(int argc,char** argv) {
  if(argc!=7) return 2;
  const char* op=argv[1];
  const char* bank=argv[2];
  int fr=std::atoi(argv[3]);
  int ft=std::atoi(argv[4]);
  const char* mode=argv[5];
  int offset=std::atoi(argv[6]);
  if(std::strcmp(op,"SWC1") && std::strcmp(op,"SDC1")) return 2;
  if(std::strcmp(bank,"dmem") && std::strcmp(bank,"imem")) return 2;
  if(fr<0 || fr>1 || ft<0 || ft>3 || offset<0 || offset>15) return 2;
  if(std::strcmp(mode,"ok") && std::strcmp(mode,"cu1off") && std::strcmp(mode,"misalign")) return 2;
  bool isImem=!std::strcmp(bank,"imem");
  bool cu1=std::strcmp(mode,"cu1off");

  Headless frontend; platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid COP1 SP sink fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true"); option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect(); ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  resetCpu(fr,cu1); resetSp(); sinks.clear();
  u64 base=isImem ? 0xffffffffa4001000ull : 0xffffffffa4000000ull;
  if(!std::strcmp(mode,"misalign")) offset = !std::strcmp(op,"SWC1") ? 1 : 4;
  cpu.ipu.r[1].u64=base;

  std::printf("{\"op\":\"%s\",\"bank\":\"%s\",\"fr\":%d,\"ft\":%d,\"mode\":\"%s\",\"offset\":%d,",
    op,bank,fr,ft,mode,offset);
  printBank("before_target",isImem); std::printf(","); printBank("before_other",!isImem); std::printf(",");

  plaidSpWordObserver=spWord;
  if(!std::strcmp(op,"SWC1")) cpu.SWC1(ft,cpu.ipu.r[1],offset);
  else cpu.SDC1(ft,cpu.ipu.r[1],offset);
  plaidSpWordObserver=nullptr;

  std::printf("\"exception\":%u,\"coprocessor_error\":%u,\"badva\":%llu,",
    (u32)cpu.scc.cause.exceptionCode,(u32)cpu.scc.cause.coprocessorError,(unsigned long long)cpu.scc.badVirtualAddress);
  printBank("after_target",isImem); std::printf(","); printBank("after_other",!isImem); std::printf(","); printSinks(); std::printf("}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
