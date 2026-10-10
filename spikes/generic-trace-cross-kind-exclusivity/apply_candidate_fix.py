from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
marker = "        let mut fetch_totals = BTreeMap::<&str, u64>::new();\n"
if "primitive trace event reused across incompatible event roles" in text:
    print("candidate already applied")
    raise SystemExit(0)
if text.count(marker) != 1:
    raise SystemExit(f"expected one insertion marker, found {text.count(marker)}")

insert = r'''        // Raw trace event IDs emitted for these primitive observations are operation
        // identities, not fungible annotations. Equivalent rows may accumulate
        // same-role event provenance, while explicit CompileBegin source-unit IDs
        // remain reusable context rather than executed-event identities.
        let mut primitive_trace_roles = BTreeMap::<String, &'static str>::new();
        let mut bind_trace_role =
            |evidence: &EvidenceRefs, source_unit: Option<&str>, role: &'static str| {
                for id in evidence {
                    if source_unit == Some(id.as_str()) {
                        continue;
                    }
                    if self
                        .evidence
                        .get(id)
                        .is_some_and(|e| e.kind == EvidenceKind::Trace)
                        && primitive_trace_roles
                            .insert(id.clone(), role)
                            .is_some_and(|old| old != role)
                    {
                        return Err(
                            "primitive trace event reused across incompatible event roles".into(),
                        );
                    }
                }
                Ok::<(), String>(())
            };
        for store in &self.word_store_observations {
            bind_trace_role(&store.evidence, None, "cpu_word_store")?;
        }
        for observation in &self.indirect_observations {
            bind_trace_role(
                &observation.evidence,
                observation.source_unit.as_deref(),
                "indirect_target",
            )?;
        }
        for verification in &self.entry_verifications {
            bind_trace_role(
                &verification.evidence,
                Some(verification.source_unit.as_str()),
                "entry_verification",
            )?;
        }
'''
path.write_text(text.replace(marker, insert + marker))
