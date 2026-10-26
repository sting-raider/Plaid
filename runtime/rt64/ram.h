// Keep RT64's word-swapped RAM mirror in sync without touching unchanged words.
#ifndef PLAID_RT64_RAM_H
#define PLAID_RT64_RAM_H
#include <cstdint>
#include <cstring>

inline void sync_ram_words(uint8_t *rdram, uint8_t *seen, const uint8_t *ram, const uint8_t *dirty_pages) {
    constexpr uint32_t ramSize = 0x800000;
    static constexpr uint8_t clean[64] = {};
    for (uint32_t group = 0; group < ramSize; group += 64 * 4096) {
        if (dirty_pages && !std::memcmp(dirty_pages + group / 4096, clean, sizeof clean)) continue;
        for (uint32_t page = group; page < group + 64 * 4096; page += 4096) {
            if (dirty_pages && !dirty_pages[page / 4096]) continue;
            for (uint32_t block = page; block < page + 4096; block += 64) {
                if (!std::memcmp(seen + block, ram + block, 64)) continue;
                for (uint32_t p = block; p < block + 64; p += 4) {
                    if (std::memcmp(seen + p, ram + p, 4)) {
                        std::memcpy(seen + p, ram + p, 4);
                        const uint32_t w = uint32_t(ram[p]) << 24 | uint32_t(ram[p + 1]) << 16 |
                            uint32_t(ram[p + 2]) << 8 | ram[p + 3];
                        std::memcpy(rdram + p, &w, 4);
                    }
                }
            }
        }
    }
}
#endif
