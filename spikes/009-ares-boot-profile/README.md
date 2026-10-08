# Explicit firmware and boot profile

Hypothesis: a new header can preserve the complete fixed experiment profile and
firmware input while projecting byte-for-byte onto the earlier boot capture.
Research v4 records a typed boot_inputs object: firmware hash/size, NTSC region,
CIC-NUS-6102, 8 MiB RAM, deterministic entropy, reference PIF HLE and enforced IPL2
checksum. These are declared inputs, not automatic CIC discovery, PIF source
witnesses or complete hardware equivalence. Firmware bytes remain ignored.

Run `python spikes/009-ares-boot-profile/run.py --budget 1000000`.
Verdict: VALIDATED at one million calls. Plain/traced/repeated checkpoints and
messages match; the complete v3 projection matches its existing golden bytes.
The full checkpoint also matches the previous boot baseline. The v4 stream is
154,485,706 bytes, SHA-256
`38a0781c763a110ca419af65bf9f1a19ed96cd9282e01b2545486d9d865bd937`.
The original v3 experiment remains available; v4 changes declared metadata only.
The longer prefix is checked separately with `--budget 10000000`.
No executable identity is promoted by this experiment. Production handling must
require actual supplied firmware bytes and recheck the full raw source.
