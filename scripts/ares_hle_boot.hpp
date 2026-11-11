// SPDX-License-Identifier: ISC
// Firmware-free replacement for the PIF ROM's IPL1/IPL2 phase in the pinned-ares
// analysis oracle. Nintendo's PIF boot ROM is copyrighted console firmware and
// is not distributed; instead the machine is put in the state that firmware
// leaves it at the first IPL3 instruction (ADR-0316). The state table is
// measured, per CIC, by spikes/099-pif-hle-boot/gen_tables.py. It is only
// state: the IPL2 code the real boot copies into RSP IMEM is not reproduced.
#pragma once
#include <cstdlib>
#include <cstring>
#include <vector>
#include "ares_hle_boot_tables.hpp"

template<typename T> static void plaidHleApply(T& object, unsigned component, const PlaidHleCic& cic,
                                               const unsigned char* rom) {
  serializer writer;
  writer(object);
  std::vector<unsigned char> bytes(writer.data(), writer.data() + writer.size());
  for(std::size_t i = 0; i < cic.count; i++) {
    auto& run = cic.runs[i];
    if(run.component != component) continue;
    if(run.offset + (std::size_t)run.length > bytes.size()) std::abort();
    std::memcpy(bytes.data() + run.offset, run.bytes, run.length);
  }
  // IPL2 DMAs the cartridge's 4 KiB IPL3 into DMEM (header excluded) before jumping to it.
  if(component == 9) std::memcpy(bytes.data() + 8 + 0x40, rom + 0x40, 0x1000 - 0x40);
  serializer reader(bytes.data(), (u32)bytes.size());
  reader(object);
}

// Returns the number of CPU instructions the skipped firmware would have executed
// (and the VI frames it spans in `vis`), or ~0 when no state was measured for this CIC.
static unsigned long long plaidHleBoot(const unsigned char* rom, std::size_t size, const char* cicName, u32& vis) {
  if(size < 0x1000) return ~0ull;
  for(auto& cic : plaidHleCics) {
    if(std::strcmp(cic.name, cicName)) continue;
    // Order matters only for components whose restore reads another's state: none do.
    plaidHleApply(cpu, 0, cic, rom);   plaidHleApply(mi, 1, cic, rom);  plaidHleApply(vi, 2, cic, rom);
    plaidHleApply(ai, 3, cic, rom);    plaidHleApply(pi, 4, cic, rom);  plaidHleApply(pif, 5, cic, rom);
    plaidHleApply(ares::Nintendo64::cic, 6, cic, rom);                   plaidHleApply(ri, 7, cic, rom);
    plaidHleApply(si, 8, cic, rom);    plaidHleApply(rsp, 9, cic, rom); plaidHleApply(rdp, 10, cic, rom);
    plaidHleApply(ares::Nintendo64::queue, 11, cic, rom);
    vis = cic.vis;
    return cic.steps;
  }
  return ~0ull;
}
