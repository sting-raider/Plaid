# Pinned function/table hint comparison

Question: given original synthetic mapped bytes and explicit text/rodata spans,
when pinned spimdisasm analyzes them, does it provide useful function/pointer
hints that can complement Plaid's reachable CFG without becoming closure proof?

Pins: spimdisasm `4b5d4c68eeb9f9eae14b3bb713971433ae2c3c43` (1.42.4),
Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` (1.16.2). Both MIT.
Source licenses remain in the ignored reference checkouts; no implementation is
copied into Plaid. The Python bindings are built separately for this experiment.

Run `python spikes/001-spimdisasm/compare.py` after fetching these pins into
`.refs/`. Linux needs GCC and Python development headers; Windows uses WSL
Ubuntu. `PLAID_PYTHON_DEPS` may point to an extracted header prefix. This run used
Ubuntu's `libpython3.14-dev=3.14.4-1` extracted under ignored
`target/reference-tools/python-root/`. No global Python packages are installed.
Outputs and the binding cache live in `target/spimdisasm-spike/`.

The experiment uses the pinned backend APIs: Context, SectionText/SectionRodata,
`analyze`, symbol metadata and disassembly. No user symbols are seeded. Default
backend configuration includes trust in direct JAL function hints. Text/rodata
classification and virtual mapping are supplied, not recovered automatically.

## Verdict: PARTIAL

### Evidence

The four fixture assertions pass:

| Fixture | Function hints | Plaid reachable blocks | Result |
|---|---:|---:|---|
| Direct call | 2 | 4 | Both identify the callee at 80000020; hints include 3 padding words beyond reach. |
| Constant JR and unreachable words | 2 | 2 | Both identify target 80000040; function extents include 14 extra words, including unreachable JR bytes. |
| Guarded pointer table | 1 | 5 | spimdisasm identifies table at 80000100 and labels 80000040/50; Plaid retains both as uncertified candidates. |
| Truncated JR | 1 | 1 | A function hint exists even though Plaid reports unsupported/missing delay-slot coverage. |

`reference.json` records pin/version, input hashes, function extents, symbol/table
hints and assembly. `comparison.json` records reachable blocks, candidate targets,
unresolved kinds and hinted words outside discovered reach. These are reproducible
synthetic observations, not a function-detection accuracy or performance benchmark.

### Constraints and surprises

Function extents may include alignment/padding and unreachable code-like data.
They cannot authorize decoding every word as reachable code. A table pattern and
its entries do not prove data immutability, complete guard coverage or dispatch
lifetime. Manual section boundaries are a major input dependency. Both tools use
the same pinned Rabbitizer decoder; this is not an independent CPU oracle.
The backend labels a truncated return as a function while Plaid retains a blocker.

### Recommendation

Consider a separate, provenance-bearing candidate-hint adapter only after an
explicit production design decision. Retain canonical input hashes, image/
generation/mapping identity and uncertainty. Recheck instruction CFG and pointer
sets independently; never promote a function/table label to executable-universe
closure or native readiness. Do not add spimdisasm to Plaid's production runtime.
