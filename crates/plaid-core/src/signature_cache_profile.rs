use super::{CodeImage, Identification, Match};
use crate::{GuestAddr, rom::sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap};

// Exact full-body identities for reviewed libultra CACHE routines. The source
// words remain in the ROM; only size, first-word prefilter, and SHA-256 are
// retained here. The full-body digest is required after the cheap prefilter.
const PROFILES: &[Profile] = &[
    Profile {
        name: "osInvalDCache",
        size: 0xb0,
        first_word: 0x18a0_0020,
        sha256: "8ae1ab78f7b451eff125bd297f76cbcc5f2e3c7a54c6c1497d3f3c0b281f886f",
    },
    Profile {
        name: "osInvalDCache",
        size: 0xb0,
        first_word: 0x18a0_001f,
        sha256: "7ea4c6bffed307fe915ab8ef0ae37d86482e17b132eb99598f82ad5cbca40a71",
    },
    Profile {
        name: "osInvalICache",
        size: 0x74,
        first_word: 0x18a0_0011,
        sha256: "b868489aa115fdc2f51ebae88065f21a34d22bfd3e4c0f14ab431fe181859810",
    },
    Profile {
        name: "osInvalICache",
        size: 0x74,
        first_word: 0x18a0_0011,
        sha256: "713e7b78373df6fbf3d030b5237e9c1e2148c9443cbfdf938f2e8ffdf8e2d326",
    },
    Profile {
        name: "osWritebackDCache",
        size: 0x74,
        first_word: 0x18a0_0011,
        sha256: "1f0c92717c0320c652883aff97a82af6fc935d0aba9eab058253f183113ec924",
    },
    Profile {
        name: "osWritebackDCache",
        size: 0x74,
        first_word: 0x18a0_0011,
        sha256: "5306341d7122fdbbae63d48917c76f7f6c2ee0321e490862302581561bf0474c",
    },
];

struct Profile<'a> {
    name: &'static str,
    /// Verified code extent, including the terminal delay slot.
    size: u32,
    first_word: u32,
    sha256: &'a str,
}

fn body_sha256(image: &CodeImage, entry: GuestAddr, size: u32) -> Option<String> {
    if size == 0 || !size.is_multiple_of(4) {
        return None;
    }
    let mut bytes = Vec::with_capacity(size as usize);
    for offset in (0..size).step_by(4) {
        bytes.extend_from_slice(
            &image
                .instruction_word(GuestAddr(entry.0.checked_add(offset)?))?
                .to_be_bytes(),
        );
    }
    Some(sha256(&bytes))
}

fn matches_profile(image: &CodeImage, entry: GuestAddr, profile: &Profile<'_>) -> bool {
    image.instruction_word(entry) == Some(profile.first_word)
        && body_sha256(image, entry, profile.size).as_deref() == Some(profile.sha256)
}

fn candidates(image: &CodeImage, profiles: &[Profile<'_>], wanted: &BTreeSet<&str>) -> Vec<Match> {
    let mut by_first_word: HashMap<u32, Vec<&Profile>> = HashMap::new();
    for profile in profiles.iter().filter(|p| wanted.contains(p.name)) {
        by_first_word
            .entry(profile.first_word)
            .or_default()
            .push(profile);
    }
    let mut result = Vec::new();
    for (index, first_word) in image.words.iter().enumerate() {
        let Some(profiles) = by_first_word.get(first_word) else {
            continue;
        };
        let Some(offset) = u32::try_from(index)
            .ok()
            .and_then(|index| index.checked_mul(4))
        else {
            continue;
        };
        let Some(entry) = image.base.pc.0.checked_add(offset).map(GuestAddr) else {
            continue;
        };
        for profile in profiles {
            if matches_profile(image, entry, profile) {
                result.push(Match {
                    entry,
                    name: profile.name.into(),
                    size: profile.size,
                });
            }
        }
    }
    result
}

pub(super) fn merge(image: &CodeImage, out: &mut Identification, wanted: &BTreeSet<&str>) {
    merge_candidates(out, candidates(image, PROFILES, wanted));
}

fn merge_candidates(out: &mut Identification, candidates: Vec<Match>) {
    let superseded: BTreeSet<_> = candidates
        .iter()
        .flat_map(|candidate| {
            out.matches
                .iter()
                .filter(move |existing| {
                    existing.entry == candidate.entry
                        && existing.name == candidate.name
                        && existing.size != candidate.size
                })
                .cloned()
        })
        .collect();
    out.matches.retain(|m| !superseded.contains(m));
    let mut by_entry: BTreeMap<GuestAddr, BTreeSet<(String, u32)>> = BTreeMap::new();
    for m in out.matches.iter().chain(candidates.iter()) {
        by_entry
            .entry(m.entry)
            .or_default()
            .insert((m.name.clone(), m.size));
    }
    let conflicts: BTreeSet<_> = by_entry
        .into_iter()
        .filter_map(|(entry, identities)| (identities.len() > 1).then_some(entry))
        .collect();
    let conflicting_names: BTreeSet<_> = out
        .matches
        .iter()
        .chain(candidates.iter())
        .filter(|m| conflicts.contains(&m.entry))
        .map(|m| m.name.clone())
        .collect();
    out.ambiguous.extend(conflicting_names);
    let mut matches: BTreeSet<_> = out.matches.iter().cloned().collect();
    matches.extend(
        candidates
            .into_iter()
            .filter(|m| !out.ambiguous.contains(&m.name)),
    );
    matches.retain(|m| !conflicts.contains(&m.entry));
    out.matches = matches.into_iter().collect();
    out.matches.sort();
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::{CodeAddress, GuestRange};

    fn image(words: &[u32], base: u32) -> CodeImage {
        CodeImage {
            base: CodeAddress {
                pc: GuestAddr(base),
                image: "00".repeat(32),
                generation: 0,
            },
            words: words.to_vec(),
            rom_offset: None,
            physical_start: None,
            holes: Vec::<GuestRange>::new(),
            slots: Vec::new(),
        }
    }

    fn synthetic_profile<'a>(words: &[u32], digest: &'a str) -> Profile<'a> {
        let bytes: Vec<u8> = words.iter().flat_map(|word| word.to_be_bytes()).collect();
        Profile {
            name: "synthetic-cache-contract",
            size: bytes.len() as u32,
            first_word: words[0],
            sha256: digest,
        }
    }

    fn synthetic_cache_words() -> [u32; 5] {
        let cache_hit_writeback = (0x2f << 26) | (8 << 21) | (25 << 16);
        [0x18a0_0011, 0, cache_hit_writeback, 0x03e0_0008, 0]
    }

    #[test]
    fn full_body_digest_accepts_address_shifted_synthetic_fixture() {
        // Authored instruction-shaped data, not copied ROM or SDK bytes.
        let words = synthetic_cache_words();
        let bytes: Vec<u8> = words.iter().flat_map(|word| word.to_be_bytes()).collect();
        let digest = sha256(&bytes);
        let profile = synthetic_profile(&words, &digest);
        let image = image(&words, 0x8123_4000);
        assert!(matches_profile(&image, GuestAddr(0x8123_4000), &profile));
        assert!(!matches_profile(&image, GuestAddr(0x8123_4004), &profile));
    }

    #[test]
    fn full_body_digest_rejects_each_mutation_and_truncation() {
        let words = synthetic_cache_words();
        let bytes: Vec<u8> = words.iter().flat_map(|word| word.to_be_bytes()).collect();
        let digest = sha256(&bytes);
        let profile = synthetic_profile(&words, &digest);
        for index in 0..words.len() {
            let mut changed = words;
            changed[index] ^= 1;
            let image = image(&changed, 0x8000_0400);
            assert!(!matches_profile(&image, GuestAddr(0x8000_0400), &profile));
        }
        let mut changed_delay = words;
        changed_delay[words.len() - 1] = 1;
        assert!(!matches_profile(
            &image(&changed_delay, 0x8000_0400),
            GuestAddr(0x8000_0400),
            &profile
        ));
        let image = image(&words[..words.len() - 1], 0x8000_0400);
        assert!(!matches_profile(&image, GuestAddr(0x8000_0400), &profile));
    }

    #[test]
    fn relocation_free_profile_copies_are_preserved() {
        let words = synthetic_cache_words();
        let bytes: Vec<u8> = words.iter().flat_map(|word| word.to_be_bytes()).collect();
        let digest = sha256(&bytes);
        let profile = synthetic_profile(&words, &digest);
        let profiles = [profile];
        let fixture = image(
            &[
                words[0], words[1], words[2], words[3], words[4], words[0], words[1], words[2],
                words[3], words[4],
            ],
            0x8000_0400,
        );
        let found = candidates(&fixture, &profiles, &["synthetic-cache-contract"].into());
        assert_eq!(found.len(), 2);
        let mut identified = Identification::default();
        merge_candidates(&mut identified, found);
        assert_eq!(identified.matches.len(), 2);
        assert!(identified.ambiguous.is_empty());
    }

    #[test]
    fn profile_collision_with_another_name_is_ambiguous() {
        let entry = GuestAddr(0x8000_0400);
        let mut identified = Identification {
            matches: vec![Match {
                entry,
                name: "osWritebackDCache".into(),
                size: 0x74,
            }],
            ..Identification::default()
        };
        merge_candidates(
            &mut identified,
            vec![Match {
                entry,
                name: "osInvalICache".into(),
                size: 0x74,
            }],
        );
        assert!(identified.matches.is_empty());
        assert!(identified.ambiguous.contains("osWritebackDCache"));
        assert!(identified.ambiguous.contains("osInvalICache"));
    }

    #[test]
    fn verified_extent_replaces_same_entry_narrow_signature_extent() {
        let entry = GuestAddr(0x8000_0400);
        let mut identified = Identification {
            matches: vec![Match {
                entry,
                name: "osInvalDCache".into(),
                size: 0xac,
            }],
            ..Identification::default()
        };
        merge_candidates(
            &mut identified,
            vec![Match {
                entry,
                name: "osInvalDCache".into(),
                size: 0xb0,
            }],
        );
        assert_eq!(identified.matches.len(), 1);
        assert_eq!(identified.matches[0].size, 0xb0);
        assert!(identified.ambiguous.is_empty());
    }

    #[test]
    fn only_requested_names_supply_candidates() {
        let words = [0x18a0_0011u32, 0, 0x240b_2000, 0x03e0_0008];
        let bytes: Vec<u8> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
        let digest = sha256(&bytes);
        let profiles = [synthetic_profile(&words, &digest)];
        let fixture = image(&words, 0x8000_0400);
        assert!(candidates(&fixture, &profiles, &BTreeSet::new()).is_empty());
        assert!(candidates(&fixture, &profiles, &["osGetCount"].into()).is_empty());
        assert_eq!(
            candidates(&fixture, &profiles, &["synthetic-cache-contract"].into()).len(),
            1
        );
    }
}
