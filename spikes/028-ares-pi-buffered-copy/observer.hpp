/* SPDX-License-Identifier: ISC
 * Original buffered PI access ledger; copy existing values, never access guests.
 */
struct PiCopyEvent { u64 ordinal; u32 kind,phase,transfer,block,dram,pbus,length,lane,value; };
static std::vector<PiCopyEvent> piCopyEvents;
static bool piCopyEnabled = false;
static u32 piCopyPhase = 0, piCopyTransfer = 0, piCopyBlock = 0;

static void pi_copy_event(u32 kind,u32 dram,u32 pbus,u32 length,u32 lane,u32 value) {
  if(!piCopyEnabled) return;
  if(kind == 1) { ++piCopyTransfer; piCopyBlock = 0; }
  if(kind == 2) ++piCopyBlock;
  piCopyEvents.push_back({piCopyEvents.size()+1,kind,piCopyPhase,piCopyTransfer,piCopyBlock,dram,pbus,length,lane,value});
}
static void pi_copy_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(!piCopyEnabled || device != (u32)RBusDevice::PI_DMA) return;
  if(!write || bytes != Byte || value > 255) std::abort();
  pi_copy_event(9,address,0,bytes,device,value);
}
struct PiCopyRom : PIDevice {
  auto piAddress(u32 address,PIDeviceTiming timing) -> bool override {
    return cartridge.romDevice.piAddress(address,timing);
  }
  auto piReadHalf(PIDeviceTiming timing) -> maybe<u16> override {
    u32 offset = cartridge.romDevice.piViewOffset;
    auto value = cartridge.romDevice.piReadHalf(timing);
    if(value) pi_copy_event(10,0,offset,2,0,*value);
    return value;
  }
  auto piWriteHalf(u16 value,PIDeviceTiming timing) -> void override {
    cartridge.romDevice.piWriteHalf(value,timing);
  }
};
static void print_pi_copy_events() {
  std::printf("\"events\":[");
  for(size_t i=0;i<piCopyEvents.size();i++) {
    const auto& e = piCopyEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"kind\":%u,\"phase\":%u,\"transfer\":%u,\"block\":%u,\"dram\":%u,\"pbus\":%u,\"length\":%u,\"lane\":%u,\"value\":%u}",
      i ? "," : "",(unsigned long long)e.ordinal,e.kind,e.phase,e.transfer,e.block,e.dram,e.pbus,e.length,e.lane,e.value);
  }
  std::printf("]");
}
