/* SPDX-License-Identifier: GPL-2.0-or-later
 * Headless, synthetic integer/control execution with the actual pinned CPUs.
 * The harness stops at a sentinel loop; it is not a boot/device/timing oracle.
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "device/device.h"
#include "device/r4300/new_dynarec/new_dynarec.h"
#include "device/r4300/pure_interp.h"
#include "main/rom.h"
#include "api/callbacks.h"
struct device g_dev;
m64p_rom_header ROM_HEADER;
static unsigned int interrupts;
static struct memory memory;
static uint32_t sp_memory[SP_MEM_SIZE / 4];

void DebugMessage(int level, const char *message, ...) {
    (void)level; (void)message;
}
/* Stop policy is shared by both CPUs; instruction semantics and Count updates
 * come from the pinned reference. No guest-visible device interrupts are tested. */
void gen_interrupt(struct r4300_core *core) {
    if (++interrupts > 1000) abort();
    if (*r4300_pc(core) == 0x80000100u) *r4300_stop(core) = 1;
    *r4300_cp0_cycle_count(&core->cp0) = -100;
    core->cp0.next_interrupt = r4300_cp0_regs(&core->cp0)[CP0_COUNT_REG] + 100;
}
/* Flat synthetic memory mapping only; TLB/MMIO access is deliberately excluded. */
uint32_t *mem_base_u32(void *base, uint32_t address) {
    (void)base;
    if (address < 0x800000) return &g_dev.rdram.dram[address / 4];
    if (address >= 0x04000000 && address < 0x04002000)
        return &g_dev.sp.mem[(address - 0x04000000) / 4];
    abort();
}
unsigned int add_random_interrupt_time(struct r4300_core *core) { (void)core; return 0; }

int main(int argc, char **argv) {
    struct r4300_core *core = &g_dev.r4300;
    struct new_dynarec_hot_state *state = &core->new_dynarec_hot_state;
    struct interrupt_handler handlers[CP0_INTERRUPT_HANDLERS_COUNT] = {{0}};
    struct cart_rom cart;
    FILE *file;
    uint32_t *cartridge;
    long cartridge_size;
    unsigned int i;
    int pure;
    if (argc != 3) return 1;
    pure = !strcmp(argv[1], "pure");
    if (!pure && strcmp(argv[1], "dynarec")) return 2;
    file = fopen(argv[2], "rb");
    if (!file || fseek(file, 0, SEEK_END)) return 3;
    cartridge_size = ftell(file);
    if (cartridge_size < 64 || cartridge_size > 65536 || cartridge_size % 4 || fseek(file, 0, SEEK_SET)) return 3;
    cartridge = malloc((size_t)cartridge_size);
    if (!cartridge || fread(cartridge, 1, (size_t)cartridge_size, file) != (size_t)cartridge_size) return 3;
    fclose(file);
    /* Convert canonical BE bytes to the reference's host-word ROM layout. */
    for (i = 0; i < (unsigned long)cartridge_size / 4; ++i) {
        uint8_t *p = (uint8_t *)&cartridge[i];
        uint32_t word = ((uint32_t)p[0]<<24) | ((uint32_t)p[1]<<16) | ((uint32_t)p[2]<<8) | p[3];
        cartridge[i] = word;
    }
    g_dev.rdram.dram = calloc(0x800000, 1);
    if (!g_dev.rdram.dram) return 4;
    g_dev.rdram.dram_size = 0x800000;
    g_dev.sp.mem = sp_memory;
    init_r4300(core, &memory, &g_dev.mi, &g_dev.rdram, handlers,
        pure ? EMUMODE_PURE_INTERPRETER : EMUMODE_DYNAREC, 2, 0, 0, 0, 0xa4000040);
    state->regs[10] = 3;
    state->cycle_count = -100;
    core->cp0.next_interrupt = 100;
    g_dev.sp.mem[0x40 / 4] = 0x3c198000; /* LUI t9, 0x8000 */
    g_dev.sp.mem[0x44 / 4] = 0x03200008; /* JR t9 */
    g_dev.sp.mem[0x48 / 4] = 0;
    if (!pure) new_dynarec_init();
    init_cart_rom(&cart, (uint8_t *)cartridge, (size_t)cartridge_size, core, &g_dev.pi);
    cart_rom_dma_write(&cart, (uint8_t *)g_dev.rdram.dram, 0, 0x10000040, (size_t)cartridge_size - 64);
    if (pure) run_pure_interpreter(core);
    else new_dyna_start();
    printf("{\"pc\":%" PRIu32 ",\"hi\":%" PRId64 ",\"lo\":%" PRId64 ",\"regs\":[",
        *r4300_pc(core), state->hi, state->lo);
    for (i = 0; i < 32; ++i) printf("%s%" PRId64, i ? "," : "", state->regs[i]);
    printf("]}\n");
    if (!pure) new_dynarec_cleanup();
    free(g_dev.rdram.dram);
    free(cartridge);
    return 0;
}
