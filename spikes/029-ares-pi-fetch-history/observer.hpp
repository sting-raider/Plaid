/* SPDX-License-Identifier: ISC
 * Original chronology observer: existing results only, no guest access/clock.
 */
static std::vector<std::string> joinedEvents;
static u32 joinedStage = 0;
static u32 joinedTransfer = 0, joinedBlock = 0;
static bool joinedEnabled = false, joinedPiActive = false;
static u64 joinedContext = 0;

template<typename... Args>
static void joined_record(const char* kind,const char* format,Args... args) {
  if(!joinedEnabled) return;
  char payload[4096], prefix[160];
  int length = std::snprintf(payload,sizeof(payload),format,args...);
  if(length < 0 || (size_t)length >= sizeof(payload)) std::abort();
  std::snprintf(prefix,sizeof(prefix),"{\"ordinal\":%llu,\"stage\":%u,\"kind\":\"%s\",",
      (unsigned long long)joinedEvents.size()+1,joinedStage,kind);
  joinedEvents.emplace_back(std::string(prefix)+payload+"}");
}
static std::string joined_words(const u32* words) {
  std::string result = "[";
  for(u32 i=0;i<8;i++) result += (i ? "," : "")+std::to_string(words[i]);
  return result+"]";
}
static void joined_pi(u32 kind,u32 dram,u32 pbus,u32 length,u32 lane,u32 value) {
  if(!joinedEnabled) return;
  if(kind == 1) { ++joinedTransfer; joinedBlock=0; joinedPiActive=true; }
  if(kind == 2) ++joinedBlock;
  joined_record("pi","\"event\":%u,\"transfer\":%u,\"block\":%u,\"dram\":%u,\"pbus\":%u,\"length\":%u,\"lane\":%u,\"value\":%u",
      kind,joinedTransfer,joinedBlock,dram,pbus,length,lane,value);
  if(kind == 8) joinedPiActive=false;
}
struct JoinedRom : PIDevice {
  auto piAddress(u32 address,PIDeviceTiming timing) -> bool override {
    return cartridge.romDevice.piAddress(address,timing);
  }
  auto piReadHalf(PIDeviceTiming timing) -> maybe<u16> override {
    u32 offset=cartridge.romDevice.piViewOffset;
    auto value=cartridge.romDevice.piReadHalf(timing);
    if(value && joinedPiActive) joined_record("rom","\"transfer\":%u,\"block\":%u,\"offset\":%u,\"value\":%u",
        joinedTransfer,joinedBlock,offset,(u32)*value);
    return value;
  }
  auto piWriteHalf(u16 value,PIDeviceTiming timing) -> void override {
    cartridge.romDevice.piWriteHalf(value,timing);
  }
};
static void joined_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  joined_record("scalar","\"context\":%llu,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"value\":%llu",
      (unsigned long long)joinedContext,(unsigned long long)cpu.ipu.pc,write ? "true" : "false",address,bytes,device,(unsigned long long)value);
}
static void joined_burst(bool write,u32 address,u32 bytes,u32 device,const u32* words) {
  if(bytes != 32) std::abort();
  auto payload=joined_words(words);
  joined_record("burst","\"context\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"words\":%s",
      (unsigned long long)joinedContext,write ? "true" : "false",address,bytes,device,payload.c_str());
}
static void joined_fill(u32 slot,u32 physical,u32 index,const u32* words) {
  auto payload=joined_words(words);
  joined_record("fill","\"context\":%llu,\"slot\":%u,\"physical\":%u,\"index\":%u,\"words\":%s",
      (unsigned long long)joinedContext,slot,physical,index,payload.c_str());
}
static void joined_boundary(bool begin,u64 vaddr,u32 translated,u32 bus,bool cached,u32 value) {
  if(!joinedEnabled) return;
  if(begin) { if(joinedContext) std::abort(); joinedContext=joinedEvents.size()+1; }
  if(!joinedContext) std::abort();
  joined_record(begin ? "begin" : "end","\"context\":%llu,\"vaddr\":%llu,\"translated\":%u,\"bus\":%u,\"cached\":%s,\"value\":%u",
      (unsigned long long)joinedContext,(unsigned long long)vaddr,translated,bus,cached ? "true" : "false",value);
  if(!begin) joinedContext=0;
}
static void joined_cache(u64 pc,u32 operation,u64 vaddr,u32 physical,u32 beforeTag,u32 afterTag,const u32* before,const u32* after) {
  auto beforeWords=joined_words(before), afterWords=joined_words(after);
  joined_record("cache","\"pc\":%llu,\"operation\":%u,\"vaddr\":%llu,\"physical\":%u,\"before_tag\":%u,\"after_tag\":%u,\"before_words\":%s,\"after_words\":%s",
      (unsigned long long)pc,operation,(unsigned long long)vaddr,physical,beforeTag,afterTag,beforeWords.c_str(),afterWords.c_str());
}
static void joined_fetch() {
  u32 pa=plaidFetchAccess.physical,word=cpu.disassembler.fetchedWord();
  bool cached=plaidFetchAccess.cached;
  auto& line=cpu.icache.line(cpu.ipu.pc);
  auto words=cached ? joined_words(line.words) : std::string("[]");
  joined_record("fetch","\"pc\":%llu,\"physical\":%u,\"cached\":%s,\"word\":%u,\"slot\":%u,\"tag\":%u,\"words\":%s",
      (unsigned long long)cpu.ipu.pc,pa,cached ? "true" : "false",word,(u32)(cpu.ipu.pc>>5&511),cached ? (u32)line.tagKey : 0,words.c_str());
}
static void joined_print() {
  std::printf("\"events\":[");
  for(size_t i=0;i<joinedEvents.size();i++) std::printf("%s%s",i ? "," : "",joinedEvents[i].c_str());
  std::printf("]");
}
