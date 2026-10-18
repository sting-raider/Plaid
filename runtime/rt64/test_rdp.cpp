// Synthetic RT64 regression; no GPU, ROM, microcode or game command capture.
#define SDL_MAIN_HANDLED
#include "hle/rt64_rdp.h"
#include "hle/rt64_interpreter.h"
#include "readback.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

static Readback pendingReadback;

void plaidReadback(uint32_t physical, uint32_t size) {
    pendingReadback.record(physical, size);
}

struct WritebackCall {
    uint32_t physical;
    std::vector<uint8_t> bytes;
};

struct WritebackContext {
    std::vector<uint8_t> ram;
    std::vector<WritebackCall> calls;
    int attempts = 0;
    bool reject = false;
};

extern "C" int plaidTestWriteback(void *opaque, uint32_t physical, uint32_t size, const uint8_t *bytes) {
    auto *context = static_cast<WritebackContext *>(opaque);
    context->attempts++;
    if (context->reject || physical > context->ram.size() || size > context->ram.size() - physical) return 1;
    context->calls.push_back({physical, std::vector<uint8_t>(bytes, bytes + size)});
    if (size) std::memcpy(context->ram.data() + physical, bytes, size);
    return 0;
}

static int readbackContract() {
    std::vector<uint8_t> rdram(16), seen(16), before;
    WritebackContext context{std::vector<uint8_t>(16), {}, 0, false};
    for (uint32_t p = 0; p < rdram.size(); p++) rdram[p ^ 3u] = uint8_t(0x40 + p);

    // The patched fullSync hook reports physical spans; the helper must
    // convert partial words by absolute RDRAM byte address, not span offset.
    pendingReadback.clear();
    plaidReadback(5, 3);
    plaidReadback(9, 2);
    if (pendingReadback.finish(rdram, seen, plaidTestWriteback, &context)) return 1;
    if (context.calls.size() != 2 || context.calls[0].physical != 5 || context.calls[0].bytes != std::vector<uint8_t>({0x45, 0x46, 0x47}) ||
        context.calls[1].physical != 9 || context.calls[1].bytes != std::vector<uint8_t>({0x49, 0x4a})) return 2;
    if (seen != context.ram) return 3;

    // Equal-valued transfers still reach the runtime callback; value diffs
    // are not the readback-write census.
    context.calls.clear();
    pendingReadback.clear();
    plaidReadback(5, 3);
    if (pendingReadback.finish(rdram, seen, plaidTestWriteback, &context) || context.calls.size() != 1 || context.attempts != 3) return 4;

    // Refusal and an out-of-range span leave seen unchanged.
    pendingReadback.clear();
    plaidReadback(5, 2);
    before = seen;
    context.reject = true;
    if (!pendingReadback.finish(rdram, seen, plaidTestWriteback, &context) || seen != before) return 5;
    context.reject = false;
    pendingReadback.clear();
    plaidReadback(15, 2);
    const int attempts = context.attempts;
    if (!pendingReadback.finish(rdram, seen, plaidTestWriteback, &context) || seen != before || context.attempts != attempts) return 6;
    pendingReadback.clear();
    std::puts("PASS RT64 readback spans preserve exact coverage, byte order and failure behavior");
    return 0;
}

static int rectangles = 0;
static bool rectangleValid = true;
static void rectangle(RT64::State *, RT64::DisplayList **dl) {
    rectangleValid &= (*dl)[0].w0 == 0x24000100 && (*dl)[0].w1 == 0x00000200 &&
        (*dl)[1].w0 == 0x11223344 && (*dl)[1].w1 == 0x55667788;
    rectangles++;
}
static void interrupt() {}

int main() {
    if (int result = readbackContract()) return result;
    RT64::RDP rdp(nullptr);
    uint64_t original[RDP_TMEM_WORDS];
    std::memset(original, 0xa5, sizeof original);
    std::memcpy(rdp.TMEM, original, sizeof original);
    // These commands must finish before accessing a workload or RDRAM.
    // Before the patch they underflow rowCount and dereference the null state.
    for (uint16_t top : {uint16_t(4), uint16_t(7), uint16_t(1024), uint16_t(4095)}) {
        for (uint16_t bottom : {uint16_t(0), uint16_t(3)}) {
            rdp.loadTile(0, 0, top, 124, bottom);
            if (std::memcmp(rdp.TMEM, original, sizeof original)) return 1;
            if (rdp.tiles[0].ult != top || rdp.tiles[0].lrt != bottom) return 2;
        }
    }
    std::puts("PASS RT64 empty vertical tile loads leave TMEM unchanged");
    // DPC_END can split a command across submissions. Exercise the real raw
    // RDP parser with a synthetic consumer, without creating a GPU device.
    uint8_t ram[64]{};
    uint32_t intr = 0;
    RT64::State state(ram, &intr, interrupt);
    RT64::Interpreter interpreter;
    interpreter.setup(&state);
    state.ext.interpreter = &interpreter;
    state.rdramCheckPending = false;
    state.rdp->gbi = interpreter.gbiManager.getGBIForRDP();
    state.rdp->gbi->map[0x24] = rectangle;
    RT64::DisplayList commands[2];
    commands[0].w0 = 0x24000100; commands[0].w1 = 0x00000200;
    commands[1].w0 = 0x11223344; commands[1].w1 = 0x55667788;
    interpreter.processRDPLists(0, commands, commands + 1);
    if (rectangles || state.rdp->pendingCommandRemainingBytes != 8) return 3;
    interpreter.processRDPLists(0, commands + 1, commands + 2);
    if (rectangles != 1 || !rectangleValid || state.rdp->pendingCommandRemainingBytes) return 4;
    interpreter.processRDPLists(0, commands, commands + 2);
    if (rectangles != 2 || !rectangleValid) return 5;
    std::puts("PASS RT64 raw RDP parser retains split commands across DPC submissions");
    return 0;
}
