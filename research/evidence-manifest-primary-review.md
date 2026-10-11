# Primary harvest: externally expected evidence commitments

2026-10-11. Reviewed model-only; no production manifest schema adopted.

Reviewed complete note/model/ablations/workflow and closeout 6097622292 from
`research/evidence-manifest-composition-gpt56sol`, exact head
`31ca1f778f3b0ac2161a676eb2944437fbc74757`. Full primary replay reproduces all
fixed checks and 4,000 fuzz histories on every declared deletion/substitution/
reorder/merge axis. Semantic digest:
`519772b1ad3bdaa555a30c49fd92b65c14e3be9b6aff5d2c5b58434467e13fec`.
The complete ablation reproduces digest
`8cc5a6caa077d6bf9a1115fc5b92b43994be5b96d52044efafbaca2afb2acac4`.
Successful final-head Actions 38052922476 / artifact 11670331397 supplies two
matching complete stable model reports (only build/verify timing excluded) and
two identical ablations. Exact script SHA-256 values are respectively
`e6c241f2d9e4fd5ff631ff7b017aa7e7bb6bcb720871be1caf27efc89f89cbd9` and
`d7d55db9489376093d42bbfc561289462c6330852f8112beb744e5c8114cf4d5`.

The 40,000-event baseline reproduces 12,398,469 bytes of primitive leaves versus
15,601 bytes of full manifests. The root-only external map is 5,601 bytes.
Verification still hashes all events; do not claim sublinear proof checking.
Source membership alone detects complete disappearance, count detects changed
cardinality, and a semantic commitment or complete raw-source replay is needed
for same-count substitutions. Recomputing a map-controlled hash after deletion
cannot preserve the original expectation.

Current main still validates contiguous trace sequence and terminal count,
hashes complete canonical NDJSON, and inserts every event evidence identity
before projecting typed facts. Its whole-ROM/native gate remains OPEN. Those
source identities do not supply an external expected source set after every
related map fact is deleted. The model clarifies that future certificate
boundary; it does not implement or authenticate it in production.

Additional primary probes limit promotion of the prototype:

- Its merge removes a conflicting local manifest. Merging that result with the
  original valid map restores the manifest and strict acceptance. A same-session
  contradictory commitment is not retained as a permanent conflict or rejected
  at merge input validation.
- A malformed primitive semantic tuple containing the same key twice commits
  only the later value because `leaf()` converts it to a dictionary. A shadowed
  forged earlier value is accepted against the original expected root.
- An extra local manifest with no primitive events is ignored by the strict
  verifier; it checks the actual primitive session set and expected manifests,
  not exact local-manifest membership or a complete serialized schema.

Reproduce from `base_fixture()`: clone the base, replace session A's local root
with `'f'*64`, then merge with base. Verification rejects; merging that conflict
result with base again accepts. For the duplicate-key probe, replace the first
event's semantic tuple with `((key,'forged'),)+event.semantics`, where key is its
first existing key; strict verification accepts without rewriting the expected
root. For the extra-manifest probe add a copy of session A's manifest under key
`unexpected` with its session field changed accordingly; verification accepts.

These probes concern invalid inputs/contradictory local state outside the valid
constructor corpus. They do not refute the external-expectation boundary or the
declared 4,000-case results. A production implementation must strictly validate
typed leaves and local commitments, reject conflicting imports or retain sticky
conflicts, and define its exact source-membership/partial-map contract. Hashing
does not establish sensor completeness or trustworthy capture origins.

Disposition: retain the bounded deletion counterexamples, ablations and size
baseline as model evidence. No Python model, branch workflow, ProgramMap
self-hash or new production architecture merged. Trusted expected-source inputs,
complete source/projection verification, sharding, sensor coverage, lifetime and
whole-ROM/native closure remain OPEN. No progress milestone changes.
