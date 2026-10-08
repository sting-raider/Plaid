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
  const char* name;
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
    rsp.imem.fill(0x55667788);
    for(auto& r : rsp.ipu.r) r.u32 = 0;
    for(u32 r = 0; r < 32; r++) {
      for(u32 b = 0; b < 16; b++) rsp.vpu.r[r].byte(b) = u8(0x80u + ((r * 17u + b) & 0x7fu));
    }
  };

  std::vector<ProbeResult> results;
  auto probe = [&](const char* name, auto fn) {
    resetMem();
    auto imemBefore = copy4k(rsp.imem.data);
    auto dmemBefore = copy4k(rsp.dmem.data);
    fn();
    if(std::memcmp(imemBefore.data(), rsp.imem.data, 4096)) {
      std::fprintf(stderr, "IMEM mutated by %s\n", name);
      std::abort();
    }
    u32 changed = 0;
    for(u32 i = 0; i < 4096; i++) changed += dmemBefore[i] != rsp.dmem.data[i];
    if(!changed) {
      std::fprintf(stderr, "DMEM unexpectedly unchanged by %s\n", name);
      std::abort();
    }
    results.push_back({name, changed, digest(rsp.dmem.data, 4096)});
  };

  // Scalar handlers. RSP SH/SW are deliberately unaligned bytewise stores.
  probe("SB@0x1000", [&] {
    rsp.ipu.r[1].u32 = 0x1000; rsp.ipu.r[2].u32 = 0xa1b2c3d4;
    rsp.SB(rsp.ipu.r[2], rsp.ipu.r[1], 0);
    if(rsp.dmem.read<Byte>(0x000) != 0xd4) std::abort();
  });
  probe("SH@0x0fff", [&] {
    rsp.ipu.r[1].u32 = 0x0fff; rsp.ipu.r[2].u32 = 0xa1b2c3d4;
    rsp.SH(rsp.ipu.r[2], rsp.ipu.r[1], 0);
    if(rsp.dmem.read<Byte>(0xfff) != 0xc3 || rsp.dmem.read<Byte>(0x000) != 0xd4) std::abort();
  });
  probe("SW@0x0ffe", [&] {
    rsp.ipu.r[1].u32 = 0x0ffe; rsp.ipu.r[2].u32 = 0xa1b2c3d4;
    rsp.SW(rsp.ipu.r[2], rsp.ipu.r[1], 0);
    if(rsp.dmem.read<Byte>(0xffe) != 0xa1 || rsp.dmem.read<Byte>(0xfff) != 0xb2 ||
       rsp.dmem.read<Byte>(0x000) != 0xc3 || rsp.dmem.read<Byte>(0x001) != 0xd4) std::abort();
  });

  // Every architectural RSP vector-store family in the pinned interpreter.
  // Use a boundary address that forces the multi-byte forms to confront 4 KiB wrap.
  probe("SBV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SBV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SDV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SDV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SFV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SFV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SHV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SHV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SLV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SLV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SPV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SPV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SQV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SQV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SRV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SRV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SSV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SSV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("STV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.STV<0>(0, rsp.ipu.r[1], 0); });
  probe("SUV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SUV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });
  probe("SWV", [&] { rsp.ipu.r[1].u32 = 0x0fff; rsp.SWV<0>(rsp.vpu.r[2], rsp.ipu.r[1], 0); });

  // Execute decoded scalar stores from IMEM. If the RSP's data address space
  // aliases IMEM, these stores overwrite their own resident program.
  auto runProgram = [&](const char* name, u32 base, u32 storeOpcode, auto checkDmem) {
    resetMem();
    rsp.imem.fill(0);
    rsp.imem.write<Word>(0x00, 0x34080000u | (base & 0xffff));       // ORI t0,r0,base
    rsp.imem.write<Word>(0x04, 0x3c09a1b2);                         // LUI t1,0xa1b2
    rsp.imem.write<Word>(0x08, 0x3529c3d4);                         // ORI t1,t1,0xc3d4
    rsp.imem.write<Word>(0x0c, storeOpcode | (8u << 21) | (9u << 16));
    rsp.imem.write<Word>(0x10, 0x0000000d);                         // BREAK
    auto imemBefore = copy4k(rsp.imem.data);
    auto dmemBefore = copy4k(rsp.dmem.data);
    rsp.pipeline = {};
    rsp.branch.setPc(0);
    rsp.ipu.pc = 0;
    rsp.status.halted = 0;
    for(u32 guard = 0; guard < 16 && !rsp.status.halted; guard++) rsp.instruction();
    if(!rsp.status.halted) std::abort();
    if(std::memcmp(imemBefore.data(), rsp.imem.data, 4096)) {
      std::fprintf(stderr, "IMEM mutated by executed %s\n", name);
      std::abort();
    }
    checkDmem();
    u32 changed = 0;
    for(u32 i = 0; i < 4096; i++) changed += dmemBefore[i] != rsp.dmem.data[i];
    if(!changed) std::abort();
    results.push_back({name, changed, digest(rsp.dmem.data, 4096)});
  };

  runProgram("decoded_SH@0x0fff", 0x0fff, 0xa4000000, [&] {
    if(rsp.dmem.read<Byte>(0xfff) != 0xc3 || rsp.dmem.read<Byte>(0x000) != 0xd4) std::abort();
  });
  runProgram("decoded_SW@0x1000", 0x1000, 0xac000000, [&] {
    if(rsp.dmem.read<Word>(0x000) != 0xa1b2c3d4) std::abort();
  });

  string finalImem = digest(rsp.imem.data, 4096);
  string finalDmem = digest(rsp.dmem.data, 4096);
  std::printf("{\"probes\":[");
  for(size_t i = 0; i < results.size(); i++) {
    const auto& r = results[i];
    std::printf("%s{\"name\":\"%s\",\"changed_dmem\":%u,\"dmem_sha256\":\"%s\"}",
      i ? "," : "", r.name, r.changedDmem, r.dmemHash.data());
  }
  std::printf("],\"probe_count\":%zu,\"imem_sha256\":\"%s\",\"dmem_sha256\":\"%s\"}\n",
    results.size(), finalImem.data(), finalDmem.data());

  ares::Nintendo64::system.unload();
  return results.size() == 17 ? 0 : 70;
}
