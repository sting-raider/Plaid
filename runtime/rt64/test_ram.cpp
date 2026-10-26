#include "ram.h"
#include <cstdio>
#include <vector>

int main() {
    constexpr uint32_t size = 0x800000;
    std::vector<uint8_t> ram(size), seen(size), rdram(size), expectedSeen, expectedRam, dirty(size / 4096);
    uint32_t random = 1;
    for (uint32_t i = 0; i < size; i++) {
        random = random * 1664525u + 1013904223u;
        ram[i] = seen[i] = uint8_t(random >> 24);
        rdram[i] = uint8_t(random >> 16); // Unobserved renderer data must survive unchanged guest words.
    }
    const uint32_t offsets[] = {0, 3, 60, 63, 64, 4095, 4096, 64 * 4096 - 1, 64 * 4096, size - 1};
    for (uint32_t offset : offsets) ram[offset] ^= 0xff;
    for (unsigned test = 0; test < 5; test++) {
        for (uint32_t p = 0; p < dirty.size(); p++)
            dirty[p] = test == 0 ? 0 : test == 1 ? uint8_t(p % 64 == 0) :
                test == 2 ? uint8_t(p % 64 == 63 ? 0x80 : 0) : 1;
        const uint8_t *pages = test == 4 ? nullptr : dirty.data();
        expectedSeen = seen; expectedRam = rdram;
        for (uint32_t p = 0; p < size; p += 4) {
            if (pages && !pages[p / 4096]) continue;
            if (!std::memcmp(expectedSeen.data() + p, ram.data() + p, 4)) continue;
            std::memcpy(expectedSeen.data() + p, ram.data() + p, 4);
            for (uint32_t i = 0; i < 4; i++) expectedRam[p + i] = ram[p + 3 - i];
        }
        sync_ram_words(rdram.data(), seen.data(), ram.data(), pages);
        if (seen != expectedSeen || rdram != expectedRam) {
            std::fprintf(stderr, "RAM sync differs from word-wise reference, case %u\n", test);
            return 1;
        }
        // Restore changed guest bytes to exercise both directions on the next pass.
        for (uint32_t offset : offsets) ram[offset] ^= 0xff;
    }
    return 0;
}
