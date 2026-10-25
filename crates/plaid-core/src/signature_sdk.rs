//! Relocation-aware identities for a reviewed, differently compiled SDK family.
//! Only metadata is retained; no SDK instruction bodies or game addresses.
use super::{CodeImage, GuestAddr, Identification, Match, combine, jump_target};
use crate::rom::sha256;
use std::collections::{BTreeMap, BTreeSet};

struct Profile {
    name: &'static str,
    size: u32,
    first: u32,
    digest: &'static str,
    references: &'static [(&'static str, u32, u32)],
    calls: &'static [(u32, &'static str)],
}

fn body(
    image: &CodeImage,
    entry: GuestAddr,
    profile: &Profile,
) -> Option<BTreeMap<String, GuestAddr>> {
    let end = entry.0.checked_add(profile.size)?;
    // shortcut: fixed SDK text only; slot SDKs need linked-address and table
    // identity verification before these profiles can certify their bindings.
    if image
        .slots
        .iter()
        .any(|(range, _, _)| range.start.0 < end && range.end() > u64::from(entry.0))
    {
        return None;
    }
    let mut words: Vec<_> = (0..profile.size)
        .step_by(4)
        .map(|o| image.instruction_word(GuestAddr(entry.0.checked_add(o)?)))
        .collect::<Option<_>>()?;
    let mut data = BTreeMap::new();
    for &(symbol, high, low) in profile.references {
        let (h, l) = (
            *words.get(high as usize / 4)?,
            *words.get(low as usize / 4)?,
        );
        let address = if l >> 26 == 13 {
            (h << 16) | (l & 0xffff)
        } else {
            (h << 16).wrapping_add(l as i16 as u32)
        };
        if !(0x8000_0000..0xc000_0000).contains(&address) || address % 4 != 0 {
            return None;
        }
        if data
            .insert(symbol.to_string(), GuestAddr(address))
            .is_some_and(|old| old.0 != address)
        {
            return None;
        }
    }
    for (index, word) in words.iter_mut().enumerate() {
        if matches!(*word >> 26, 2 | 3) {
            let target =
                ((entry.0 + index as u32 * 4 + 4) & 0xf000_0000) | (*word & 0x03ff_ffff) << 2;
            if (target < entry.0 || target - entry.0 >= profile.size)
                && !profile
                    .calls
                    .iter()
                    .any(|&(offset, _)| offset == index as u32 * 4)
            {
                return None;
            }
            // Internal absolute jumps retain their exact function-relative edge.
            *word = (*word & 0xfc00_0000)
                | if target >= entry.0 && target - entry.0 < profile.size {
                    (target - entry.0) / 4
                } else {
                    0
                };
        }
    }
    for &(_, h, l) in profile.references {
        words[h as usize / 4] &= 0xffff_0000;
        words[l as usize / 4] &= 0xffff_0000;
    }
    let bytes: Vec<_> = words.iter().flat_map(|word| word.to_be_bytes()).collect();
    (sha256(&bytes) == profile.digest).then_some(data)
}

struct Candidate<'a> {
    entry: GuestAddr,
    profile: &'a Profile,
    data: BTreeMap<String, GuestAddr>,
}

fn identify(image: &CodeImage, profiles: &[Profile]) -> Identification {
    let mut candidates = Vec::new();
    for (index, word) in image.words.iter().enumerate() {
        for profile in profiles.iter().filter(|p| {
            let mask = if p.references.iter().any(|&(_, h, l)| h == 0 || l == 0) {
                0xffff_0000
            } else if p.calls.iter().any(|&(offset, _)| offset == 0) {
                0xfc00_0000
            } else {
                u32::MAX
            };
            p.first == *word & mask
        }) {
            let Some(entry) = u32::try_from(index)
                .ok()
                .and_then(|i| i.checked_mul(4))
                .and_then(|o| image.base.pc.0.checked_add(o))
                .map(GuestAddr)
            else {
                continue;
            };
            if let Some(data) = body(image, entry, profile) {
                candidates.push(Candidate {
                    entry,
                    profile,
                    data,
                });
            }
        }
    }
    let scope = |entry: GuestAddr| {
        image
            .holes
            .iter()
            .filter(|h| h.end() <= u64::from(entry.0))
            .count()
    };
    // A masked relocation must still resolve to its verified peer/global. Drop
    // broken dependencies to a fixed point, including mutually recursive peers.
    let mut dependencies_stable = false;
    loop {
        let mut names: BTreeMap<_, BTreeSet<_>> = BTreeMap::new();
        let mut globals: BTreeMap<_, BTreeSet<_>> = BTreeMap::new();
        let mut entries: BTreeMap<_, BTreeSet<_>> = BTreeMap::new();
        let mut aliases: BTreeMap<_, BTreeSet<_>> = BTreeMap::new();
        for c in &candidates {
            names
                .entry((scope(c.entry), c.profile.name))
                .or_default()
                .insert(c.entry);
            entries.entry(c.entry).or_default().insert(c.profile.name);
            for (name, address) in &c.data {
                globals
                    .entry((scope(c.entry), name.as_str()))
                    .or_default()
                    .insert(*address);
                aliases
                    .entry((scope(c.entry), *address))
                    .or_default()
                    .insert(name.as_str());
            }
        }
        let accepted: Vec<_> = candidates
            .iter()
            .filter(|c| {
                (!dependencies_stable
                    || (names[&(scope(c.entry), c.profile.name)].len() == 1
                        && entries[&c.entry].len() == 1))
                    && c.profile.calls.iter().all(|&(offset, name)| {
                        jump_target(image, c.entry.0 + offset).is_some_and(|target| {
                            candidates
                                .iter()
                                .any(|peer| peer.entry.0 == target && peer.profile.name == name)
                        })
                    })
                    && c.data.iter().all(|(name, address)| {
                        (!dependencies_stable
                            || (globals[&(scope(c.entry), name.as_str())].len() == 1
                                && aliases[&(scope(c.entry), *address)].len() == 1))
                            && if name == "__osCleanupThread" {
                                candidates
                                    .iter()
                                    .any(|peer| peer.entry == *address && peer.profile.name == name)
                            } else if name == "__osRcpImTable" {
                                (0..64).all(|mask| {
                                    let expected: u32 = (0..6)
                                        .map(|bit| {
                                            (if mask & (1 << bit) == 0 { 1 } else { 2 })
                                                << (2 * bit)
                                        })
                                        .sum();
                                    image.word(GuestAddr(address.0 + mask / 2 * 4)).is_some_and(
                                        |word| {
                                            (if mask % 2 == 0 {
                                                word >> 16
                                            } else {
                                                word & 0xffff
                                            }) == expected
                                        },
                                    )
                                })
                            } else {
                                true
                            }
                    })
            })
            .map(|c| c.entry)
            .collect();
        if accepted.len() == candidates.len() {
            if dependencies_stable {
                break;
            }
            dependencies_stable = true;
            continue;
        }
        candidates.retain(|c| accepted.contains(&c.entry));
        dependencies_stable = false;
    }
    let mut out = Identification::default();
    for c in candidates {
        out.data_bindings.insert(c.entry, c.data);
        out.matches.push(Match {
            entry: c.entry,
            name: c.profile.name.into(),
            size: c.profile.size,
        });
    }
    out
}

pub(super) fn merge(image: &CodeImage, out: &mut Identification, wanted: &BTreeSet<&str>) {
    let mut sdk = identify(image, PROFILES);
    sdk.matches.retain(|m| wanted.contains(m.name.as_str()));
    sdk.data_bindings
        .retain(|entry, _| sdk.matches.iter().any(|m| m.entry == *entry));
    *out = combine(std::mem::take(out), sdk);
}

pub(super) fn supported_status(image: &CodeImage, m: &Match) -> bool {
    matches!(m.name.as_str(), "osCreateThread" | "osSetIntMask")
        && PROFILES
            .iter()
            .any(|p| p.name == m.name && p.size == m.size && body(image, m.entry, p).is_some())
}

// Relocation-normalized metadata only; reviewed SDK semantics: research/rs-thread-dispatch.md.
const PROFILES: &[Profile] = &[
    Profile {
        name: "osGetThreadPri",
        size: 0x18,
        first: 0x14800002,
        digest: "a9262fb71c174eb7879a272c6b371ed3a236bf61c73d4e051fa2f55a5d674e1a",
        references: &[("__osRunningThread", 0x4, 0x8)],
        calls: &[],
    },
    Profile {
        name: "osCreateThread",
        size: 0xd0,
        first: 0x27bdffe8,
        digest: "d0befc44ad66ee73e14463c4ab5767af170c489f369b03a56c74fa269270c4d1",
        references: &[
            ("__osCleanupThread", 0x14, 0x18),
            ("__osActiveQueue", 0xa8, 0xac),
            ("__osActiveQueue", 0xa8, 0xb0),
        ],
        calls: &[(0xa0, "__osDisableInt"), (0xb8, "__osRestoreInt")],
    },
    Profile {
        name: "osDestroyThread",
        size: 0xd4,
        first: 0x27bdffe0,
        digest: "d57d92bd738eebf1e6a87cb0900f8530e52555a6f0cec22a770df2e0014f54ad",
        references: &[
            ("__osRunningThread", 0x20, 0x24),
            ("__osActiveQueue", 0x4c, 0x50),
            ("__osActiveQueue", 0x4c, 0x64),
            ("__osRunningThread", 0xa0, 0xa4),
            ("__osActiveQueue", 0x2c, 0x50),
            ("__osActiveQueue", 0x3c, 0x50),
        ],
        calls: &[
            (0x10, "__osDisableInt"),
            (0x44, "__osDequeueThread"),
            (0xb0, "__osDispatchThread"),
            (0xb8, "__osRestoreInt"),
        ],
    },
    Profile {
        name: "__osEnqueueAndYield",
        size: 0x108,
        first: 0x3c050000,
        digest: "c03479dcf6d914e85dc29744257e9a8c486293794982c129d28e0e44ae0617ac",
        references: &[
            ("__osRunningThread", 0x0, 0x4),
            ("__OSGlobalIntMask", 0x84, 0x88),
            ("__OSGlobalIntMask", 0xc4, 0xc8),
        ],
        calls: &[(0xf8, "__osEnqueueThread"), (0x100, "__osDispatchThread")],
    },
    Profile {
        name: "__osEnqueueThread",
        size: 0x4c,
        first: 0x0080c821,
        digest: "8f708d5dc76f4e54d1ffd2508dcc06c5764f27c1c76aa319a8588e645bf40985",
        references: &[],
        calls: &[],
    },
    Profile {
        name: "__osPopThread",
        size: 0x14,
        first: 0x8c820000,
        digest: "397c7e3ffdad1ac5762a6c3a69ac2364d58132ee248686ffcb7531a20e5239c0",
        references: &[],
        calls: &[],
    },
    Profile {
        name: "__osDispatchThread",
        size: 0x184,
        first: 0x3c040000,
        digest: "e9a76b6a8ef6b1ad50bedf44dac4b429f3ce1c5519bf7fe15a7f0743c0722787",
        references: &[
            ("__osRunQueue", 0x0, 0x4),
            ("__osRunningThread", 0x10, 0x14),
            ("__OSGlobalIntMask", 0x2c, 0x30),
            ("__OSGlobalIntMask", 0x13c, 0x140),
            ("__osRcpImTable", 0x154, 0x158),
        ],
        calls: &[(0x8, "__osPopThread")],
    },
    Profile {
        name: "__osCleanupThread",
        size: 0x8,
        first: 0x0c000000,
        digest: "231755490db2bd2d49180f9aa7b083d71e42190de45f496a1706b816e20ad277",
        references: &[],
        calls: &[(0x0, "osDestroyThread")],
    },
    Profile {
        name: "__osDisableInt",
        size: 0x24,
        first: 0x40086000,
        digest: "29634706c815fc9b66b46b589cf3d78834cd1a4e141f9a0cccfa5494705ef9a9",
        references: &[],
        calls: &[],
    },
    Profile {
        name: "__osRestoreInt",
        size: 0x1c,
        first: 0x40086000,
        digest: "b6f58a0412d63a52440645623c5a49320459a39befc7ea4359a374051eceb105",
        references: &[],
        calls: &[],
    },
    Profile {
        name: "osRecvMesg",
        size: 0x128,
        first: 0x27bdffd0,
        digest: "9ac23e85c1a305cd054a247a4154a7312d39d090086f0c58d889fcf6d9006949",
        references: &[("__osRunningThread", 0x3c, 0x5c)],
        calls: &[
            (0x28, "__osDisableInt"),
            (0x4c, "__osRestoreInt"),
            (0x60, "__osEnqueueAndYield"),
            (0xec, "__osPopThread"),
            (0xf4, "osStartThread"),
            (0xfc, "__osRestoreInt"),
        ],
    },
    Profile {
        name: "osSendMesg",
        size: 0x138,
        first: 0x27bdffd0,
        digest: "e3be991b388a27b1b5a3f6bccf595c6b02addbf5f9b5ba2e293b824f837aba3c",
        references: &[("__osRunningThread", 0x4c, 0x6c)],
        calls: &[
            (0x2c, "__osDisableInt"),
            (0x5c, "__osRestoreInt"),
            (0x70, "__osEnqueueAndYield"),
            (0xf4, "__osPopThread"),
            (0xfc, "osStartThread"),
            (0x104, "__osRestoreInt"),
        ],
    },
    Profile {
        name: "osSetIntMask",
        size: 0xac,
        first: 0x400c6000,
        digest: "a1da770766688a5b3e84da4e5f8ddbf0ff0f9c7af2b4be367e211a6c1b439361",
        references: &[
            ("__OSGlobalIntMask", 0x8, 0xc),
            ("__osRcpImTable", 0x60, 0x64),
        ],
        calls: &[],
    },
    Profile {
        name: "osSetThreadPri",
        size: 0xc0,
        first: 0x27bdffe0,
        digest: "1b24506f19502850cdc4868d78010ce5b95f55bae3c3bc8efa2d866433939396",
        references: &[
            ("__osRunningThread", 0x28, 0x2c),
            ("__osRunningThread", 0x38, 0x3c),
            ("__osRunningThread", 0x70, 0x78),
            ("__osRunQueue", 0x74, 0x7c),
            ("__osRunQueue", 0x74, 0x90),
            ("__osRunningThread", 0x54, 0x78),
        ],
        calls: &[
            (0x18, "__osDisableInt"),
            (0x5c, "__osDequeueThread"),
            (0x68, "__osEnqueueThread"),
            (0x98, "__osEnqueueAndYield"),
            (0xa0, "__osRestoreInt"),
        ],
    },
    Profile {
        name: "osStartThread",
        size: 0x110,
        first: 0x27bdffe0,
        digest: "14c3879bdc8c4dc5ea25d27b56ce337e78a4f744a579cf880160b2189cd8d672",
        references: &[
            ("__osRunQueue", 0x40, 0x44),
            ("__osRunQueue", 0x58, 0x5c),
            ("__osRunQueue", 0x70, 0x74),
            ("__osRunningThread", 0xac, 0xb0),
            ("__osRunQueue", 0xb8, 0xcc),
            ("__osRunningThread", 0x34, 0xb0),
            ("__osRunQueue", 0xb8, 0xe0),
        ],
        calls: &[
            (0x14, "__osDisableInt"),
            (0x88, "__osEnqueueThread"),
            (0x94, "__osPopThread"),
            (0xa4, "__osEnqueueThread"),
            (0xbc, "__osDispatchThread"),
            (0xe8, "__osEnqueueAndYield"),
            (0xf0, "__osRestoreInt"),
        ],
    },
    Profile {
        name: "osStopThread",
        size: 0xb0,
        first: 0x27bdffe0,
        digest: "3c3ea99374d9bee0525210563333b0c0af78bff926dd086c9118a28fda5a53a4",
        references: &[("__osRunningThread", 0x68, 0x6c)],
        calls: &[
            (0x10, "__osDisableInt"),
            (0x74, "__osEnqueueAndYield"),
            (0x8c, "__osDequeueThread"),
            (0x94, "__osRestoreInt"),
        ],
    },
    Profile {
        name: "__osDequeueThread",
        size: 0x34,
        first: 0x8c820000,
        digest: "a3d22597cb86bb7b7c54a1a587ad48ca405f55d1842cfaa70aed9e7793cbd877",
        references: &[],
        calls: &[],
    },
];

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::{CodeAddress, GuestRange};

    // Authored miniature call/branch/data graph, not an SDK body.
    const FIXTURES: &[Profile] = &[
        Profile {
            name: "fixture_caller",
            size: 48,
            first: 0x3c08_0000,
            digest: "003aea8c3f14057905033eb1dee925bf0a2be30bf6dc247b0b2198a8c8f1ab3b",
            references: &[("__OSGlobalIntMask", 0, 4), ("__osRcpImTable", 12, 16)],
            calls: &[(20, "fixture_peer")],
        },
        Profile {
            name: "fixture_peer",
            size: 12,
            first: 0x4002_6000,
            digest: "2ea7fc1f266eee7e59be3d8ffee2aebda5c74a4e6765e268c725a9a6a9f50ddf",
            references: &[],
            calls: &[],
        },
        Profile {
            name: "fixture_thunk",
            size: 8,
            first: 0x0c00_0000,
            digest: "231755490db2bd2d49180f9aa7b083d71e42190de45f496a1706b816e20ad277",
            references: &[],
            calls: &[(0, "fixture_peer")],
        },
    ];

    fn fixture(base: u32, data: u32) -> CodeImage {
        let mut words = vec![0; 128];
        words[..12].copy_from_slice(&[
            0x3c08_0000 | data.wrapping_add(0x8000) >> 16,
            0x2508_0000 | data & 0xffff,
            0x8d09_0000,
            0x3c0a_0000 | (base + 256) >> 16,
            0x354a_0000 | (base + 256) & 0xffff,
            0x0c00_0000 | ((base + 64) >> 2) & 0x03ff_ffff,
            0,
            0x0800_0000 | ((base + 40) >> 2) & 0x03ff_ffff,
            0,
            0xad09_0004,
            0x03e0_0008,
            0,
        ]);
        words[16..19].copy_from_slice(&[0x4002_6000, 0x03e0_0008, 0]);
        for mask in 0..64 {
            let command: u32 = (0..6)
                .map(|bit| (if mask & (1 << bit) == 0 { 1 } else { 2 }) << (2 * bit))
                .sum();
            words[64 + mask / 2] |= command << (if mask % 2 == 0 { 16 } else { 0 });
        }
        CodeImage {
            base: CodeAddress {
                pc: GuestAddr(base),
                image: "authored".into(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        }
    }

    fn has_caller(image: &CodeImage) -> bool {
        identify(image, FIXTURES)
            .matches
            .iter()
            .any(|m| m.name == "fixture_caller")
    }

    #[test]
    fn relocated_bodies_retain_internal_edges_and_verified_peer_calls() {
        for (base, data) in [(0x8000_0400, 0x8000_1000), (0x8050_0000, 0x8040_fff0)] {
            let mut image = fixture(base, data);
            assert!(has_caller(&image));
            assert_eq!(
                identify(&image, FIXTURES).data_bindings[&GuestAddr(base)]["__OSGlobalIntMask"],
                GuestAddr(data)
            );
            // The masked call immediate is still constrained to its exact peer.
            image.words[5] += 1;
            assert!(!has_caller(&image));
            image = fixture(base, data);
            image.words[7] += 1;
            assert!(!has_caller(&image));
            image = fixture(base, data);
            image.words[16] ^= 1;
            assert!(!has_caller(&image));
        }
    }

    #[test]
    fn every_body_word_and_table_entry_is_authenticated() {
        for index in 0..12 {
            let mut image = fixture(0x8000_0400, 0x8000_1000);
            // Non-relocated bits in every instruction, including delay slots.
            image.words[index] ^= 1 << 16;
            assert!(!has_caller(&image), "word {index}");
        }
        for index in 64..96 {
            for bit in [1, 1 << 16] {
                let mut image = fixture(0x8000_0400, 0x8000_1000);
                image.words[index] ^= bit;
                assert!(!has_caller(&image));
            }
        }
    }

    #[test]
    fn duplicate_peers_gaps_slots_and_truncation_refuse() {
        let mut image = fixture(0x8000_0400, 0x8000_1000);
        image.words[20..23].copy_from_slice(&[0x4002_6000, 0x03e0_0008, 0]);
        assert!(!has_caller(&image));
        image = fixture(0x8000_0400, 0x8000_1000);
        image.holes.push(GuestRange {
            start: GuestAddr(0x8000_0418),
            size: 4,
        });
        assert!(!has_caller(&image));
        image = fixture(0x8000_0400, 0x8000_1000);
        image.slots.push((
            GuestRange {
                start: GuestAddr(0x8000_0400),
                size: 48,
            },
            0x8000_0400,
            48,
        ));
        assert!(!has_caller(&image));
        image = fixture(0x8000_0400, 0x8000_1000);
        image.words.truncate(11);
        assert!(!has_caller(&image));
    }

    #[test]
    fn call_first_thunks_resolve_dependencies_before_ambiguity() {
        let mut image = fixture(0x8000_0400, 0x8000_1000);
        image.words[24..26].copy_from_slice(&[0x0c00_0110, 0x0000_2021]);
        image.words[28..30].copy_from_slice(&[0x0c00_010f, 0x0000_2021]);
        let out = identify(&image, FIXTURES);
        assert!(
            out.matches
                .iter()
                .any(|m| m.name == "fixture_thunk" && m.entry == GuestAddr(0x8000_0460))
        );
        assert!(has_caller(&image));
        image.words[28] = image.words[24];
        assert!(
            !identify(&image, FIXTURES)
                .matches
                .iter()
                .any(|m| m.name == "fixture_thunk")
        );
    }

    #[test]
    fn distinct_sdk_globals_cannot_alias() {
        assert!(!has_caller(&fixture(0x8000_0400, 0x8000_0500)));
    }
}
