#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
spec = json.loads((Path(__file__).with_name("replacements.json")).read_text())
for edit in spec:
    path = root / edit["path"]
    text = path.read_text()
    old = edit["old"]
    new = edit["new"]
    if new in text:
        continue
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{edit['path']}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1))
print("candidate fix applied")
