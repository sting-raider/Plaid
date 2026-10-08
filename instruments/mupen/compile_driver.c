/* SPDX-License-Identifier: GPL-2.0-or-later
 * Compiles synthetic words with the real pinned recompiler, but NEVER enters
 * generated host code. This is a hook/protocol test, not a CPU execution oracle.
 */
#include <stdlib.h>
#include "device/device.h"
#include "device/r4300/new_dynarec/new_dynarec.h"
#include "main/rom.h"
#include "api/callbacks.h"
struct device g_dev;
m64p_rom_header ROM_HEADER;
int new_recompile_block(int addr);
void *get_addr_ht(unsigned int vaddr);
void DebugMessage(int level, const char *message, ...) {
    (void)level; (void)message;
}
void invalidate_r4300_cached_code(struct r4300_core *core, uint32_t address, size_t size) {
    invalidate_cached_code_new_dynarec(core,address,size);
}
unsigned int add_random_interrupt_time(struct r4300_core *core) { (void)core; return 0; }
int main(void) {
    uint32_t cartridge[1024] = {0};
    struct cart_rom cart;
    g_dev.rdram.dram = calloc(0x800000, 1);
    if (!g_dev.rdram.dram) return 1;
    g_dev.rdram.dram_size = 0x800000;
    g_dev.r4300.rdram = &g_dev.rdram;
    new_dynarec_init();
    cartridge[0] = 0x80371240;
    cartridge[16] = 0x08000000;
    init_cart_rom(&cart,(uint8_t *)cartridge,sizeof(cartridge),&g_dev.r4300,&g_dev.pi);
    cart_rom_dma_write(&cart,(uint8_t *)g_dev.rdram.dram,0,0x10000040,8);
    if (new_recompile_block((int)0x80000000)) return 2;
    if (!get_addr_ht(0x80000000)) return 3;
    invalidate_cached_code_new_dynarec(&g_dev.r4300, 0x80000000, 8);
    g_dev.rdram.dram[0] = 0x3c088000;
    g_dev.rdram.dram[1] = 0x35080000;
    g_dev.rdram.dram[2] = 0x01000008;
    g_dev.rdram.dram[3] = 0;
    if (new_recompile_block((int)0x80000000)) return 4;
    if (!get_addr_ht(0x80000000)) return 5;
    g_dev.rdram.dram[0x1000 / 4] = 0;
    g_dev.rdram.dram[0x1004 / 4] = 0x08000401;
    g_dev.rdram.dram[0x1008 / 4] = 0;
    if (new_recompile_block((int)0x80001001)) return 6;
    g_dev.rdram.dram[0x2000 / 4] = 0x08000000;
    g_dev.rdram.dram[0x2004 / 4] = 0;
    if (new_recompile_block((int)0x80002000)) return 7;
    /* Requested lengths differ from actual ROM/RDRAM bytes copied. */
    cart_rom_dma_write(&cart,(uint8_t *)g_dev.rdram.dram,0x2000,0x10000ffc,8);
    cart_rom_dma_write(&cart,(uint8_t *)g_dev.rdram.dram,0x7ffffc,0x10000040,16);
    cart_rom_dma_write(&cart,(uint8_t *)g_dev.rdram.dram,0x2010,0x10001000,8);
    invalidate_cached_code_new_dynarec(&g_dev.r4300, 0, 0);
    new_dynarec_cleanup();
    free(g_dev.rdram.dram);
    return 0;
}
