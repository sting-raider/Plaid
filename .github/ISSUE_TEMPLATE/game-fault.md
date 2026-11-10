---
name: Game fault
description: A native build stops with a fault, stalls, or renders wrongly
title: "[Fault] <game>: fault <code> at <pc>"
labels: []
assignees: []
---

**Game and ROM:** <!-- exact name; add the SHA-1 from `python scripts/native.py` output or `sha1sum`. Never attach the ROM. -->

**Plaid commit:** <!-- git rev-parse --short HEAD -->

**Command:**

```text
SDL_AUDIODRIVER=dummy python scripts/native.py "<rom>" --rt64 --seconds 30
```

**Last `{"stop"` line, exactly as printed:**

```text
```

**What you saw** (frame count / screen reached / expected vs actual):
