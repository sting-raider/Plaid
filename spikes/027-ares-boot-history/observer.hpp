/* SPDX-License-Identifier: ISC
 * Stream already-completed results and existing fields, without guest accesses.
 */
static FILE* accessBootTrace = nullptr;
static u64 accessBootOrdinal = 0, accessBootActive = 0, accessBootPending = 0;
static u64 accessBootPc = 0, accessBootVaddr = 0;
static u32 accessBootTranslated = 0, accessBootBus = 0, accessBootWord = 0;
static bool accessBootCached = false;

static void access_boot_record(const char* kind) {
  if(!accessBootTrace || ++accessBootOrdinal == 0) std::abort();
  std::fprintf(accessBootTrace,"{\"record\":\"%s\",\"ordinal\":%llu,\"context\":%llu,\"pc\":%llu",
    kind,(unsigned long long)accessBootOrdinal,(unsigned long long)accessBootActive,(unsigned long long)cpu.ipu.pc);
}
static void access_boot_words(const char* field,const u32* words,u32 count) {
  std::fprintf(accessBootTrace,",\"%s\":[",field);
  for(u32 i=0;i<count;i++) std::fprintf(accessBootTrace,"%s%u",i ? "," : "",words[i]);
  std::fprintf(accessBootTrace,"]");
}
static void access_boot_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(bytes != Byte && bytes != Half && bytes != Word && bytes != Dual) std::abort();
  access_boot_record("scalar");
  std::fprintf(accessBootTrace,",\"write\":%s,\"address\":%u,\"aligned_address\":%u,\"bytes\":%u,\"device\":%u,\"value\":%llu}\n",
    write ? "true" : "false",address,address & ~(bytes-1),bytes,device,(unsigned long long)value);
}
static void access_boot_burst(bool write,u32 address,u32 bytes,u32 device,const u32* words) {
  if((bytes != ICache && bytes != DCache) || (address & (bytes-1))) std::abort();
  access_boot_record("burst");
  std::fprintf(accessBootTrace,",\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u",
    write ? "true" : "false",address,bytes,device);
  access_boot_words("words",words,bytes/4);
  std::fprintf(accessBootTrace,"}\n");
}
static void access_boot_fill(u32 slot,u32 physical,u32 index,const u32* words) {
  access_boot_record("fill");
  std::fprintf(accessBootTrace,",\"slot\":%u,\"physical\":%u,\"index\":%u",slot,physical,index);
  access_boot_words("words",words,8);
  std::fprintf(accessBootTrace,"}\n");
}
static void access_boot_cache(u64 pc,u32 operation,u64 vaddr,u32 physical,u32 beforeTag,u32 afterTag,
                              const u32* beforeWords,const u32* afterWords) {
  if(pc != cpu.ipu.pc) std::abort();
  access_boot_record("cache_operation");
  std::fprintf(accessBootTrace,",\"operation\":%u,\"vaddr\":%llu,\"physical\":%u,\"before_tag\":%u,\"after_tag\":%u",
    operation,(unsigned long long)vaddr,physical,beforeTag,afterTag);
  access_boot_words("before_words",beforeWords,8);
  access_boot_words("after_words",afterWords,8);
  std::fprintf(accessBootTrace,"}\n");
}
static void access_boot_boundary(bool begin,u64 vaddr,u32 translated,u32 bus,bool cached,u32 value) {
  if(begin) {
    if(accessBootActive || accessBootPending) std::abort();
    accessBootActive = accessBootOrdinal + 1;
    accessBootPc = cpu.ipu.pc; accessBootVaddr = vaddr;
    accessBootTranslated = translated; accessBootBus = bus; accessBootCached = cached;
  } else {
    if(!accessBootActive || cpu.ipu.pc != accessBootPc || vaddr != accessBootVaddr ||
       translated != accessBootTranslated || bus != accessBootBus || cached != accessBootCached) std::abort();
    accessBootWord = value;
  }
  access_boot_record(begin ? "fetch_begin" : "fetch_end");
  std::fprintf(accessBootTrace,",\"vaddr\":%llu,\"translated\":%u,\"bus\":%u,\"cached\":%s,\"value\":%u}\n",
    (unsigned long long)vaddr,translated,bus,cached ? "true" : "false",value);
  if(!begin) {
    accessBootPending = accessBootActive;
    accessBootActive = 0;
  }
}
static void access_boot_fetch(u64 seq,u64 pc,u32 word,u32 physical,bool cached) {
  if(accessBootActive || !accessBootPending || pc != accessBootPc || word != accessBootWord ||
     physical != accessBootBus || cached != accessBootCached) std::abort();
  access_boot_record("fetch");
  std::fprintf(accessBootTrace,",\"fetch_context\":%llu,\"fetch_seq\":%llu,\"word\":%u,\"physical\":%u,\"cached\":%s}\n",
    (unsigned long long)accessBootPending,(unsigned long long)seq,word,physical,cached ? "true" : "false");
  accessBootPending = 0;
}
static void access_boot_start(const char* tracePath,const char* romHash,u32 budget,u32 mappedSize,const char* firmwareHash) {
  std::string filename = std::string(tracePath) + ".history.ndjson";
  accessBootTrace = std::fopen(filename.c_str(),"wb");
  if(!accessBootTrace) std::abort();
  std::fprintf(accessBootTrace,"{\"record\":\"header\",\"format\":\"plaid-ares-access-history-v0\",\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"rom_sha256\":\"%s\",\"budget\":%u,\"mapped_cartridge_size\":%u,\"firmware_sha256\":\"%s\",\"policy\":\"identity_ram_successful_access_and_fetch_boundaries\",\"lifecycle_policy\":\"single_run_no_host_restore\",\"paired_fetch_format\":\"plaid-ares-fetch-research-v5\"}\n",
    romHash,budget,mappedSize,firmwareHash);
  plaidRdramScalarObserver = access_boot_scalar;
  plaidRdramBurstObserver = access_boot_burst;
  plaidCacheFillObserver = access_boot_fill;
  plaidCacheOperationObserver = access_boot_cache;
  plaidCpuFetchObserver = access_boot_boundary;
}
static void access_boot_finish(u64 fetches) {
  if(accessBootActive || accessBootPending) std::abort();
  plaidRdramScalarObserver = nullptr; plaidRdramBurstObserver = nullptr;
  plaidCacheFillObserver = nullptr; plaidCacheOperationObserver = nullptr; plaidCpuFetchObserver = nullptr;
  std::fprintf(accessBootTrace,"{\"record\":\"end\",\"record_count\":%llu,\"fetch_count\":%llu,\"reason\":\"instruction_call_budget\"}\n",
    (unsigned long long)accessBootOrdinal,(unsigned long long)fetches);
  if(std::ferror(accessBootTrace) || std::fclose(accessBootTrace)) std::abort();
  accessBootTrace = nullptr;
}
