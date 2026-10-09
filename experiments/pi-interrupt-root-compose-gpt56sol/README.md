# PI interrupt-root composition replay

Bounded adversarial evidence for `research/pi-interrupt-root-composition.md`.

## Reproduce

With exact repositories from `refs.lock.toml` checked out under `.refs/`:

```bash
python3 experiments/pi-interrupt-root-compose-gpt56sol/source_guard.py
python3 -m py_compile \
  experiments/pi-interrupt-root-compose-gpt56sol/model.py \
  experiments/pi-interrupt-root-compose-gpt56sol/source_guard.py
python3 experiments/pi-interrupt-root-compose-gpt56sol/model.py
```

The branch-only workflow `.github/workflows/research-pi-interrupt-root-compose.yml`
fetches exact ares, Mupen64Plus and Gopher64 pins, fails closed on source drift,
runs the deterministic adversaries plus 64 x 5,000-operation replay, hashes the
receipts and uploads them.

## Verified receipt

GitHub Actions run `38005465802` on branch commit
`c88a763761079c3a445a55532ac44ec3cea09c4d` completed successfully on Ubuntu 24.04.
Job `114073119015` passed exact reference fetch, source guards, Python compilation,
causal replay, hashing and artifact upload.

Observed replay:

```text
histories = 64
operations = 320000
queue_failed_copies = 6154
histories_with_copy_without_completion = 64
roots_whose_source_is_not_latest_copy = 56
same_value_mask_operations = 40095
RESULT_SHA256=90187885016ce98b2f8fbcf4104b419c9a2450c182a9d2cd82093b61a9eb0ab2
PASS: copy, completion, MI pending/mask, CPU gate and root generations remain causally distinct
```

File hashes from the successful job:

```text
33001bf0f4c2cee4c8d5da523004da8b42ad7b45307dc47f0dea4d7a7d6a2f71  model.py
6fb2604bcf4ab2a28f16a1ac88d09668ebf369814fbdf8ddc98845ef94a8afea  source_guard.py
63329edddaca0f20e8ac691d5dc04f4cde842eedc7a3133de69a7618ac0fc1f9  results.txt
```

Artifact ID `11650474479`, artifact ZIP digest
`sha256:2ebe10713be27d1f521a2ee1c68153e009b468131de920f426dd709f0d265c05`.

## Scope

This executable replay is a source-guarded causal extraction. It deliberately does
not claim that ares queue saturation is N64 hardware behavior and it does not replace
the prior full-reference interrupt-root fixture. It composes that validated root
contract with the already-validated PI request/queue counterexample and independent
Mupen/Gopher source agreement on the coarse PI-completion -> MI-pending -> mask ->
CPU-gate separation.
