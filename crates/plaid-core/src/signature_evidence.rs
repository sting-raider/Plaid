//! Source-bound optional static signature candidates.
//!
//! A successful signature match is a naming/classification hint only. It does not
//! establish unique symbol identity, reachability, byte provenance, immutability,
//! executable lifetime, exhaustive indirect targets, or closed-world readiness.

use crate::{program::CodeAddress, rom::sha256};
use serde::Serialize;

pub const FORMAT: &str = "plaid-n64sym-candidate-v0";
pub const N64SYM_REVISION: &str = "ccf4600f3389f1a84bde23339225cf372fdf7712";
const MAX_SOURCE_BYTES: usize = 16 * 1024 * 1024;
const MAX_SIGNATURES: usize = 100_000;
const MAX_RELOCATIONS_PER_SIGNATURE: usize = 16_384;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum N64SymRelocationKind {
    Target26,
    Hi16,
    Lo16,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(deny_unknown_fields)]
pub struct N64SymRelocation {
    kind: N64SymRelocationKind,
    symbol: String,
    offset: u32,
}

impl N64SymRelocation {
    pub fn kind(&self) -> N64SymRelocationKind {
        self.kind
    }

    pub fn symbol(&self) -> &str {
        &self.symbol
    }

    pub fn offset(&self) -> u32 {
        self.offset
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(deny_unknown_fields)]
pub struct N64SymSignatureKey {
    size: u32,
    crc_a: u32,
    crc_b: u32,
}

impl N64SymSignatureKey {
    pub fn size(&self) -> u32 {
        self.size
    }

    pub fn crc_a(&self) -> u32 {
        self.crc_a
    }

    pub fn crc_b(&self) -> u32 {
        self.crc_b
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct N64SymCandidateEvidence {
    format: String,
    source_revision: String,
    signature_source_sha256: String,
    signature_index: u64,
    reported_name: String,
    key: N64SymSignatureKey,
    relocations: Vec<N64SymRelocation>,
    same_key_entries: u64,
    same_crc_b_entries: u64,
    address: CodeAddress,
    matched_bytes_sha256: String,
    normalized_bytes_sha256: String,
    relocation_normalized: bool,
    candidate_only: bool,
    unique_symbol_identity_certified: bool,
    exact_executable_byte_identity_certified: bool,
    reachability_certified: bool,
    byte_provenance_certified: bool,
    immutability_certified: bool,
    executable_lifetime_certified: bool,
    indirect_target_set_exhaustive: bool,
    closed_world_certified: bool,
    native_complete: bool,
}

impl N64SymCandidateEvidence {
    pub fn source_revision(&self) -> &str {
        &self.source_revision
    }

    pub fn signature_source_sha256(&self) -> &str {
        &self.signature_source_sha256
    }

    pub fn signature_index(&self) -> u64 {
        self.signature_index
    }

    pub fn reported_name(&self) -> &str {
        &self.reported_name
    }

    pub fn key(&self) -> N64SymSignatureKey {
        self.key
    }

    pub fn relocations(&self) -> &[N64SymRelocation] {
        &self.relocations
    }

    pub fn same_key_entries(&self) -> u64 {
        self.same_key_entries
    }

    pub fn same_crc_b_entries(&self) -> u64 {
        self.same_crc_b_entries
    }

    pub fn address(&self) -> &CodeAddress {
        &self.address
    }

    pub fn matched_bytes_sha256(&self) -> &str {
        &self.matched_bytes_sha256
    }

    pub fn normalized_bytes_sha256(&self) -> &str {
        &self.normalized_bytes_sha256
    }

    pub fn relocation_normalized(&self) -> bool {
        self.relocation_normalized
    }

    pub fn candidate_only(&self) -> bool {
        self.candidate_only
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SignatureDefinition {
    name: String,
    key: N64SymSignatureKey,
    relocations: Vec<N64SymRelocation>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn parse_u32(token: &str) -> Result<u32, String> {
    let value = if let Some(hex) = token
        .strip_prefix("0x")
        .or_else(|| token.strip_prefix("0X"))
    {
        u64::from_str_radix(hex, 16)
    } else {
        token.parse::<u64>()
    }
    .map_err(|_| format!("invalid n64sym integer {token:?}"))?;
    u32::try_from(value).map_err(|_| format!("n64sym integer out of range {token:?}"))
}

fn parse_kind(token: &str) -> Result<N64SymRelocationKind, String> {
    match token {
        ".targ26" => Ok(N64SymRelocationKind::Target26),
        ".hi16" => Ok(N64SymRelocationKind::Hi16),
        ".lo16" => Ok(N64SymRelocationKind::Lo16),
        _ => Err(format!("unsupported n64sym relocation directive {token:?}")),
    }
}

fn validate_definition(definition: &mut SignatureDefinition) -> Result<(), String> {
    require(definition.key.size != 0, "zero-sized n64sym signature")?;
    definition
        .relocations
        .sort_by_key(|relocation| relocation.offset);
    require(
        definition.relocations.len() <= MAX_RELOCATIONS_PER_SIGNATURE,
        "too many n64sym relocations",
    )?;
    let mut previous_offset = None;
    for relocation in &definition.relocations {
        require(
            relocation.offset.is_multiple_of(4),
            "unaligned n64sym relocation offset",
        )?;
        require(
            relocation.offset <= definition.key.size.saturating_sub(4),
            "n64sym relocation extends beyond signature",
        )?;
        require(
            previous_offset != Some(relocation.offset),
            "duplicate n64sym relocation offset",
        )?;
        previous_offset = Some(relocation.offset);
    }
    Ok(())
}

fn parse_signature_source(source: &[u8]) -> Result<Vec<SignatureDefinition>, String> {
    require(!source.is_empty(), "empty n64sym signature source")?;
    require(
        source.len() <= MAX_SOURCE_BYTES,
        "n64sym signature source exceeds bounded limit",
    )?;
    let text = std::str::from_utf8(source).map_err(|_| "n64sym signature source is not UTF-8")?;
    let mut definitions = Vec::<SignatureDefinition>::new();

    for (line_index, raw) in text.lines().enumerate() {
        let line = raw.split_once('#').map_or(raw, |(prefix, _)| prefix).trim();
        if line.is_empty() {
            continue;
        }
        let tokens: Vec<_> = line.split_whitespace().collect();
        if line.starts_with('.') {
            require(tokens.len() >= 3, "malformed n64sym relocation line")?;
            let kind = parse_kind(tokens[0])?;
            let definition = definitions
                .last_mut()
                .ok_or("n64sym relocation precedes any signature")?;
            for token in &tokens[2..] {
                require(
                    definition.relocations.len() < MAX_RELOCATIONS_PER_SIGNATURE,
                    "too many n64sym relocations",
                )?;
                definition.relocations.push(N64SymRelocation {
                    kind,
                    symbol: tokens[1].to_string(),
                    offset: parse_u32(token)?,
                });
            }
            continue;
        }

        require(tokens.len() == 4, "malformed n64sym signature line")?;
        require(
            definitions.len() < MAX_SIGNATURES,
            "too many n64sym signatures",
        )?;
        let first = tokens[0]
            .as_bytes()
            .first()
            .copied()
            .ok_or("empty n64sym symbol name")?;
        require(
            first.is_ascii_alphabetic() || first == b'_',
            "invalid n64sym symbol name",
        )?;
        definitions.push(SignatureDefinition {
            name: tokens[0].to_string(),
            key: N64SymSignatureKey {
                size: parse_u32(tokens[1])?,
                crc_a: parse_u32(tokens[2])?,
                crc_b: parse_u32(tokens[3])?,
            },
            relocations: Vec::new(),
        });

        require(
            line_index < MAX_SOURCE_BYTES,
            "n64sym signature source has implausible line count",
        )?;
    }

    require(
        !definitions.is_empty(),
        "n64sym source contains no signatures",
    )?;
    for definition in &mut definitions {
        validate_definition(definition)?;
    }
    Ok(definitions)
}

fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for byte in bytes {
        crc ^= u32::from(*byte);
        for _ in 0..8 {
            crc = if crc & 1 != 0 {
                (crc >> 1) ^ 0xedb8_8320
            } else {
                crc >> 1
            };
        }
    }
    !crc
}

fn normalized_bytes(bytes: &[u8], relocations: &[N64SymRelocation]) -> Result<Vec<u8>, String> {
    let mut normalized = bytes.to_vec();
    for relocation in relocations {
        let offset = usize::try_from(relocation.offset)
            .map_err(|_| "n64sym relocation offset does not fit host usize")?;
        require(
            offset
                .checked_add(4)
                .is_some_and(|end| end <= normalized.len()),
            "n64sym relocation exceeds matched bytes",
        )?;
        match relocation.kind {
            N64SymRelocationKind::Target26 => {
                normalized[offset] &= 0xfc;
                normalized[offset + 1] = 0;
                normalized[offset + 2] = 0;
                normalized[offset + 3] = 0;
            }
            N64SymRelocationKind::Hi16 | N64SymRelocationKind::Lo16 => {
                normalized[offset + 2] = 0;
                normalized[offset + 3] = 0;
            }
        }
    }
    Ok(normalized)
}

/// Verify one exact source-ordered n64sym signature entry against an exact byte span.
///
/// `expected_signature_source_sha256` must come from a separately trusted source
/// receipt. The source entry's reported name remains a candidate label even when
/// this function succeeds.
pub fn inspect_n64sym_candidate(
    signature_source: &[u8],
    expected_signature_source_sha256: &str,
    source_revision: &str,
    signature_index: u64,
    address: CodeAddress,
    matched_bytes: &[u8],
) -> Result<N64SymCandidateEvidence, String> {
    require(
        source_revision == N64SYM_REVISION,
        "unsupported n64sym source revision",
    )?;
    require(
        valid_sha256(expected_signature_source_sha256),
        "invalid n64sym signature-source digest",
    )?;
    let source_digest = sha256(signature_source);
    require(
        source_digest == expected_signature_source_sha256,
        "n64sym signature-source receipt mismatch",
    )?;

    let definitions = parse_signature_source(signature_source)?;
    let index = usize::try_from(signature_index)
        .map_err(|_| "n64sym signature index does not fit host usize")?;
    let definition = definitions
        .get(index)
        .ok_or("n64sym signature index outside source")?;
    let size = usize::try_from(definition.key.size)
        .map_err(|_| "n64sym signature size does not fit host usize")?;
    require(
        matched_bytes.len() == size,
        "matched byte span differs from n64sym signature size",
    )?;

    let normalized = normalized_bytes(matched_bytes, &definition.relocations)?;
    let crc_a_limit = normalized.len().min(8);
    require(
        crc32(&normalized[..crc_a_limit]) == definition.key.crc_a,
        "n64sym crcA mismatch",
    )?;
    require(
        crc32(&normalized) == definition.key.crc_b,
        "n64sym crcB mismatch",
    )?;

    let same_key_entries = definitions
        .iter()
        .filter(|candidate| candidate.key == definition.key)
        .count();
    let same_crc_b_entries = definitions
        .iter()
        .filter(|candidate| candidate.key.crc_b == definition.key.crc_b)
        .count();

    Ok(N64SymCandidateEvidence {
        format: FORMAT.into(),
        source_revision: source_revision.into(),
        signature_source_sha256: source_digest,
        signature_index,
        reported_name: definition.name.clone(),
        key: definition.key,
        relocations: definition.relocations.clone(),
        same_key_entries: u64::try_from(same_key_entries)
            .map_err(|_| "n64sym same-key count overflow")?,
        same_crc_b_entries: u64::try_from(same_crc_b_entries)
            .map_err(|_| "n64sym crcB count overflow")?,
        address,
        matched_bytes_sha256: sha256(matched_bytes),
        normalized_bytes_sha256: sha256(&normalized),
        relocation_normalized: !definition.relocations.is_empty(),
        candidate_only: true,
        unique_symbol_identity_certified: false,
        exact_executable_byte_identity_certified: false,
        reachability_certified: false,
        byte_provenance_certified: false,
        immutability_certified: false,
        executable_lifetime_certified: false,
        indirect_target_set_exhaustive: false,
        closed_world_certified: false,
        native_complete: false,
    })
}

/// Recompute the complete candidate evidence from the source and exact byte span.
pub fn verify_n64sym_candidate(
    evidence: &N64SymCandidateEvidence,
    signature_source: &[u8],
    expected_signature_source_sha256: &str,
    source_revision: &str,
    signature_index: u64,
    address: CodeAddress,
    matched_bytes: &[u8],
) -> Result<(), String> {
    require(
        *evidence
            == inspect_n64sym_candidate(
                signature_source,
                expected_signature_source_sha256,
                source_revision,
                signature_index,
                address,
                matched_bytes,
            )?,
        "n64sym candidate evidence differs from source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::GuestAddr;

    const ALPHA: &[u8] = &[
        0x24, 0x02, 0x00, 0x01, 0x03, 0xe0, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00,
    ];
    const GAMMA: &[u8] = &[
        0x0c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0xe0, 0x00, 0x08, 0x00, 0x00, 0x00,
        0x00,
    ];

    fn address() -> CodeAddress {
        CodeAddress {
            pc: GuestAddr(0x8000_1000),
            image: "fixture".into(),
            generation: 7,
        }
    }

    fn inspect(source: &[u8], index: u64, bytes: &[u8]) -> Result<N64SymCandidateEvidence, String> {
        inspect_n64sym_candidate(
            source,
            &sha256(source),
            N64SYM_REVISION,
            index,
            address(),
            bytes,
        )
    }

    #[test]
    fn exact_pinned_identical_body_labels_remain_candidates() {
        let alpha_source = b"# sig_v1\nalpha 0x000C 0x076D7C20 0x92AA615F\n";
        let beta_source = b"# sig_v1\nbeta 0x000C 0x076D7C20 0x92AA615F\n";
        let alpha = inspect(alpha_source, 0, ALPHA).unwrap();
        let beta = inspect(beta_source, 0, ALPHA).unwrap();

        assert_eq!(alpha.reported_name(), "alpha");
        assert_eq!(beta.reported_name(), "beta");
        assert_eq!(alpha.key(), beta.key());
        assert_eq!(alpha.matched_bytes_sha256(), beta.matched_bytes_sha256());
        assert!(alpha.candidate_only() && beta.candidate_only());

        let serialized = serde_json::to_value(&alpha).unwrap();
        for field in [
            "unique_symbol_identity_certified",
            "exact_executable_byte_identity_certified",
            "reachability_certified",
            "byte_provenance_certified",
            "immutability_certified",
            "executable_lifetime_certified",
            "indirect_target_set_exhaustive",
            "closed_world_certified",
            "native_complete",
        ] {
            assert_eq!(serialized[field], false, "{field} must remain fail-closed");
        }
    }

    #[test]
    fn exact_pinned_target26_normalization_matches_byte_distinct_variants() {
        let source =
            b"# sig_v1\ngamma 0x0010 0x328DCA26 0xF6C672A8\n .targ26 external_target 0x000\n";
        let mut relocated = GAMMA.to_vec();
        relocated[..4].copy_from_slice(&0x0c12_3456u32.to_be_bytes());

        let original = inspect(source, 0, GAMMA).unwrap();
        let variant = inspect(source, 0, &relocated).unwrap();
        assert_ne!(
            original.matched_bytes_sha256(),
            variant.matched_bytes_sha256()
        );
        assert_eq!(
            original.normalized_bytes_sha256(),
            variant.normalized_bytes_sha256()
        );
        assert!(original.relocation_normalized());
        assert_eq!(
            original.relocations()[0].kind(),
            N64SymRelocationKind::Target26
        );
        assert_eq!(original.relocations()[0].offset(), 0);
        assert_eq!(original.relocations()[0].symbol(), "external_target");

        let mut nonreloc = GAMMA.to_vec();
        nonreloc[4] ^= 1;
        assert!(inspect(source, 0, &nonreloc).is_err());
    }

    #[test]
    fn source_order_and_visible_ambiguity_are_retained() {
        let source = b"alpha 0x000C 0x076D7C20 0x92AA615F\nbeta 0x000C 0x076D7C20 0x92AA615F\n";
        let first = inspect(source, 0, ALPHA).unwrap();
        let second = inspect(source, 1, ALPHA).unwrap();
        assert_eq!(first.reported_name(), "alpha");
        assert_eq!(second.reported_name(), "beta");
        assert_eq!(first.same_key_entries(), 2);
        assert_eq!(first.same_crc_b_entries(), 2);
        assert_eq!(second.signature_index(), 1);
    }

    #[test]
    fn source_receipt_revision_span_and_relocations_fail_closed() {
        let source = b"alpha 0x000C 0x076D7C20 0x92AA615F\n";
        assert!(
            inspect_n64sym_candidate(
                source,
                &"0".repeat(64),
                N64SYM_REVISION,
                0,
                address(),
                ALPHA,
            )
            .is_err()
        );
        assert!(
            inspect_n64sym_candidate(
                source,
                &sha256(source),
                "different-revision",
                0,
                address(),
                ALPHA,
            )
            .is_err()
        );
        assert!(inspect(source, 1, ALPHA).is_err());
        assert!(inspect(source, 0, &ALPHA[..8]).is_err());

        let unaligned = b"gamma 0x0010 0x328DCA26 0xF6C672A8\n.targ26 target 2\n";
        let duplicate = b"gamma 0x0010 0x328DCA26 0xF6C672A8\n.targ26 target 0 0\n";
        let out_of_range = b"gamma 0x0010 0x328DCA26 0xF6C672A8\n.targ26 target 16\n";
        assert!(inspect(unaligned, 0, GAMMA).is_err());
        assert!(inspect(duplicate, 0, GAMMA).is_err());
        assert!(inspect(out_of_range, 0, GAMMA).is_err());
    }

    #[test]
    fn forged_or_deleted_candidate_report_is_rejected_by_replay() {
        let source = b"alpha 0x000C 0x076D7C20 0x92AA615F\n";
        let report = inspect(source, 0, ALPHA).unwrap();
        verify_n64sym_candidate(
            &report,
            source,
            &sha256(source),
            N64SYM_REVISION,
            0,
            address(),
            ALPHA,
        )
        .unwrap();

        let mut forged = report.clone();
        forged.reported_name = "beta".into();
        assert!(
            verify_n64sym_candidate(
                &forged,
                source,
                &sha256(source),
                N64SYM_REVISION,
                0,
                address(),
                ALPHA,
            )
            .is_err()
        );

        let deleted = b"# sig_v1\n";
        assert!(inspect(deleted, 0, ALPHA).is_err());
    }

    #[test]
    fn crc_contract_matches_validated_exact_pin_vectors() {
        assert_eq!(crc32(&ALPHA[..8]), 0x076d_7c20);
        assert_eq!(crc32(ALPHA), 0x92aa_615f);
        assert_eq!(crc32(&GAMMA[..8]), 0x328d_ca26);
        assert_eq!(crc32(GAMMA), 0xf6c6_72a8);
        assert_eq!(
            sha256(GAMMA),
            "0a182d4da2341f510213a00ae11f3398f138c25985f28c503f649c33ef3d9430"
        );
    }
}
