from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
marker = 'return Err("indirect trace event has conflicting semantics".into());'
if marker in text:
    print("candidate fix already applied")
    raise SystemExit(0)

old = '''        for o in &self.indirect_observations {
            if !o.site.0.is_multiple_of(4) || !o.target.0.is_multiple_of(4) {
                return Err("unaligned indirect observation".into());
            }
            if o.delay_slot_pc
                .is_some_and(|ds| o.site.0.checked_add(4) != Some(ds.0))
            {
                return Err("incorrect observed delay slot PC".into());
            }
            if let Some(unit) = &o.source_unit
                && !self
                    .evidence
                    .get(unit)
                    .is_some_and(|e| e.kind == EvidenceKind::Trace)
            {
                return Err("missing indirect source-unit trace provenance".into());
            }
            refs(&o.evidence)?;
        }
'''

new = '''        let mut indirect_events =
            BTreeMap::<&str, (u32, u32, Option<u32>, u64, Option<&str>)>::new();
        for o in &self.indirect_observations {
            if !o.site.0.is_multiple_of(4) || !o.target.0.is_multiple_of(4) {
                return Err("unaligned indirect observation".into());
            }
            if o.delay_slot_pc
                .is_some_and(|ds| o.site.0.checked_add(4) != Some(ds.0))
            {
                return Err("incorrect observed delay slot PC".into());
            }
            if let Some(unit) = &o.source_unit
                && !self
                    .evidence
                    .get(unit)
                    .is_some_and(|e| e.kind == EvidenceKind::Trace)
            {
                return Err("missing indirect source-unit trace provenance".into());
            }
            refs(&o.evidence)?;
            let semantics = (
                o.site.0,
                o.target.0,
                o.delay_slot_pc.map(|pc| pc.0),
                o.generation,
                o.source_unit.as_deref(),
            );
            for id in &o.evidence {
                // CompileBegin provenance is reusable context for many executed
                // transfers. It is not the identity of this observation event.
                if o.source_unit.as_deref() == Some(id.as_str()) {
                    continue;
                }
                if self
                    .evidence
                    .get(id)
                    .is_some_and(|e| e.kind == EvidenceKind::Trace)
                    && indirect_events
                        .insert(id.as_str(), semantics)
                        .is_some_and(|old| old != semantics)
                {
                    return Err("indirect trace event has conflicting semantics".into());
                }
            }
        }
'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"expected exactly one candidate insertion site, found {count}")
path.write_text(text.replace(old, new, 1))
print("candidate fix applied")
