# Compile the native program once

ADR-0301 follows ADR-0300. Exact-tree validation and acceptance receipts are
retained under ignored target/receipts/runtime-units-exact/.

The native pipeline includes the complete generated main unit in both the
headless runtime and the window runtime. Diagnostics that rebuild the runtime
repeat that work again. The main unit contains the guarded dispatch tables,
source witnesses and preload constants. Its compilation takes minutes for
large maps even when all guest function objects are cached.

The candidate exposes optional lower-map --runtime-unit output. Program
definitions compile into one object; a generated runtime header declares their
public seam and contains the same state/helper declarations as the existing
multipart units. Only preload and host-entry functions gain external linkage.
The native pipeline links the single program object into each runtime variant.
Runtime adapter cache dependencies include the header, boot payloads, runtime
source/headers and RSP ABI headers. Program bodies remain dependencies of the
separate program object.

The synthetic SDK Status/scheduler test executes single-unit, ordinary multipart and
separate-runtime artifacts through actual host handoffs. The guest function
units are byte identical. The 215126-block retained Majora's Mask map also
produces guest units byte identical to the ADR-0300 build. Its separate compile
benchmark compiled the program once in 226.359 s, then the headless/window
adapters in 1.203/1.188 s. The previous combined builds took 259.764/242.088 s
(measured source-write to successful object-stamp timestamps in the fresh
ADR-0300 MM output). This is an iteration-cost comparison under build load,
not an artifact runtime-speed claim. The visible silent five-second trial
stops with VI 267, fault 0, PC 00000000. Full acceptance remains pending.
The separate-runtime two-stage refill fixture also matches complete pinned
reference state in bare-kernel and SDK-owned modes, retaining atomic refusal
and source mutations. Ignored benchmark commands/timings are under
target/native/units-mm/.
