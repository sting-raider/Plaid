/* SPDX-License-Identifier: ISC
 * Original broad cache-context observer. No extra guest bus/translation reads.
 */
#define PLAID_PHYSICAL_FETCH 1
#define PLAID_ROM_FETCH_SOURCE 1
#define PLAID_PIF_BOOT 1
#define PLAID_BOOT_PROFILE 1
#define PLAID_CACHE_FETCH 1
#include "../006-ares-rom-source/driver.cpp"
#include <cstdlib>
#include <nall/hash/sha256.hpp>

static void cache_fetch_fields(FILE* trace,u64 pc,u32 physical,bool cached,u32 word) {
  if(!cached) return;
  const auto& line = cpu.icache.line(pc);
  if(!line.hit(physical) || line.index != (physical & 0xfe0) || line.words[physical >> 2 & 7] != word)
    std::abort();
  std::fprintf(trace,",\"cache_line\":{\"slot\":%u,\"tag_key\":%u,\"index\":%u,\"words\":[",
    (u32)(pc >> 5 & 0x1ff),line.tagKey,(u32)line.index);
  for(u32 i=0;i<8;i++) std::fprintf(trace,"%s%u",i ? "," : "",line.words[i]);
  std::fprintf(trace,"]}");
}

static void cache_checkpoint_fields(FILE* state) {
  std::vector<u8> bytes;
  auto append = [&](u32 value,u32 width) {
    for(u32 i=width;i>0;i--) bytes.push_back(value >> (8*(i-1)));
  };
  for(const auto& line : cpu.icache.lines) {
    append(line.tagKey,4); append(line.index,2);
    for(u32 word : line.words) append(word,4);
  }
  auto hash = nall::Hash::SHA256(std::span<const u8>{bytes.data(),bytes.size()}).digest();
  std::fprintf(state,",\"icache_sha256\":\"%s\"",hash.data());
}

static void boot_profile_header(FILE* trace,const char* romHash,u32 budget,
    u32 mappedSize,const char* firmwareHash) {
  std::fprintf(trace,"{\"record\":\"header\",\"format\":\"plaid-ares-fetch-research-v5\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"initial_state\":\"cpu_power_pif_entry\",\"mapped_cartridge_size\":%u,\"source_policy\":\"delegated_rom_halves_before_prologue\",\"boot_inputs\":{\"firmware_sha256\":\"%s\",\"firmware_size\":1984,\"region\":\"ntsc\",\"cic\":\"CIC-NUS-6102\",\"rdram_size\":8388608,\"deterministic_entropy\":true,\"pif_processor\":\"reference_hle\",\"pif_checksum_enforced\":true},\"cache_policy\":\"selected_icache_line_at_prologue\"}\n",
    romHash,budget,mappedSize,firmwareHash);
}

#include "../004-ares-fetch/driver.cpp"
int main(int argc,char** argv) { return fetch_observer_main(argc,argv); }
