/* SPDX-License-Identifier: ISC
 * Plaid research fixture: can ordinary RSP stores ever mutate IMEM?
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <array>
#include <vector>

static auto digest(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

static auto copy4k(const u8* data) -> std::array<u8, 4096> {
  std::array<u8, 4096> out{};
  std::memcpy(out.data(), data, out.size());
  return out;
}

struct ProbeResult {
  string name;
  u32 instruction;
  u32 base;
  u32 changedDmem;
  string dmemHash;
};

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP self-store IMEM fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  auto resetMem = [&] {
    rsp.dmem.fill(0x11223344);
    rsp.imem.fill(0);
    for(auto& r : rsp.ipu.r) r.u32 = 0;
    for(u32 r = 0; r < 32; r++) {
      for(u32 b = 0; b < 16; b++) rsp.vpu.r[r].byte(b) = u8(0x80u + ((r * 17u + b) & 0x7fu));
    }
  };

  std::vector<ProbeResult> results;
  auto runDecoded = [&](string name, u32 instruction, u32 base, bool scalar, auto checkDmem, bool expectMutation = true) {
    resetMem();
    rsp.ipu.r[1].u32 = base;
    if(scalar) rsp.ipu.r[2].u32 = 0xa1b2c3d4;
    rsp.imem.write<Word>(0x000, instruction);
    rsp.imem.write<Word>(0x004, 0x0000000d); // BREAK
    auto imemBefore = copy4k(rsp.imem.data);
    auto dmemBefore = copy4k(rsp.dmem.data);

    rsp.pipeline = {};
    rsp.branch.setPc(0);
    rsp.ipu.pc = 0;
    rsp.status.halted = 0;
    for(u32 guard = 0; guard < 8 && !rsp.status.halted; guard++) rsp.instruction();
    if(!rsp.status.halted) {
      std::fprintf(stderr, "RSP failed to halt after %s\n", name.data());
      std::abort();
    }
    if(std::memcmp(imemBefore.data(), rsp.imem.data, 4096)) {
      std::fprintf(stderr, "IMEM mutated by executed %s base=%08x\n", name.data(), base);
      std::abort();
    }
    checkDmem();
    u32 changed = 0;
    for(u32 i = 0; i < 4096; i++) changed += dmemBefore[i] != rsp.dmem.data[i];
    if(bool(changed) != expectMutation) {
      std::fprintf(stderr, "DMEM mutation differs from expected %u for %s base=%08x\n", expectMutation, name.data(), base);
      std::abort();
    }
    results.push_back({name, instruction, base, changed, digest(rsp.dmem.data, 4096)});
  };

  // Scalar store opcodes: base=r1, rt=r2, immediate=0. These are actual
  // decoded guest instructions, including unaligned SH/SW wrap through 0xfff.
  runDecoded("SB", 0xa0220000, 0x1000, true, [&] {
    if(rsp.dmem.read<Byte>(0x000) != 0xd4) std::abort();
  });
  runDecoded("SH", 0xa4220000, 0x0fff, true, [&] {
    if(rsp.dmem.read<Byte>(0xfff) != 0xc3 || rsp.dmem.read<Byte>(0x000) != 0xd4) std::abort();
  });
  runDecoded("SW-wrap", 0xac220000, 0x0ffe, true, [&] {
    if(rsp.dmem.read<Byte>(0xffe) != 0xa1 || rsp.dmem.read<Byte>(0xfff) != 0xb2 ||
       rsp.dmem.read<Byte>(0x000) != 0xc3 || rsp.dmem.read<Byte>(0x001) != 0xd4) std::abort();
  });
  runDecoded("SW-bit12", 0xac220000, 0x1000, true, [&] {
    if(rsp.dmem.read<Word>(0x000) != 0xa1b2c3d4) std::abort();
  });

  // SWC2 encoding from the pinned n64-systemtest assembler:
  // op=58, base=r1, vt=v2, e=0, imm7=0, with WC2 subtype in bits 15..11.
  struct VectorStore {
    const char* bit12Name;
    const char* wrapName;
    u32 subtype;
  };
  const VectorStore stores[] = {
    {"SBV@0x1000","SBV@0x0fff",0}, {"SSV@0x1000","SSV@0x0fff",1},
    {"SLV@0x1000","SLV@0x0fff",2}, {"SDV@0x1000","SDV@0x0fff",3},
    {"SQV@0x1000","SQV@0x0fff",4}, {"SRV@0x1000","SRV@0x0fff",5},
    {"SPV@0x1000","SPV@0x0fff",6}, {"SUV@0x1000","SUV@0x0fff",7},
    {"SHV@0x1000","SHV@0x0fff",8}, {"SFV@0x1000","SFV@0x0fff",9},
    {"SWV@0x1000","SWV@0x0fff",10}, {"STV@0x1000","STV@0x0fff",11},
  };
  for(const auto& store : stores) {
    u32 instruction = (58u << 26) | (1u << 21) | (2u << 16) | (store.subtype << 11);
    // 0x1000 is the adversarial would-be IMEM selector if the RSP data path
    // shared the CPU-visible 8 KiB SP memory addressing model.
    // SRV writes address & 15 bytes; at this aligned base it is a true no-op.
    // Still execute it and require both DMEM and IMEM to remain unchanged.
    runDecoded(store.bit12Name, instruction, 0x1000, false, [&] {}, store.subtype != 5);
    // 0x0fff forces multi-byte/vector forms to confront the 4 KiB wrap edge.
    runDecoded(store.wrapName, instruction, 0x0fff, false, [&] {});
  }

  // Worker closeout adds the real SRV write path with the would-be IMEM bit set.
  u32 srvInstruction = (58u << 26) | (1u << 21) | (2u << 16) | (5u << 11);
  runDecoded("SRV@0x100f", srvInstruction, 0x100f, false, [&] {});

  string finalImem = digest(rsp.imem.data, 4096);
  string finalDmem = digest(rsp.dmem.data, 4096);
  std::printf("{\"probes\":[");
  for(size_t i = 0; i < results.size(); i++) {
    const auto& r = results[i];
    std::printf("%s{\"name\":\"%s\",\"instruction\":%u,\"base\":%u,\"changed_dmem\":%u,\"dmem_sha256\":\"%s\"}",
      i ? "," : "", r.name.data(), r.instruction, r.base, r.changedDmem, r.dmemHash.data());
  }
  std::printf("],\"probe_count\":%zu,\"imem_sha256\":\"%s\",\"dmem_sha256\":\"%s\"}\n",
    results.size(), finalImem.data(), finalDmem.data());

  ares::Nintendo64::system.unload();
  return results.size() == 29 ? 0 : 70;
}
