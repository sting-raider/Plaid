/* SPDX-License-Identifier: ISC */
struct RawTlbEntry {
  std::array<bool,2> global,valid,dirty;
  std::array<u32,2> cca;
  std::array<u64,2> physical;
  u32 pageMask,asid,region;
  u64 virtualAddress,maskHi,maskLo,select;
  bool globals;
};
static RawTlbEntry raw_tlb_entry(const CPU::TLB::Entry& x) {
  return {{bool(x.global[0]),bool(x.global[1])},{bool(x.valid[0]),bool(x.valid[1])},
    {bool(x.dirty[0]),bool(x.dirty[1])},{u32(x.cacheAlgorithm[0]),u32(x.cacheAlgorithm[1])},
    {u64(x.physicalAddress[0]),u64(x.physicalAddress[1])},u32(x.pageMask),u32(x.addressSpaceID),u32(x.region),
    u64(x.virtualAddress),u64(x.addressMaskHi),u64(x.addressMaskLo),u64(x.addressSelect),bool(x.globals)};
}
static std::vector<RawTlbEntry> raw_tlb_entries() {
  std::vector<RawTlbEntry> result;for(const auto& x:cpu.tlb.entry)result.push_back(raw_tlb_entry(x));return result;
}
static void print_tlb_entry(const RawTlbEntry& x) {
  std::printf("{\"global\":[%s,%s],\"valid\":[%s,%s],\"dirty\":[%s,%s],\"cca\":[%u,%u],\"physical\":[%llu,%llu],\"page_mask\":%u,\"virtual_address\":%llu,\"asid\":%u,\"region\":%u,\"globals\":%s,\"mask_hi\":%llu,\"mask_lo\":%llu,\"select\":%llu}",
    x.global[0]?"true":"false",x.global[1]?"true":"false",x.valid[0]?"true":"false",x.valid[1]?"true":"false",
    x.dirty[0]?"true":"false",x.dirty[1]?"true":"false",x.cca[0],x.cca[1],
    (unsigned long long)x.physical[0],(unsigned long long)x.physical[1],x.pageMask,(unsigned long long)x.virtualAddress,x.asid,x.region,
    x.globals?"true":"false",(unsigned long long)x.maskHi,(unsigned long long)x.maskLo,(unsigned long long)x.select);
}
static void print_tlb_entries(const std::vector<RawTlbEntry>& entries) {
  std::printf("[");for(size_t n=0;n<entries.size();n++){if(n)std::printf(",");print_tlb_entry(entries[n]);}std::printf("]");
}
static void print_initial_tlb() {
  std::printf("{\"index\":%u,\"staged\":",u32(cpu.scc.index.tlbEntry));print_tlb_entry(raw_tlb_entry(cpu.scc.tlb));
  std::printf(",\"entries\":");print_tlb_entries(raw_tlb_entries());std::printf("}");
}
static string raw_tlb_digest() {
  string result{u32(cpu.scc.index.tlbEntry)};auto entries=raw_tlb_entries();entries.push_back(raw_tlb_entry(cpu.scc.tlb));
  for(const auto& x:entries){for(u32 n=0;n<2;n++)result.append(":",u32(x.global[n]),":",u32(x.valid[n]),":",u32(x.dirty[n]),":",x.cca[n],":",x.physical[n]);
    result.append(":",x.pageMask,":",x.virtualAddress,":",x.asid,":",x.region,":",u32(x.globals),":",x.maskHi,":",x.maskLo,":",x.select);}
  return result;
}
