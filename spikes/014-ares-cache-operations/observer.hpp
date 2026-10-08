/* SPDX-License-Identifier: ISC
 * Original completed cache-operation sensor; pure existing-field snapshots.
 */
struct CacheOperation {
  u64 pc, virtualAddress, fillCount;
  u32 operation, physical, beforeTag, afterTag, beforeWords[8], afterWords[8];
};
static std::vector<CacheOperation> cacheOperations;

static void cache_operation_observer(u64 pc,u32 operation,u64 virtualAddress,u32 physical,
    u32 beforeTag,u32 afterTag,const u32* beforeWords,const u32* afterWords) {
  CacheOperation event{pc,virtualAddress,cacheFills.size(),operation,physical,beforeTag,afterTag,{},{}};
  for(u32 i=0;i<8;i++) { event.beforeWords[i] = beforeWords[i]; event.afterWords[i] = afterWords[i]; }
  cacheOperations.push_back(event);
  #if defined(PLAID_ORDERED_HISTORY_CONTEXT)
  history_event("cache_operation",cacheOperations.size());
  #endif
}

static void print_cache_operations() {
  std::printf(",\"cache_operations\":[");
  for(size_t i=0;i<cacheOperations.size();i++) {
    const auto& e = cacheOperations[i];
    std::printf("%s{\"pc\":%llu,\"operation\":%u,\"virtual\":%llu,\"physical\":%u,\"slot\":%u,\"fill_count\":%llu,\"before_tag\":%u,\"after_tag\":%u,\"before_words\":[",
      i ? "," : "",(unsigned long long)e.pc,e.operation,(unsigned long long)e.virtualAddress,e.physical,
      (u32)(e.virtualAddress >> 5 & 0x1ff),(unsigned long long)e.fillCount,e.beforeTag,e.afterTag);
    for(u32 lane=0;lane<8;lane++) std::printf("%s%u",lane ? "," : "",e.beforeWords[lane]);
    std::printf("],\"after_words\":[");
    for(u32 lane=0;lane<8;lane++) std::printf("%s%u",lane ? "," : "",e.afterWords[lane]);
    std::printf("]}");
  }
  std::printf("]");
}
