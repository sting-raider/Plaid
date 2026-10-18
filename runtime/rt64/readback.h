// Completed RT64 RAM transfers, including transfers whose values did not change.
#ifndef PLAID_RT64_READBACK_H
#define PLAID_RT64_READBACK_H
#include "../gfx.h"
#include <cstring>
#include <utility>
#include <vector>

class Readback {
    std::vector<std::pair<uint32_t, uint32_t>> spans;
public:
    void clear() { spans.clear(); }
    void record(uint32_t physical, uint32_t size) { spans.emplace_back(physical, size); }
    int finish(const std::vector<uint8_t> &rdram, std::vector<uint8_t> &seen,
               plaid_gfx_writeback writeback, void *context) {
        std::vector<uint8_t> bytes;
        if (rdram.size() % 4 || seen.size() != rdram.size()) return 1;
        for (const auto &span : spans) {
            const uint32_t p = span.first, n = span.second;
            if (p > rdram.size() || n > rdram.size() - p || !writeback) return 1;
            if (!n) continue;
            bytes.resize(n);
            for (uint32_t i = 0; i < n; i++) bytes[i] = rdram[(p + i) ^ 3u];
            if (writeback(context, p, n, bytes.data())) return 1;
            if (n) std::memcpy(seen.data() + p, bytes.data(), n);
        }
        return 0;
    }
};
#endif
