/* Synchronous graphics boundary; RAM and returned bytes use guest byte order. */
#ifndef PLAID_GFX_H
#define PLAID_GFX_H
#include <stdint.h>
#ifndef PLAID_GFX_API
#define PLAID_GFX_API
#endif
#ifdef __cplusplus
extern "C" {
#endif
typedef int (*plaid_gfx_writeback)(void *context, uint32_t physical, uint32_t size, const uint8_t *bytes);
PLAID_GFX_API int plaid_gfx_task(const uint8_t *ram, uint32_t ucode, uint32_t ucode_data, uint32_t data_ptr,
                   plaid_gfx_writeback writeback, void *context);
PLAID_GFX_API int plaid_gfx_rdp(const uint8_t *ram, const uint8_t *commands, uint32_t size, const uint8_t *dirty_pages,
                  plaid_gfx_writeback writeback, void *context);
#ifdef __cplusplus
}
#endif
#endif
