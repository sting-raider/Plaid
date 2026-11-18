# Short gameplay and save checks

The local runs use separate save files or copies of existing saves. A
title-screen run checks startup. A short gameplay check also enters a game
with controller input. A save check writes a new slot, exits, and opens the
slot in a new process.

## Paper Mario (USA)

The normal ROM-built RT64 artifact at `5bc4b3d7` created a named File 1
from a blank 128 KiB FlashRAM image and completed the creation run at
VI 6570 with fault 0. A new process opened the saved slot and reached
Mario's house and Peach's letter. The FlashRAM hash matched after reload.

Dismiss the letter to reproduce fault 3 at VI 5319. A linked call at
`800e5c40` targets `802b6348`. The complete 1,424-byte image in the
fault capture at `802b6000` matches ROM `e24040..e245d0`. The guest
table stores callback entry, ROM start, ROM end and flags at 16-byte
intervals. The caller passes the row's ROM endpoints and a fixed
destination to a copy helper, then calls the row's callback.

Discovery reads some ends and flags across these rows as larger slot
declarations. One such interval starts at ROM `e236e0` and extends to
`1000000`, covering the missing file. The broad declaration discards an
explicit raw candidate during catalog deduplication. A bounded local
diagnostic declaration retains the 1,424-byte file and lowers its
callback. Automatic discovery of this table format and short gameplay
validation remain open.

## Pokémon Stadium 2 (USA)

The installed 0.3.6 artifact passed its startup check at VI 299. With a
copy of the existing FlashRAM and Start presses at VIs 650 and 850,
the visible run stopped at VI 945 with fault 3. The caller at
`8004e350` tried to call `801514f0`.

The call target is the first executable word of a catalogued FRAGMENT
loaded at `801514d0`. Its header jumps to the initializer at offset
`0x3ec`. Separately, a HI16/LO16 relocation pair in the module
constructs a function pointer to offset `0x20`. The old map omitted that
body. With the header boundary recognized, the rebuilt map marks it
address-taken and lowers it at `80930020`. The site remains guarded by
native dispatch.

The rebuilt artifact passes the same Start and menu route with a copy
of the same FlashRAM, reaches the Poké Cup entry screen and completes
65 seconds at VI 3841 with fault 0. The artifact still reports seven
residual sites and `native_complete: false`.

The fragment-boundary regression checks the declared start, bad magic
and a jump back into the header. The local gate passed all 82 runtime
checks and seven visible ROM controls. The thread lifecycle check
passed on an isolated rerun after timing out under parallel load.
