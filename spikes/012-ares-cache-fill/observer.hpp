/* SPDX-License-Identifier: ISC
 * Original completed-fill sensor; all values come from the existing bus result.
 */
struct CacheFill {
  u32 slot, physical, index, words[8];
};
static std::vector<CacheFill> cacheFills;
static u64 lastCacheFill[512]{};

static void cache_fill_observer(u32 slot,u32 physical,u32 index,const u32* words) {
  if(slot >= 512 || index != (slot << 5 & 0xfe0) || index != (physical & 0xfe0)) std::abort();
  CacheFill fill{slot,physical,index,{}};
  for(u32 i=0;i<8;i++) fill.words[i] = words[i];
  cacheFills.push_back(fill);
  lastCacheFill[slot] = cacheFills.size();
  #if defined(PLAID_ORDERED_HISTORY_CONTEXT)
  history_event("fill",cacheFills.size());
  #endif
}

static u64 cache_fill_for_fetch(u32 slot,u32 physical,u32 index,const u32* words) {
  u64 id = lastCacheFill[slot];
  if(!id) std::abort();
  const auto& fill = cacheFills[id-1];
  if((fill.physical & ~0xfff) != (physical & ~0xfff) || fill.index != index) std::abort();
  for(u32 i=0;i<8;i++) if(fill.words[i] != words[i]) std::abort();
  return id;
}

static void print_cache_fills() {
  std::printf(",\"fills\":[");
  for(size_t i=0;i<cacheFills.size();i++) {
    const auto& fill = cacheFills[i];
    std::printf("%s{\"id\":%llu,\"slot\":%u,\"physical\":%u,\"burst_address\":%u,\"words\":[",
      i ? "," : "",(unsigned long long)i+1,fill.slot,fill.physical,(fill.physical & ~0xfff) | fill.index);
    for(u32 lane=0;lane<8;lane++) std::printf("%s%u",lane ? "," : "",fill.words[lane]);
    std::printf("]}");
  }
  std::printf("]");
}
