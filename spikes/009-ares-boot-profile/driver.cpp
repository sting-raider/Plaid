/* SPDX-License-Identifier: ISC
 * Original explicit boot-profile observer; no firmware is compiled into it.
 */
#define PLAID_PHYSICAL_FETCH 1
#define PLAID_ROM_FETCH_SOURCE 1
#define PLAID_PIF_BOOT 1
#define PLAID_BOOT_PROFILE 1
#include "../006-ares-rom-source/driver.cpp"

static void boot_profile_header(FILE* trace, const char* romHash, u32 budget,
    u32 mappedSize, const char* firmwareHash) {
  std::fprintf(trace, "{\"record\":\"header\",\"format\":\"plaid-ares-fetch-research-v4\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"initial_state\":\"cpu_power_pif_entry\",\"mapped_cartridge_size\":%u,\"source_policy\":\"delegated_rom_halves_before_prologue\",\"boot_inputs\":{\"firmware_sha256\":\"%s\",\"firmware_size\":1984,\"region\":\"ntsc\",\"cic\":\"CIC-NUS-6102\",\"rdram_size\":8388608,\"deterministic_entropy\":true,\"pif_processor\":\"reference_hle\",\"pif_checksum_enforced\":true}}\n",
    romHash, budget, mappedSize, firmwareHash);
}

#include "../004-ares-fetch/driver.cpp"
int main(int argc, char** argv) { return fetch_observer_main(argc, argv); }
