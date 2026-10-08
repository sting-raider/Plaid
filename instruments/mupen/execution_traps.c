/* SPDX-License-Identifier: GPL-2.0-or-later
 * Unused runtime services abort. Tested integer/control instructions execute in
 * the pinned CPU implementations; unsupported devices/exception paths cannot
 * silently become a successful execution.
 */
#include <stdio.h>
#include <stdlib.h>
#define TRAP(name) void name(void) { fputs("excluded runtime service: " #name "\n", stderr); abort(); }
TRAP(cached_interp_DDIV)
TRAP(cached_interp_DDIVU)
TRAP(cached_interp_DMULT)
TRAP(cached_interp_DMULTU)
TRAP(cached_interp_MFC0)
TRAP(cached_interp_MTC0)
TRAP(cached_interp_SYSCALL)
TRAP(cached_interp_TLBP)
TRAP(cached_interp_TLBR)
TRAP(cached_interp_TLBWI)
TRAP(cached_interp_TLBWR)
TRAP(cached_interpreter_jump_to)
TRAP(r4300_check_interrupt)
TRAP(validate_pi_request)
TRAP(add_interrupt_event)
TRAP(invalidate_cached_code_hacktarux)
TRAP(translate_event_queue)
TRAP(remove_event)
TRAP(add_interrupt_event_count)
