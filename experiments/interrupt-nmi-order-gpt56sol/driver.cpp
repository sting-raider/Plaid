/* SPDX-License-Identifier: ISC
 * Plaid research harness: simultaneous maskable interrupt/NMI ordering.
 */
#ifndef PLAID_FETCH_SENSOR
#define PLAID_FETCH_SENSOR 1
#endif
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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

static u32 fetchCompletions = 0;
#if PLAID_FETCH_SENSOR
static void fetchObserver(bool begin, u64, u32, u32, bool, u32) {
  if(!begin) ++fetchCompletions;
}
#endif

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

struct Snap {
  u64 pc, epc, errorepc, s0, s1;
  u32 exl, erl, bev, ip, nmi, fetches;
};

static auto snap(u32 before) -> Snap {
  return {cpu.ipu.pc, cpu.scc.epc, cpu.scc.epcError,
    cpu.ipu.r[16].u64, cpu.ipu.r[17].u64,
    (u32)cpu.scc.status.exceptionLevel, (u32)cpu.scc.status.errorLevel,
    (u32)cpu.scc.status.vectorLocation, (u32)cpu.scc.cause.interruptPending,
    (u32)cpu.scc.nmiPending, fetchCompletions - before};
}

int main(int argc, char** argv) {
  if(argc != 12) return 2;
  const char* mode = argv[1];
  const char* name = argv[2];
  int bev = std::atoi(argv[3]), ie = std::atoi(argv[4]);
  int exl = std::atoi(argv[5]), erl = std::atoi(argv[6]);
  u32 ip = (u32)std::strtoul(argv[7], nullptr, 0);
  u32 im = (u32)std::strtoul(argv[8], nullptr, 0);
  int nmi = std::atoi(argv[9]);
  int clearNmi = std::atoi(argv[10]), clearIp = std::atoi(argv[11]);
  if(strcmp(mode,"plain") && strcmp(mode,"traced")) return 2;
  if((bev|ie|exl|erl|nmi|clearNmi|clearIp) & ~1) return 2;
  if(ip > 0xff || im > 0xff) return 2;
  bool traced = !strcmp(mode,"traced");
#if !PLAID_FETCH_SENSOR
  traced = false;
#endif

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid IRQ NMI ordering fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true"); option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect(); ares::Nintendo64::system.power(false);
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data(); rdram.mapIdentity = 1;
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.icache.power(false); cpu.context.endian = CPU::Context::Endian::Big;

  constexpr u64 start = 0xffffffffa0000000ull;
  constexpr u64 epcSentinel = 0x123456789abcdef0ull;
  constexpr u64 errorSentinel = 0x5555666677778888ull;
  put(0x000, 0x24101234); // ADDIU $s0,$zero,0x1234
  put(0x004, 0x00000000);
  put(0x180, 0x24115678); // ADDIU $s1,$zero,0x5678 at BEV=0 IRQ root
  put(0x184, 0x00000000);

  cpu.scc.status.vectorLocation = bev; cpu.scc.status.interruptEnable = ie;
  cpu.scc.status.exceptionLevel = exl; cpu.scc.status.errorLevel = erl;
  cpu.scc.status.interruptMask = im; cpu.scc.cause.interruptPending = 0;
  cpu.scc.epc = epcSentinel; cpu.scc.epcError = errorSentinel;
  cpu.context.setMode(); cpu.pipeline.setPc(start); cpu.scc.nmiPending = nmi;
  for(u32 bit=0; bit<8; ++bit) if(ip & (1u<<bit)) cpu.setInterruptPending(bit,1);
#if PLAID_FETCH_SENSOR
  plaidCpuFetchObserver = traced ? fetchObserver : nullptr;
#endif

  u32 f0 = fetchCompletions;
  if(!cpu.instruction()) return 5;
  auto first = snap(f0);
  if(clearNmi) cpu.scc.nmiPending = 0;
  if(clearIp) for(u32 bit=0; bit<8; ++bit) if(ip & (1u<<bit)) cpu.setInterruptPending(bit,0);
  u32 f1 = fetchCompletions;
  if(!cpu.instruction()) return 6;
  auto second = snap(f1);

  std::printf("{\"name\":\"%s\",\"mode\":\"%s\",\"bev_in\":%d,\"ie\":%d,\"exl_in\":%d,\"erl_in\":%d,\"ip\":%u,\"im\":%u,\"nmi_in\":%d,\"clear_nmi\":%d,\"clear_ip\":%d,"
    "\"first_pc\":%llu,\"first_epc\":%llu,\"first_errorepc\":%llu,\"first_exl\":%u,\"first_erl\":%u,\"first_bev\":%u,\"first_ip\":%u,\"first_nmi\":%u,\"first_s0\":%llu,\"first_s1\":%llu,\"fetches_first\":%u,"
    "\"second_pc\":%llu,\"second_epc\":%llu,\"second_errorepc\":%llu,\"second_exl\":%u,\"second_erl\":%u,\"second_bev\":%u,\"second_ip\":%u,\"second_nmi\":%u,\"second_s0\":%llu,\"second_s1\":%llu,\"fetches_second\":%u}\n",
    name, mode, bev,ie,exl,erl,ip,im,nmi,clearNmi,clearIp,
    (unsigned long long)first.pc,(unsigned long long)first.epc,(unsigned long long)first.errorepc,first.exl,first.erl,first.bev,first.ip,first.nmi,(unsigned long long)first.s0,(unsigned long long)first.s1,first.fetches,
    (unsigned long long)second.pc,(unsigned long long)second.epc,(unsigned long long)second.errorepc,second.exl,second.erl,second.bev,second.ip,second.nmi,(unsigned long long)second.s0,(unsigned long long)second.s1,second.fetches);
  ares::Nintendo64::system.unload(); return 0;
}
