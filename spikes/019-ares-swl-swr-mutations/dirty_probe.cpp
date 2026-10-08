#include <cstdint>
#include <cstdio>
#include <initializer_list>

// Minimal language-level reproduction of the relevant pinned ares
// DataCache::Line::write indexing and dirty-mask expression.
struct Line {
  std::uint16_t dirty = 0;
  union {
    std::uint8_t bytes[16];
    std::uint16_t halfs[8];
    std::uint32_t words[4];
  };

  template<unsigned Size>
  void write(std::uint32_t paddr, std::uint64_t data) {
    if constexpr(Size == 1) bytes[(paddr >> 0 & 15) ^ 3] = data;
    if constexpr(Size == 2) halfs[(paddr >> 1 & 7) ^ 1] = data;
    if constexpr(Size == 4) words[(paddr >> 2 & 3) ^ 0] = data;
    dirty |= ((1u << Size) - 1u) << (paddr & 0xF);
  }
};

int main() {
  for (unsigned base : {0u, 4u, 8u, 12u}) {
    Line half{};
    half.write<2>(base + 1, 0x3344);
    Line word{};
    word.write<4>(base + 3, 0x11223344);
    std::printf(
        "base=%u half_dirty=%04x word_dirty=%04x\n",
        base,
        half.dirty,
        word.dirty);
  }
}
