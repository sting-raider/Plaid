//! External expectations for complete discovery-trace sources.
//!
//! A manifest is useful only when it is preserved outside the editable
//! `ProgramMap` under a stronger trust boundary. Regenerating a manifest from a
//! modified trace or map does not provide deletion resistance.
//!
//! Discovery traces already have a canonical typed NDJSON representation and a
//! complete-source projection rechecker. For that source-available case the
//! canonical source digest is stronger and smaller than inventing a second
//! semantic-root algorithm: it commits to the header, contiguous event identities,
//! typed event semantics, order, and terminal count. The manifest set preserves
//! the exact expected source/session set across later map merges.

use crate::{
    program::{ProgramMap, RomIdentity},
    rom::sha256,
    trace::DiscoveryTrace,
    trace_projection::verify_discovery_trace_projection,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const DISCOVERY_TRACE_MANIFEST_FORMAT: &str = "plaid-discovery-trace-manifest-v0";
pub const DISCOVERY_TRACE_MANIFEST_SET_FORMAT: &str = "plaid-discovery-trace-manifest-set-v0";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DiscoveryTraceManifest {
    pub format: String,
    /// SHA-256 of `DiscoveryTrace::to_ndjson()`. This is the same source/session
    /// identity used by discovery-trace evidence IDs during import.
    pub source_sha256: String,
    pub rom: RomIdentity,
    pub engine: String,
    pub revision: String,
    pub event_count: u64,
}

impl DiscoveryTraceManifest {
    /// Create the expectation at a trusted source/import boundary.
    ///
    /// Calling this after an untrusted edit merely commits to the edited source;
    /// callers that need deletion resistance must persist the returned value
    /// independently of the later editable map/source artifact.
    pub fn from_trace(trace: &DiscoveryTrace) -> Result<Self, String> {
        trace.validate()?;
        let canonical = trace.to_ndjson()?;
        let manifest = Self {
            format: DISCOVERY_TRACE_MANIFEST_FORMAT.into(),
            source_sha256: sha256(canonical.as_bytes()),
            rom: trace.header.rom.clone(),
            engine: trace.header.engine.clone(),
            revision: trace.header.revision.clone(),
            event_count: trace.events.len() as u64,
        };
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.format != DISCOVERY_TRACE_MANIFEST_FORMAT {
            return Err("unsupported discovery-trace manifest format".into());
        }
        if !valid_sha256(&self.source_sha256) {
            return Err("invalid discovery-trace source SHA-256".into());
        }
        self.rom.validate()?;
        if self.engine.is_empty() || self.revision.is_empty() {
            return Err("discovery-trace manifest is missing producer identity".into());
        }
        Ok(())
    }

    /// Recompute the canonical complete source and require exact expectation
    /// equality. Equal payloads or producer labels cannot substitute for a
    /// different source/session identity.
    pub fn verify_trace(&self, trace: &DiscoveryTrace) -> Result<(), String> {
        self.validate()?;
        let actual = Self::from_trace(trace)?;
        if self != &actual {
            return Err("discovery trace does not match external expected manifest".into());
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DiscoveryTraceManifestSet {
    pub format: String,
    /// Keyed by canonical source/session SHA-256. BTreeMap keeps serialization
    /// deterministic and makes independent-session merge order irrelevant.
    #[serde(deserialize_with = "deserialize_sessions")]
    pub sessions: BTreeMap<String, DiscoveryTraceManifest>,
}

fn deserialize_sessions<'de, D>(
    deserializer: D,
) -> Result<BTreeMap<String, DiscoveryTraceManifest>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    struct SessionsVisitor;

    impl<'de> serde::de::Visitor<'de> for SessionsVisitor {
        type Value = BTreeMap<String, DiscoveryTraceManifest>;

        fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            formatter.write_str("discovery-trace manifests with unique session keys")
        }

        fn visit_map<M>(self, mut input: M) -> Result<Self::Value, M::Error>
        where
            M: serde::de::MapAccess<'de>,
        {
            let mut sessions = BTreeMap::new();
            while let Some((key, manifest)) =
                input.next_entry::<String, DiscoveryTraceManifest>()?
            {
                if sessions.insert(key, manifest).is_some() {
                    return Err(serde::de::Error::custom(
                        "duplicate discovery-trace manifest session key",
                    ));
                }
            }
            Ok(sessions)
        }
    }

    deserializer.deserialize_map(SessionsVisitor)
}

impl DiscoveryTraceManifestSet {
    pub fn empty() -> Self {
        Self {
            format: DISCOVERY_TRACE_MANIFEST_SET_FORMAT.into(),
            sessions: BTreeMap::new(),
        }
    }

    /// Build the exact expected set at the trusted boundary.
    /// Duplicate identical sources are rejected rather than silently collapsed.
    pub fn from_traces(traces: &[DiscoveryTrace]) -> Result<Self, String> {
        let mut out = Self::empty();
        for trace in traces {
            let manifest = DiscoveryTraceManifest::from_trace(trace)?;
            if out
                .sessions
                .insert(manifest.source_sha256.clone(), manifest)
                .is_some()
            {
                return Err("duplicate discovery-trace source in manifest set".into());
            }
        }
        out.validate()?;
        Ok(out)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.format != DISCOVERY_TRACE_MANIFEST_SET_FORMAT {
            return Err("unsupported discovery-trace manifest-set format".into());
        }
        for (session, manifest) in &self.sessions {
            manifest.validate()?;
            if session != &manifest.source_sha256 {
                return Err("discovery-trace manifest key/source mismatch".into());
            }
        }
        Ok(())
    }

    /// Compose independently preserved source expectations. Reusing one source
    /// identity with different metadata is a hard conflict; no merged global
    /// re-root is created.
    pub fn merge(&self, other: &Self) -> Result<Self, String> {
        self.validate()?;
        other.validate()?;
        let mut merged = self.clone();
        for (session, manifest) in &other.sessions {
            if let Some(existing) = merged.sessions.get(session) {
                if existing != manifest {
                    return Err("conflicting discovery-trace manifests for one source".into());
                }
            } else {
                merged.sessions.insert(session.clone(), manifest.clone());
            }
        }
        Ok(merged)
    }

    /// Verify the exact externally expected source/session set. Trace slice order
    /// is irrelevant; event chronology remains committed inside each canonical
    /// source digest.
    pub fn verify_traces(&self, traces: &[DiscoveryTrace]) -> Result<(), String> {
        self.validate()?;
        let actual = Self::from_traces(traces)?;
        if self != &actual {
            return Err("discovery-trace source set does not match external expectation".into());
        }
        Ok(())
    }

    /// Verify every expected complete source and then reuse Plaid's existing
    /// typed primitive projection rechecker against the retained `ProgramMap`.
    ///
    /// This detects deletion or semantic substitution of the currently modeled
    /// raw primitive trace facts, including deletion of an entire expected trace
    /// session. It does not claim trace-sensor completeness, authenticate other
    /// source domains, or replace the stronger entry/ROM-aware projection
    /// recheckers where their extra inputs are required.
    pub fn verify_primitive_projections(
        &self,
        map: &ProgramMap,
        traces: &[DiscoveryTrace],
    ) -> Result<(), String> {
        self.verify_traces(traces)?;
        map.validate()?;
        // A valid projection of the expected sources cannot authenticate an
        // additional imported discovery session hidden in the same map.
        for id in map.evidence.keys() {
            let Some(rest) = id.strip_prefix("trace:") else {
                continue;
            };
            let (session, sequence) = rest
                .split_once(':')
                .ok_or("malformed discovery-trace evidence identity")?;
            let manifest = self
                .sessions
                .get(session)
                .ok_or("ProgramMap contains an unexpected discovery-trace session")?;
            let ordinal = sequence
                .parse::<u64>()
                .map_err(|_| "malformed discovery-trace event sequence")?;
            if ordinal >= manifest.event_count || ordinal.to_string() != sequence {
                return Err("discovery-trace evidence sequence outside expected source".into());
            }
        }
        for trace in traces {
            verify_discovery_trace_projection(map, trace)?;
        }
        Ok(())
    }
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || matches!(byte, b'a'..=b'f'))
}
