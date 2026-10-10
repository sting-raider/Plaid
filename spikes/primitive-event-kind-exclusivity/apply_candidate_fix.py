#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
marker = "trace evidence reused across incompatible primitive roles"
if marker in text:
    print("candidate fix already applied")
    raise SystemExit(0)

replacements = [
    (
        "        for o in &self.indirect_observations {\n",
        "        let mut primitive_trace_roles = BTreeMap::<String, &'static str>::new();\n"
        "        let mut claim_trace_role = |id: &str, role: &'static str| -> Result<(), String> {\n"
        "            if self\n"
        "                .evidence\n"
        "                .get(id)\n"
        "                .is_some_and(|e| e.kind == EvidenceKind::Trace)\n"
        "                && primitive_trace_roles\n"
        "                    .insert(id.to_string(), role)\n"
        "                    .is_some_and(|old| old != role)\n"
        "            {\n"
        "                return Err(\"trace evidence reused across incompatible primitive roles\".into());\n"
        "            }\n"
        "            Ok(())\n"
        "        };\n"
        "        for o in &self.indirect_observations {\n",
    ),
    (
        "            refs(&o.evidence)?;\n        }\n        for store in &self.word_store_observations {\n",
        "            refs(&o.evidence)?;\n"
        "            for id in &o.evidence {\n"
        "                claim_trace_role(id, \"indirect_event\")?;\n"
        "            }\n"
        "            if let Some(unit) = &o.source_unit {\n"
        "                claim_trace_role(unit, \"source_unit\")?;\n"
        "            }\n"
        "        }\n"
        "        for store in &self.word_store_observations {\n",
    ),
    (
        "            refs(&store.evidence)?;\n        }\n        for verification in &self.entry_verifications {\n",
        "            refs(&store.evidence)?;\n"
        "            for id in &store.evidence {\n"
        "                claim_trace_role(id, \"word_store_event\")?;\n"
        "            }\n"
        "        }\n"
        "        for verification in &self.entry_verifications {\n",
    ),
    (
        "                return Err(\"verified entry missing installed identity or unit provenance\".into());\n"
        "            }\n"
        "        }\n"
        "        let mut fetch_totals = BTreeMap::<&str, u64>::new();\n",
        "                return Err(\"verified entry missing installed identity or unit provenance\".into());\n"
        "            }\n"
        "            for id in &verification.evidence {\n"
        "                claim_trace_role(id, \"entry_verification_event\")?;\n"
        "            }\n"
        "            claim_trace_role(&verification.source_unit, \"source_unit\")?;\n"
        "        }\n"
        "        let mut fetch_totals = BTreeMap::<&str, u64>::new();\n",
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one exact anchor, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text)
print("candidate fix applied")
