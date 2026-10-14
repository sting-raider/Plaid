/* SPDX-License-Identifier: ISC
 * Original PI copy/storage/CPU component fixture; host mapping controls are opaque.
 */
#ifndef PLAID_PI_STORAGE_SENSOR
#define PLAID_PI_STORAGE_SENSOR 1
#endif
#define PLAID_ROM_HALF_ACCESS 1
#define PLAID_ROM_FETCH_SOURCE 1
#include "../006-ares-rom-source/driver.cpp"
#include <cassert>
#include <nall/hash/sha256.hpp>
#if defined(PLAID_PI_DMEM_CUT)
#include "../042-ares-rsp-dmem-history/observer.hpp"
#endif
namespace Storage = ares::Nintendo64::Memory;
static std::vector<string> events;
static u32 phase;
#if defined(PLAID_PI_RSP_SCALAR_STORES)
static u64 activeRspContext=0,activeStoreScope=0;
static u32 activeStoreKind=0;
#endif
#if defined(PLAID_PI_RSP_OPERANDS)
static constexpr u32 piProgramWord=0x34100007; // ORI s0,zero,7.
static constexpr u32 piSecondWord=0x02108821; // ADDU s1,s0,s0.
#else
static constexpr u32 piProgramWord=0x24100007;
static constexpr u32 piSecondWord=0;
#endif

static void add(const string& fields) {
  events.push_back({"{\"ordinal\":",events.size()+1,",\"phase\":",phase,",",fields,"}"});
}
#if PLAID_PI_STORAGE_SENSOR
static void storage_effect(const void* object,u32 kind,u32 address,u32 bytes,u64 value) {
#if defined(PLAID_PI_IMEM_CUT)
  if(object == static_cast<Storage::Writable*>(&rsp.imem)) {
    add({"\"record\":\"imem_storage_effect\",\"kind\":",kind,",\"offset\":",address,
      ",\"bytes\":",bytes,",\"value\":",value});return;
  }
#endif
  if(object != static_cast<Storage::Writable*>(&rdram.ram)) return;
  add({"\"record\":\"storage_effect\",\"kind\":",kind,",\"address\":",address,
    ",\"bytes\":",bytes,",\"value\":",value});
}
static void pi_effect(u32 event,u32 dram,u32 pbus,u32 length,u32 lane,u32 value) {
  add({"\"record\":\"pi_dma\",\"event\":",event,",\"dram\":",dram,
    ",\"pbus\":",pbus,",\"length\":",length,",\"lane\":",lane,",\"value\":",value});
}
static void scalar_effect(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  add({"\"record\":\"scalar\",\"write\":",write ? "true" : "false",
    ",\"address\":",address,",\"bytes\":",bytes,",\"device\":",device,",\"value\":",value});
}
#if defined(PLAID_PI_SP_EGRESS)
static u64 sp_egress_read(u32 dram,u32 bank,u32 offset,u32 bytes,u64 value) {
  add({"\"record\":\"sp_dma_egress_read\",\"dram\":",dram,",\"bank\":",bank,
    ",\"offset\":",offset,",\"bytes\":",bytes,",\"value\":",value});
  return events.size();
}
static void sp_egress_store(u64 read) {
  u64 writer=events.size();
  add({"\"record\":\"sp_dma_egress_store\",\"read_ordinal\":",read,",\"write_ordinal\":",writer});
}
#endif
static void rom_half(u32 offset,u16 value) {
  add({"\"record\":\"rom_half\",\"offset\":",offset,",\"value\":",value});
}
#if defined(PLAID_PI_SP_CONSUMPTION)
#if defined(PLAID_PI_DMEM_CUT)
static void lower_dmem_effect(u32 offset,u32 bytes,u64 value) {
  string row{"\"record\":\"rsp_dmem_effect\",\"offset\":",offset,",\"bytes\":",bytes,",\"value\":",value};
#if defined(PLAID_PI_RSP_SCALAR_STORES)
  row.append(",\"store_scope\":",activeStoreScope);
#endif
  add(row);
}
#if defined(PLAID_PI_RSP_CONSUMPTION)
static u64 performed_rsp_read(u32 address,u32 offset,u32 word) {
  add({"\"record\":\"rsp_imem_read\",\"address\":",address,",\"offset\":",offset,",\"word\":",word});
  return events.size();
}
static void performed_rsp_instruction(bool begin,u32 pc,u64 read,u32 word,u32 next,bool halted) {
  string row{"\"record\":\"rsp_instruction\",\"begin\":",begin ? "true" : "false",",\"rsp_pc\":",pc,
    ",\"read_ordinal\":",read,",\"word\":",word,",\"next_pc\":",next,",\"halted\":",halted ? "true" : "false"};
#if defined(PLAID_PI_RSP_OPERANDS)
  row.append(",\"registers\":[");
  for(u32 n=0;n<32;n++) row.append(n ? "," : "",rsp.ipu.r[n].u32);
  row.append("]");
#endif
  add(row);
#if defined(PLAID_PI_RSP_SCALAR_STORES)
  if(activeStoreScope) std::abort();
  if(begin) { if(activeRspContext) std::abort();activeRspContext=events.size(); }
  else { if(!activeRspContext) std::abort();activeRspContext=0; }
#endif
}
#if defined(PLAID_PI_RSP_SCALAR_STORES)
static void scalar_store_scope(bool begin,u32 kind) {
  if(!activeRspContext) return;
  if(begin) {if(activeStoreScope) std::abort();activeStoreScope=events.size()+1;activeStoreKind=kind;}
  else if(!activeStoreScope || kind!=activeStoreKind) std::abort();
  add({"\"record\":\"rsp_scalar_store_scope\",\"begin\":",begin ? "true" : "false",",\"kind\":",kind,
    ",\"instruction_context\":",activeRspContext,",\"store_scope\":",activeStoreScope});
  if(!begin) activeStoreScope=0;
}
#endif
#endif
#endif
static void sp_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool cpuOrigin) {
  add({"\"record\":\"sp_word\",\"write\":",write ? "true" : "false",",\"address\":",address,
    ",\"bank\":",bank,",\"offset\":",offset,",\"value\":",value,",\"cpu\":",cpuOrigin ? "true" : "false"});
}
static void sp_store(u32 dram,u32 bank,u32 offset,u32 bytes,u64 value) {
  add({"\"record\":\"sp_dma_store\",\"dram\":",dram,",\"bank\":",bank,
    ",\"offset\":",offset,",\"bytes\":",bytes,",\"value\":",value});
}
#endif
#endif
#if defined(PLAID_PI_RSP_OPERANDS)
static u64 operandEpoch=0;
static void operand_root(bool enabled) {
#if PLAID_PI_STORAGE_SENSOR
  if(!enabled) return;
  string row{"\"record\":\"rsp_operand_root\",\"epoch\":",++operandEpoch,",\"rsp_pc\":",rsp.ipu.pc,",\"registers\":["};
  for(u32 n=0;n<32;n++) row.append(n ? "," : "",rsp.ipu.r[n].u32);
  add(row.append("]"));
#else
  (void)enabled;
#endif
}
#endif
int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  Headless frontend; platform=&frontend;
  std::vector<u8> rom(16384);
  rom[0]=0x80;rom[1]=0x37;rom[2]=0x12;rom[3]=0x40;
  for(u32 n=0;n<4;n++) {
    rom[0x1000+n]=piProgramWord>>(24-n*8);
    rom[0x1004+n]=piSecondWord>>(24-n*8);
  }
  frontend.cartPak->setAttribute("title","Plaid original PI storage fixture");
  frontend.cartPak->setAttribute("region","NTSC");frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",std::span<const u8>{rom.data(),rom.size()});
  Node::System root; if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled || rdram.ram.size!=8388608) return 4;
  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();
  std::memset(rdram.ram.data,0xcc,rdram.ram.size);
  ri.io.currentLoaded=1;ri.io.select=0x14;
  cpu.scc.status.errorLevel=cpu.scc.status.exceptionLevel=cpu.scc.status.interruptEnable=0;
  cpu.context.setMode();
  RomObserver observer;
#if PLAID_PI_STORAGE_SENSOR
  if(traced) {
    pi.detach(cartridge.romDevice);pi.attach(observer,0);
    Storage::plaidMemoryMutationObserver=storage_effect;
    plaidPiDmaObserver=pi_effect;plaidRdramScalarObserver=scalar_effect;plaidRomHalfObserver=rom_half;
#if defined(PLAID_PI_SP_EGRESS)
    plaidSpDmaEgressReadObserver=sp_egress_read;plaidSpDmaEgressStoreObserver=sp_egress_store;
#endif
#if defined(PLAID_PI_SP_CONSUMPTION)
    plaidSpWordObserver=sp_word;plaidSpDmaStoreObserver=sp_store;
#if defined(PLAID_PI_DMEM_CUT)
    plaidRspDmemObserver=lower_dmem_effect;
#if defined(PLAID_PI_RSP_CONSUMPTION)
    plaidRspImemReadObserver=performed_rsp_read;plaidRspInstructionFetchObserver=performed_rsp_instruction;
#if defined(PLAID_PI_RSP_SCALAR_STORES)
    plaidRspScalarStoreObserver=scalar_store_scope;
#endif
#endif
#endif
#endif
  }
#else
  (void)traced;
#endif
  std::vector<string> states;
  auto snapshot=[&](const char* point) {
    auto ram=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
    auto extra=nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
    string row={"{\"phase\":",phase,",\"point\":\"",point,"\",\"ram\":\"",ram,"\",\"hidden\":\"",extra,
      "\",\"map_identity\":",(u32)rdram.mapIdentity,",\"ri_error\":",(u32)ri.io.error,
      ",\"busy\":",(u32)pi.io.dmaBusy,",\"interrupt\":",(u32)pi.io.interrupt,
      ",\"dram\":",(u32)pi.io.dramAddress,",\"pbus\":",(u32)pi.io.pbusAddress,
      ",\"length\":",(u32)pi.io.writeLength,",\"pc\":",(u64)cpu.ipu.pc,
      ",\"count\":",cpu.effectiveCount(),",\"exception\":",(u32)cpu.scc.cause.exceptionCode,
      ",\"epc\":",(u64)cpu.scc.epc,",\"regs\":["};
    for(u32 n=0;n<32;n++) row.append(n ? "," : "",cpu.ipu.r[n].u64);
    row.append("]");
#if defined(PLAID_PI_SP_CONSUMPTION)
    row.append(",\"imem\":\"",nall::Hash::SHA256(std::span<const u8>{rsp.imem.data,rsp.imem.size}).digest(),
      "\",\"dmem\":\"",nall::Hash::SHA256(std::span<const u8>{rsp.dmem.data,rsp.dmem.size}).digest(),"\"");
#endif
#if defined(PLAID_PI_DMEM_CUT)
    row.append(",\"machine\":\"",rsp_machine_digest(),"\"");
#endif
    row.append("}");states.push_back(row);
  };
  for(phase=0;phase<3;phase++) {
    ares::Nintendo64::queue.reset();pi.ioWrite(16,3);ri.io.error=0;
    for(auto& chip:rdram.chips) chip={};
    rdram.chips[0].present=1;rdram.chips[0].enable=1;rdram.chips[0].deviceID=2;
    if(phase==1) {rdram.chips[1].present=1;rdram.chips[1].enable=1;rdram.chips[1].deviceID=0;}
    rdram.mapIdentity=phase==0;
    snapshot("before");
    pi.ioWrite(0,0x1000);pi.ioWrite(4,0x10001000);pi.ioWrite(12,7);
    snapshot("copied");
    if(phase<2) {
      // Explicit host mapping control; no guest mapping-operation provenance claimed.
      rdram.mapIdentity=1;cpu.ipu.r[16].u64=0;
      u32 physical=phase==0 ? 0x1000 : 0x201000;
      assert(static_cast<Storage::Writable&>(rdram.ram).read<Word>(physical)==piProgramWord);
      cpu.pipeline.setPc(0xffffffffa0000000ull|physical);
      cpu.instruction();
      assert(cpu.ipu.r[16].u64==7 && cpu.scc.cause.exceptionCode==0);
      snapshot("executed");
#if defined(PLAID_PI_SP_CONSUMPTION)
      rsp.writeWord(0x04040000,0x1000,cpu);rsp.writeWord(0x04040004,physical,cpu);
      rsp.writeWord(0x04040008,0,cpu);
      assert(rsp.dma.busy.read && rsp.dma.current.pbusRegion);
      rsp.dmaTransferStep();
      assert(!rsp.dma.busy.any() && rsp.imem.read<Word>(0)==piProgramWord);
      snapshot("sp_installed");
      cpu.ipu.r[16].u64=0;cpu.pipeline.setPc(0xffffffffa4001000ull);cpu.instruction();
      assert(cpu.ipu.r[16].u64==7 && cpu.scc.cause.exceptionCode==0);
      snapshot("sp_executed");
#if defined(PLAID_PI_DMEM_CUT)
      rsp.writeWord(0x04040000,0,cpu);rsp.writeWord(0x04040004,physical,cpu);
      rsp.writeWord(0x04040008,0,cpu);rsp.dmaTransferStep();
      assert(!rsp.dma.busy.any() && rsp.dmem.read<Word>(0)==piProgramWord);
      snapshot("dmem_installed");
      cpu.ipu.r[16].u64=0;cpu.pipeline.setPc(0xffffffffa4000000ull);cpu.instruction();
      assert(cpu.ipu.r[16].u64==7);snapshot("dmem_executed");
      // Explicit opaque IMEM seed and RSP register controls; only the sink is claimed.
      rsp.imem.write<Word>(0x200,0xac220000);rsp.imem.write<Word>(0x204,0x0000000d);
      rsp.ipu.r[1].u32=0;rsp.ipu.r[2].u32=piProgramWord;
      rsp.pipeline={};rsp.branch.setPc(0x200);rsp.ipu.pc=0x200;rsp.status.halted=0;
#if defined(PLAID_PI_RSP_OPERANDS)
      operand_root(traced);
#endif
      for(u32 guard=0;guard<8 && !rsp.status.halted;guard++) rsp.instruction();
      assert(rsp.status.halted && rsp.dmem.read<Word>(0)==piProgramWord && rsp.imem.read<Word>(0)==piProgramWord);
      snapshot("rsp_equal_store");
#if defined(PLAID_PI_SP_EGRESS)
      rsp.writeWord(0x04040000,0,cpu);rsp.writeWord(0x04040004,0x3000,cpu);
      rsp.writeWord(0x0404000c,0,cpu);rsp.dmaTransferStep();
      assert(!rsp.dma.busy.any() && rdram.ram.ares::Nintendo64::Memory::Writable::read<Word>(0x3000)==piProgramWord);
      snapshot("rsp_dmem_exported");
      cpu.ipu.r[16].u64=0;cpu.pipeline.setPc(0xffffffffa0003000ull);cpu.instruction();
      assert(cpu.ipu.r[16].u64==7);snapshot("rsp_dmem_export_consumed");
      rsp.writeWord(0x04040000,0x1000,cpu);rsp.writeWord(0x04040004,0x3020,cpu);
      rsp.writeWord(0x0404000c,0,cpu);rsp.dmaTransferStep();
      assert(!rsp.dma.busy.any() && rdram.ram.ares::Nintendo64::Memory::Writable::read<Word>(0x3020)==piProgramWord);
      snapshot("imem_exported");
#endif
      cpu.ipu.r[16].u64=0;cpu.pipeline.setPc(0xffffffffa4000000ull);cpu.instruction();
      assert(cpu.ipu.r[16].u64==7);snapshot("dmem_consumed");
      cpu.ipu.r[16].u64=0;cpu.pipeline.setPc(0xffffffffa4001000ull);cpu.instruction();
      assert(cpu.ipu.r[16].u64==7);snapshot("imem_consumed");
#if defined(PLAID_PI_RSP_CONSUMPTION)
      // Execute the installed PI words; the explicit BREAK seed is an opaque root.
      rsp.imem.write<Word>(8,0x0000000d);rsp.ipu.r[16].u32=0;
      rsp.pipeline={};rsp.pipeline.singleIssue=true;
      rsp.branch.setPc(0);rsp.ipu.pc=0;rsp.status.halted=0;
#if defined(PLAID_PI_RSP_OPERANDS)
      operand_root(traced);
#endif
      for(u32 guard=0;guard<8 && !rsp.status.halted;guard++) rsp.instruction();
      assert(rsp.status.halted && rsp.ipu.r[16].u32==7);
      snapshot("rsp_imem_consumed");
      // The pin retains JR low PC bits while the actual Word read masks them.
      rsp.imem.write<Word>(0x300,0x00200008);rsp.imem.write<Word>(0x304,0);
      rsp.ipu.r[1].u32=3;rsp.ipu.r[16].u32=0;
      rsp.pipeline={};rsp.branch.setPc(0x300);rsp.ipu.pc=0x300;rsp.status.halted=0;
#if defined(PLAID_PI_RSP_OPERANDS)
      operand_root(traced);
#endif
      for(u32 guard=0;guard<16 && !rsp.status.halted;guard++) rsp.instruction();
      assert(rsp.status.halted && rsp.ipu.r[16].u32==7 && rsp.ipu.pc==15);
      snapshot("rsp_unaligned_consumed");
      // A paired VNOP is performed after MTC0 sets HALT in the same batch.
      rsp.imem.write<Word>(0x400,0x40822000);rsp.imem.write<Word>(0x404,0x4a000037);
      rsp.ipu.r[2].u32=2;rsp.pipeline={};rsp.branch.setPc(0x400);rsp.ipu.pc=0x400;rsp.status.halted=0;
#if defined(PLAID_PI_RSP_OPERANDS)
      operand_root(traced);
#endif
      rsp.instruction();
      assert(rsp.status.halted && rsp.ipu.pc==0x408);
      snapshot("rsp_halt_dual_consumed");
#if defined(PLAID_PI_IMEM_CUT)
      auto reinstall=[&] {
        rsp.writeWord(0x04040000,0x1000,cpu);rsp.writeWord(0x04040004,physical,cpu);
        rsp.writeWord(0x04040008,0,cpu);rsp.dmaTransferStep();
        assert(!rsp.dma.busy.any() && rsp.imem.read<Word>(0)==piProgramWord);
      };
      auto consume=[&](const char* point) {
        cpu.ipu.r[16].u64=0;cpu.pipeline.setPc(0xffffffffa4001000ull);cpu.instruction();
        assert(cpu.ipu.r[16].u64==7);
        rsp.imem.write<Word>(8,13);rsp.ipu.r[16].u32=0;
        rsp.pipeline={};rsp.pipeline.singleIssue=true;rsp.branch.setPc(0);rsp.ipu.pc=0;rsp.status.halted=0;
  #if defined(PLAID_PI_RSP_OPERANDS)
      operand_root(traced);
#endif
      for(u32 guard=0;guard<8 && !rsp.status.halted;guard++) rsp.instruction();
        assert(rsp.status.halted && rsp.ipu.r[16].u32==7);snapshot(point);
      };
      reinstall();rsp.imem.write<Word>(0,piProgramWord);snapshot("imem_equal_written");consume("imem_equal_consumed");
      reinstall();rsp.imem.fill(piProgramWord);snapshot("imem_filled");consume("imem_fill_consumed");
      reinstall();auto imemFile=vfs::memory::create(12);
      imemFile->writem(piProgramWord,4);imemFile->writem(piSecondWord,4);imemFile->writem(13,4);imemFile->seek(0);
      rsp.imem.load(imemFile);snapshot("imem_loaded");consume("imem_load_consumed");
#endif
#endif
#endif
#endif
    } else assert(ri.io.error);
  }
#if PLAID_PI_STORAGE_SENSOR
  Storage::plaidMemoryMutationObserver=nullptr;plaidPiDmaObserver=nullptr;
  plaidRdramScalarObserver=nullptr;plaidRomHalfObserver=nullptr;
#if defined(PLAID_PI_SP_CONSUMPTION)
  plaidSpWordObserver=nullptr;plaidSpDmaStoreObserver=nullptr;
#if defined(PLAID_PI_DMEM_CUT)
  plaidRspDmemObserver=nullptr;
#if defined(PLAID_PI_RSP_CONSUMPTION)
  plaidRspImemReadObserver=nullptr;plaidRspInstructionFetchObserver=nullptr;
#endif
#endif
#endif
  if(traced) {pi.detach(observer);pi.attach(cartridge.romDevice,0);}
#endif
  std::printf("{\"states\":[");
  for(size_t n=0;n<states.size();n++) std::printf("%s%s",n ? "," : "",states[n].data());
  std::printf("],\"events\":[");
  for(size_t n=0;n<events.size();n++) std::printf("%s%s",n ? "," : "",events[n].data());
  std::printf("]}\n");ares::Nintendo64::system.unload();
}
