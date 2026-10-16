// Synthetic RT64 regression; no GPU, ROM, microcode or game command capture.
#define SDL_MAIN_HANDLED
#include "hle/rt64_rdp.h"
#include "hle/rt64_interpreter.h"
#include <cstdio>
#include <cstring>

static int rectangles = 0;
static bool rectangleValid = true;
static void rectangle(RT64::State *, RT64::DisplayList **dl) {
    rectangleValid &= (*dl)[0].w0 == 0x24000100 && (*dl)[0].w1 == 0x00000200 &&
        (*dl)[1].w0 == 0x11223344 && (*dl)[1].w1 == 0x55667788;
    rectangles++;
}
static void interrupt() {}

int main() {
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
