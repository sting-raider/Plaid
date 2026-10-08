/* SPDX-License-Identifier: ISC
 * Original sensor for completed identity-mapped RAM burst reads and stores.
 */
struct RdramBurst {
  bool write;
  u32 address, bytes, device, words[8];
};
static std::vector<RdramBurst> rdramBursts;

static void rdram_burst_observer(bool write,u32 address,u32 bytes,u32 device,const u32* words) {
  if((bytes != ICache && bytes != DCache) || (address & (bytes-1))) std::abort();
  RdramBurst event{write,address,bytes,device,{}};
  for(u32 i=0;i<bytes/4;i++) event.words[i] = words[i];
  rdramBursts.push_back(event);
}

static void print_rdram_bursts() {
  std::printf(",\"rdram_bursts\":[");
  for(size_t i=0;i<rdramBursts.size();i++) {
    const auto& e = rdramBursts[i];
    std::printf("%s{\"write\":%s,\"address\":%u,\"bytes\":%u,\"icache_requestor\":%s,\"words\":[",
      i ? "," : "",e.write ? "true" : "false",e.address,e.bytes,
      e.device == (u32)RBusDevice::VR4300_ICACHE ? "true" : "false");
    for(u32 lane=0;lane<e.bytes/4;lane++) std::printf("%s%u",lane ? "," : "",e.words[lane]);
    std::printf("]}");
  }
  std::printf("]");
}
