/* SPDX-License-Identifier: ISC
 * Original ordered callback ledger for the declared controlled fixture only.
 * Indices reference separately retained payloads; no guest accesses occur here.
 */
struct HistoryEvent { const char* kind; u64 index; };
struct FixtureWrite { u32 address, word; };
static bool historyEnabled = false;
static std::vector<HistoryEvent> historyEvents;
static std::vector<FixtureWrite> fixtureWrites;

static void history_event(const char* kind,u64 index) {
  if(historyEnabled) historyEvents.push_back({kind,index});
}

static void history_fixture_write(u32 address,u32 word) {
  if(!historyEnabled) return;
  fixtureWrites.push_back({address,word});
  history_event("fixture_write",fixtureWrites.size());
}

static void print_history() {
  std::printf(",\"history_policy\":\"controlled_fixture_callbacks_v0\",\"history\":[");
  for(size_t i=0;i<historyEvents.size();i++) {
    const auto& e = historyEvents[i];
    std::printf("%s{\"seq\":%llu,\"kind\":\"%s\",\"index\":%llu}",
      i ? "," : "",(unsigned long long)i+1,e.kind,(unsigned long long)e.index);
  }
  std::printf("],\"fixture_writes\":[");
  for(size_t i=0;i<fixtureWrites.size();i++) {
    const auto& e = fixtureWrites[i];
    std::printf("%s{\"actor\":\"fixture\",\"address\":%u,\"bytes\":4,\"word\":%u}",
      i ? "," : "",e.address,e.word);
  }
  std::printf("]");
}
