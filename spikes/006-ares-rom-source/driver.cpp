/* SPDX-License-Identifier: ISC
 * Original bounded ROM-source experiment; reference implementation is separate.
 */
#define main original_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main

#if defined(PLAID_ROM_HALF_ACCESS)
// Project-owned optional result callback; no guest access or device layout change.
static void (*plaidRomHalfObserver)(u32,u16) = nullptr;
#endif

struct RomObserver : PIDevice {
  struct HalfRead { u32 offset; u16 word; };
  std::vector<HalfRead> reads;
  auto piAddress(u32 address, PIDeviceTiming timing) -> bool override {
    return cartridge.romDevice.piAddress(address, timing);
  }
  auto piReadHalf(PIDeviceTiming timing) -> maybe<u16> override {
    auto offset = cartridge.romDevice.piViewOffset;
    auto data = cartridge.romDevice.piReadHalf(timing);
    if(data) {
      reads.push_back({offset, *data});
      #if defined(PLAID_ROM_HALF_ACCESS)
      if(plaidRomHalfObserver) plaidRomHalfObserver(offset,*data);
      #endif
    }
    return data;
  }
  auto piWriteHalf(u16 data, PIDeviceTiming timing) -> void override {
    cartridge.romDevice.piWriteHalf(data, timing);
  }
  auto source(u32 physical, bool cached, u32 word) const -> bool {
    return !cached && reads.size() == 2
      && physical == 0x10000000 + reads[0].offset
      && reads[1].offset == reads[0].offset + 2
      && reads[1].offset + 2 <= cartridge.rom.size
      && ((u32)reads[0].word << 16 | reads[1].word) == word;
  }
};

struct SourceFrontend : Headless {
  RomObserver rom;
  FILE* samples = nullptr;
  auto log(Node::Debugger::Tracer::Tracer node, string_view) -> void override {
    if(node != cpu.debugger.tracer.instruction) return;
    auto word = cpu.disassembler.fetchedWord();
    bool backed = rom.source(plaidFetchAccess.physical, plaidFetchAccess.cached, word);
    std::fprintf(samples,"{\"pc\":%llu,\"word\":%u,\"physical\":%u,\"cached\":%s,\"rom_half_reads\":%zu,\"rom_offset\":",
      (unsigned long long)cpu.ipu.pc, word, plaidFetchAccess.physical,
      plaidFetchAccess.cached ? "true" : "false", rom.reads.size());
    if(backed) std::fprintf(samples,"%u",rom.reads[0].offset);
    else std::fprintf(samples,"null");
    std::fprintf(samples,"}\n");
  }
};

int rom_source_fixture_main(int argc, char** argv) {
  if(argc != 4) return 2;
  bool wrapped = strcmp(argv[1], "original");
  bool traced = !strcmp(argv[1], "traced");
  if(wrapped && !traced && strcmp(argv[1], "plain")) return 2;
  SourceFrontend frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid original source fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8196);
  auto file = frontend.cartPak->write("program.rom");
  file->seek(0x1000); file->writem(0x24100001, 4); file->writem(0x24100002, 4);
  file->seek(0x2000); file->writem(0x24100003, 4); // Unmapped final file word.
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data(); rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  if(wrapped) { pi.detach(cartridge.romDevice); pi.attach(frontend.rom, 0); }
  if(traced) {
    frontend.samples = std::fopen(argv[2], "wb");
    if(!frontend.samples) return 5;
    cpu.debugger.tracer.instruction->setDepth(0);
    cpu.debugger.tracer.instruction->setMask(false);
    cpu.debugger.tracer.instruction->setEnabled(true);
  }
  auto step = [&](u64 pc, u64 expected) {
    frontend.rom.reads.clear(); // Exact current fetch window, before any opcode.
    cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    return cpu.ipu.r[16].u64 == expected && cpu.scc.cause.exceptionCode == 0;
  };
  if(!step(0xffffffffb0001000ull, 1)) return 6;
  // The ROM ignores writes, while PI temporarily latches this identical word.
  pi.writeWord(0x10001000, 0x24100001, cpu);
  if(!step(0xffffffffb0001000ull, 1)) return 7;
  if(!step(0xffffffffb0002000ull, 1)) return 8;
  // Prior data reads cannot be reused as the next instruction's source.
  bus.read<Word>(0x10001000, cpu, RBusDevice::VR4300_UNCACHED);
  pi.writeWord(0x10001000, 0x24100001, cpu);
  if(!step(0xffffffffb0001000ull, 1)) return 9;
  auto& entry = cpu.tlb.entry[0]; entry = {};
  entry.global[0] = entry.global[1] = 1;
  entry.valid[0] = entry.valid[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 2;
  entry.virtualAddress = 0x4000; entry.physicalAddress[0] = 0x10001000;
  entry.synchronize();
  if(!step(0x4000, 1)) return 10;
  cpu.scc.status.privilegeMode = 2; cpu.scc.status.reverseEndian = 1;
  cpu.context.setMode();
  if(!step(0x4000, 2)) return 11;
  auto state = std::fopen(argv[3], "wb"); if(!state) return 5;
  std::fprintf(state,"{\"pc\":%llu,\"regs\":[",(unsigned long long)cpu.ipu.pc);
  for(int n=0;n<32;n++) std::fprintf(state,"%s%llu",n ? "," : "",(unsigned long long)cpu.ipu.r[n].u64);
  std::fprintf(state,"],\"hi\":%llu,\"lo\":%llu,\"count\":%llu,\"exception\":%u,\"epc\":%llu,\"pi_latch\":%u,\"pi_busy\":%u,\"pi_address\":%u,\"mapped_size\":%u}\n",
    (unsigned long long)cpu.ipu.hi.u64,(unsigned long long)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,(u32)pi.io.busLatch,(u32)pi.io.ioBusy,
    (u32)pi.io.pbusAddress,cartridge.rom.size);
  if(std::ferror(state) || std::fclose(state)) return 12;
  if(traced && (std::ferror(frontend.samples) || std::fclose(frontend.samples))) return 12;
  ares::Nintendo64::system.unload();
  return 0;
}

#if !defined(PLAID_ROM_FETCH_SOURCE)
int main(int argc, char** argv) { return rom_source_fixture_main(argc, argv); }
#endif
