/* SPDX-License-Identifier: ISC
 * Original bounded Plaid fetch-observer experiment. No CPU semantics patch.
 */
#if !defined(PLAID_ROM_FETCH_SOURCE)
#define main bounded_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#endif
#include <cstdlib>
#include <nall/hash/sha256.hpp>

struct Observer : Headless {
  #if defined(PLAID_ROM_FETCH_SOURCE)
  RomObserver rom;
  #endif
  FILE* trace = nullptr;
  FILE* messages = nullptr;
  u64 fetches = 0;
  auto log(Node::Debugger::Tracer::Tracer node, string_view message) -> void override {
    if(node == cpu.debugger.tracer.instruction) {
      // The disassembler was passed the exact fetched word by instructionPrologue.
      // No additional guest memory read or TLB translation is performed here.
      auto pc = cpu.ipu.pc;
      #if defined(PLAID_ROM_FETCH_SOURCE)
      auto word = cpu.disassembler.fetchedWord();
      bool backed = rom.source(plaidFetchAccess.physical, plaidFetchAccess.cached, word);
      std::fprintf(trace, "{\"record\":\"fetch\",\"seq\":%llu,\"pc\":%llu,\"word\":%u,\"delay_slot\":%s,\"physical\":%u,\"cached\":%s,\"source\":",
        (unsigned long long)fetches++, (unsigned long long)pc, word,
        cpu.pipeline.inDelaySlot() ? "true" : "false", plaidFetchAccess.physical,
        plaidFetchAccess.cached ? "true" : "false");
      if(backed) std::fprintf(trace,"{\"kind\":\"cartridge_rom\",\"offset\":%u}",rom.reads[0].offset);
      else std::fprintf(trace,"{\"kind\":\"unknown\"}");
      #if defined(PLAID_CACHE_FETCH)
      cache_fetch_fields(trace, pc, plaidFetchAccess.physical, plaidFetchAccess.cached, word);
      #endif
      std::fprintf(trace,"}\n");
      #elif defined(PLAID_PHYSICAL_FETCH)
      std::fprintf(trace, "{\"record\":\"fetch\",\"seq\":%llu,\"pc\":%llu,\"word\":%u,\"delay_slot\":%s,\"physical\":%u,\"cached\":%s}\n",
        (unsigned long long)fetches++, (unsigned long long)pc,
        cpu.disassembler.fetchedWord(), cpu.pipeline.inDelaySlot() ? "true" : "false",
        plaidFetchAccess.physical, plaidFetchAccess.cached ? "true" : "false");
      #else
      std::fprintf(trace, "{\"record\":\"fetch\",\"seq\":%llu,\"pc\":%llu,\"word\":%u,\"delay_slot\":%s}\n",
        (unsigned long long)fetches++, (unsigned long long)pc,
        cpu.disassembler.fetchedWord(), cpu.pipeline.inDelaySlot() ? "true" : "false");
      #endif
    } else if(messages) {
      std::fwrite(message.data(), 1, message.size(), messages);
    }
  }
};

int fetch_observer_main(int argc, char** argv) {
  #if defined(PLAID_PIF_BOOT)
  if(argc != 8) return 2;
  #else
  if(argc != 7) return 2;
  #endif
  bool traced = !strcmp(argv[1], "traced");
  if(!traced && strcmp(argv[1], "plain")) return 2;
  auto bytes = nall::file::read(argv[2]);
  if(bytes.size() < 4096 || bytes.size() > 64_MiB || bytes.size() % 4) return 3;
  u32 budget = std::strtoul(argv[6], nullptr, 10);
  if(!budget || budget > 10000000) return 3;
  Observer frontend;
  platform = &frontend;
  #if defined(PLAID_PIF_BOOT)
  auto firmware = nall::file::read(argv[7]);
  if(firmware.size() != 0x7c0 || !Accuracy::PIF::IPL2Checksum) return 3;
  auto firmwareHash = nall::Hash::SHA256(std::span<const u8>{firmware.data(), firmware.size()}).digest();
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  #endif
  frontend.messages = std::fopen(argv[5], "wb");
  if(!frontend.messages) return 4;
  frontend.cartPak->setAttribute("title", "Pinned n64-systemtest research");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", std::span<const u8>{bytes.data(), bytes.size()});
  ares::Nintendo64::system.expansionPak = true;
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 5;
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  #if defined(PLAID_ROM_FETCH_SOURCE)
  pi.detach(cartridge.romDevice); pi.attach(frontend.rom, 0);
  #endif
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 6;
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  #if !defined(PLAID_PIF_BOOT)
  // Declared post-IPL2 entry, not a claim of an authentic complete boot.
  for(u32 offset=0; offset<4096; offset+=4)
    rsp.dmem.write<Word>(offset, (u32)bytes[offset]<<24 | (u32)bytes[offset+1]<<16 |
      (u32)bytes[offset+2]<<8 | bytes[offset+3]);
  cpu.ipu.r[22].u64 = 0x3f;
  cpu.pipeline.setPc(0xffffffffa4000040ull);
  #endif
  if(traced) {
    frontend.trace = std::fopen(argv[3], "wb");
    if(!frontend.trace) return 4;
    auto romHash = nall::Hash::SHA256(std::span<const u8>{bytes.data(), bytes.size()}).digest();
    #if defined(PLAID_BOOT_PROFILE)
    boot_profile_header(frontend.trace, romHash.data(), budget, cartridge.rom.size, firmwareHash.data());
    #elif defined(PLAID_PIF_BOOT)
    std::fprintf(frontend.trace, "{\"record\":\"header\",\"format\":\"plaid-ares-fetch-research-v3\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"initial_state\":\"cpu_power_pif_entry\",\"mapped_cartridge_size\":%u,\"source_policy\":\"delegated_rom_halves_before_prologue\",\"firmware_sha256\":\"%s\",\"pif_processor\":\"reference_hle\",\"pif_checksum_enforced\":true}\n", romHash.data(), budget, cartridge.rom.size, firmwareHash.data());
    #elif defined(PLAID_ROM_FETCH_SOURCE)
    std::fprintf(frontend.trace, "{\"record\":\"header\",\"format\":\"plaid-ares-fetch-research-v2\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"initial_state\":\"declared_post_ipl2_sp_entry\",\"mapped_cartridge_size\":%u,\"source_policy\":\"delegated_rom_halves_before_prologue\"}\n", romHash.data(), budget, cartridge.rom.size);
    #elif defined(PLAID_PHYSICAL_FETCH)
    std::fprintf(frontend.trace, "{\"record\":\"header\",\"format\":\"plaid-ares-fetch-research-v1\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"initial_state\":\"declared_post_ipl2_sp_entry\",\"mapped_cartridge_size\":%u}\n", romHash.data(), budget, cartridge.rom.size);
    #else
    std::fprintf(frontend.trace, "{\"record\":\"header\",\"format\":\"plaid-ares-fetch-research-v0\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"initial_state\":\"declared_post_ipl2_sp_entry\"}\n", romHash.data(), budget);
    #endif
    cpu.debugger.tracer.instruction->setDepth(0);
    cpu.debugger.tracer.instruction->setMask(false);
    cpu.debugger.tracer.instruction->setEnabled(true);
  }
  for(u32 step=0; step<budget; step++) {
    #if defined(PLAID_ROM_FETCH_SOURCE)
    frontend.rom.reads.clear();
    #endif
    if(cpu.instruction()) cpu.synchronize();
  }
  if(traced) {
    std::fprintf(frontend.trace, "{\"record\":\"end\",\"fetch_count\":%llu,\"reason\":\"instruction_call_budget\"}\n",
      (unsigned long long)frontend.fetches);
    if(std::ferror(frontend.trace) || std::fclose(frontend.trace)) return 7;
  }
  auto state = std::fopen(argv[4], "wb");
  if(!state) return 4;
  std::fprintf(state, "{\"pc\":%llu,\"regs\":[", (unsigned long long)cpu.ipu.pc);
  for(int n=0;n<32;n++) std::fprintf(state, "%s%lld", n ? "," : "", (long long)(int64_t)cpu.ipu.r[n].u64);
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto spHash = nall::Hash::SHA256(std::span<const u8>{rsp.dmem.data, rsp.dmem.size}).digest();
  std::fprintf(state, "],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"exception\":%u,\"epc\":%llu,\"pif_state\":%u,\"rdram_identity\":%u,\"rdram_size\":%u,\"ram_sha256\":\"%s\",\"sp_sha256\":\"%s\"",
    (long long)(int64_t)cpu.ipu.hi.u64, (long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(), (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc, (u32)pif.state, (u32)rdram.mapIdentity, rdram.ram.size,
    ramHash.data(), spHash.data());
  #if defined(PLAID_PIF_BOOT)
  std::fprintf(state, ",\"configuration\":%u,\"status\":%u,\"pif_checksum_enforced\":true,\"pi\":{\"dma_busy\":%u,\"io_busy\":%u,\"dram_address\":%u,\"pbus_address\":%u,\"write_length\":%u,\"bsd1\":[%u,%u,%u,%u]}",
    (u32)cpu.getControlRegister(16), (u32)cpu.getControlRegister(12),
    (u32)pi.io.dmaBusy, (u32)pi.io.ioBusy, (u32)pi.io.dramAddress,
    (u32)pi.io.pbusAddress, (u32)pi.io.writeLength, (u32)pi.bsd1.latency,
    (u32)pi.bsd1.pulseWidth, (u32)pi.bsd1.pageSize, (u32)pi.bsd1.releaseDuration);
  #endif
  #if defined(PLAID_CACHE_FETCH)
  cache_checkpoint_fields(state);
  #endif
  std::fprintf(state, "}\n");
  if(std::ferror(state) || std::fclose(state)) return 7;
  if(std::ferror(frontend.messages) || std::fclose(frontend.messages)) return 7;
  ares::Nintendo64::system.unload();
  return 0;
}

#if !defined(PLAID_PHYSICAL_FETCH)
int main(int argc, char** argv) { return fetch_observer_main(argc, argv); }
#endif
