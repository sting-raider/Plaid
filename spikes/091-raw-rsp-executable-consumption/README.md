# Actual IMEM reads feed performed RSP instruction occurrences

Extend the existing raw-clock PI/RAM/SP state with the exact returned IMEM Word
read and a separately performed RSP instruction begin/end. Freeze byte parents
at that read using the shared SP writer selector. The instruction consumes its
returned raw-clock read ID; matching PC or equal words cannot substitute for it.
Unknown code roots remain explicit samples, and unused lookahead reads supply no
instruction occurrence. All broad proof flags remain false.

The initial PC-only candidate was rejected before integration. At the exact pin,
JR/JALR retain low logical PC bits while the Word read masks its address. A paired
instruction can also be performed after MTC0 sets HALT. The final contract keeps
logical PC, actual read address, aligned offset, begin/end status and original
read/begin/end ordinals separately. It does not restrict discovery to aligned PCs
or infer execution suppression from a status flag.

```text
python spikes/091-raw-rsp-executable-consumption/test_consumer.py
python spikes/091-raw-rsp-executable-consumption/test_prepare.py
python spikes/091-raw-rsp-executable-consumption/run.py
python spikes/091-raw-rsp-executable-consumption/run.py --verify-existing
```

Strict source v7 admits `rsp_imem_read` and read-bound `rsp_instruction` records.
First reads and held lookahead have bounded, distinct receipt lifetimes; stale,
missing, mismatched or multiply consumed reads reject. Reads freeze before later
equal writes or installations. Performed instruction reports coalesce only equal
semantic samples while digesting every discrete read/begin/end occurrence. New
`rsp_consumption`/SP-PI report-v2 appears only when an instruction is performed;
earlier source/report paths remain unchanged. V7's SP projection uses report-v3.

The opt-in shadow records each of the interpreter's two existing read sites once,
including lookahead, and binds only actually performed instructions. It adds no
guest access or reference object field. Default shadows remain byte-exact after
normalizing generated output paths, verified against the retained v6 build.

The fresh pinned ISC ares control executes identity/translated PI copies through
IMEM installation and actual RSP consumption. Guest JR demonstrates logical3/7/11
with actual aligned0/4/8 reads. A MTC0/VNOP pair demonstrates performed begin-HALT1.
Its222 events contain32 reads,24 performed instructions and8 unused lookaheads;
28 full backing/machine checkpoints agree baseline/disabled/enabled/repeat.
Descriptor/mapping/register/IMEM seed/stepping controls remain opaque. Register/
task ancestry, hardware consensus and continuous executable lifetime stay OPEN.

Local capture uses spike057's `--history storage-rsp-exec`. The supplied100k
prefix contains no performed RSP instruction yet, but retains the exact424,660
record legacy body, fetch and checkpoint controls with repeat equality. Complete
canonical/independent replay agrees. ROM-derived streams, binaries and licensed
reference shadows/notices stay ignored; no ROM/assets enter Git. Complete writer,
source, cache/mapping, reset/restore/epoch, whole-ROM and native closure remain OPEN.
