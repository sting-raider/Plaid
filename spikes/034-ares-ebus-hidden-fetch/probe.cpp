#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
using u8 = uint8_t;
using u16 = uint16_t;
using u32 = uint32_t;
using u64 = uint64_t;
using n1 = bool;
static constexpr u32 Byte=1, Half=2, Word=4, Dual=8, ICache=32;
#define ARCHITECTURE_SUPPORTS_SSE4_1 0
namespace memory {
template<unsigned N, class T> void writel(u8* p, T value) {
  for(unsigned i=0;i<N;i++) p[i]=(u8)(value >> (8*i));
}
}
static auto range(u32 n) { std::vector<u32> v; for(u32 i=0;i<n;i++) v.push_back(i); return v; }
#include "hidden.hpp"

static void require(bool x, const char* msg) { if(!x) { std::fprintf(stderr,"FAIL:%s\n",msg); std::exit(1);} }
int main() {
  std::array<u8, 64> bytes{};
  HiddenRAM h; h.data=bytes.data();
  std::array<u64,16> counts{};
  for(unsigned a=0;a<256;a++) for(unsigned b=0;b<256;b++) {
    bytes[0]=a; bytes[1]=b;
    auto got=h.nibble(0), want=((a&3u)<<2)|(b&3u);
    require(got==want,"nibble formula");
    counts[got]++;
  }
  for(auto c:counts) require(c==4096,"nibble distribution");

  for(unsigned upperBit=0; upperBit<2; upperBit++) for(unsigned lowBit=0; lowBit<2; lowBit++) {
    bytes.fill(0xa5);
    u32 value=(upperBit<<16)|lowBit;
    h.update<Word>(0,value);
    u32 expected=((upperBit?3u:0u)<<2)|(lowBit?3u:0u);
    require(h.nibble(0)==expected,"ordinary word update transform");
  }

  for(unsigned nib=0;nib<16;nib++) {
    bytes.fill(0xa5);
    h.ebusScatter<Word>(0,0x12345670u|nib);
    require(h.nibble(0)==nib,"ebus scatter roundtrip");
  }

  for(unsigned slot=0;slot<4;slot++) {
    bytes.fill(0);
    auto address=slot*4u;
    auto offset=address>>1;
    bytes[offset]=3; bytes[offset+1]=2;
    require(h.nibble(address)==14,"address to hidden offset");
    if(slot>0) require(h.nibble(address-4)!=14,"adjacent source separation");
  }

  std::printf("{\"exhaustive_pairs\":65536,\"outputs\":16,\"count_per_output\":4096,");
  std::printf("\"ordinary_word_outputs\":[0,3,12,15],\"ebus_word_outputs\":16,");
  std::printf("\"word_source_bytes\":2,\"source_bits_per_byte\":2}\n");
}
