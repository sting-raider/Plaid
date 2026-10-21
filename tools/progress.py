#!/usr/bin/env python3
"""Generate Plaid's README progress map from docs/progress.json, and the
progress history (chart, table, badges) from docs/history.json.

`--record` measures the current tree (lowered VR4300 forms via
`plaid isa-coverage`, milestone counts from docs/progress.json) and stores
today's point; `--backfill` adds missing past days from git history."""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "progress.json"
SVG = ROOT / "docs" / "progress.svg"
DETAILS = ROOT / "docs" / "PROGRESS.md"
HISTORY = ROOT / "docs" / "history.json"
HISTORY_SVG = ROOT / "docs" / "history.svg"
HISTORY_MD = ROOT / "docs" / "HISTORY.md"
BADGES = ROOT / "docs" / "badges"
COVERAGE = ROOT / "docs" / "isa-coverage.json"
COVERAGE_SVG = ROOT / "docs" / "coverage.svg"
RSP_COVERAGE = ROOT / "docs" / "rsp-coverage.json"
ASSUMPTIONS = ROOT / "docs" / "assumptions.json"
ASSUMPTIONS_SVG = ROOT / "docs" / "assumptions.svg"
README = ROOT / "README.md"
BEGIN, END = "<!-- assumptions:begin -->", "<!-- assumptions:end -->"

STATE_LABEL = {
    "verified": "verified",
    "partial": "partial",
    "open": "open",
}


def load() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise SystemExit(f"unsupported progress schema: {data.get('version')!r}")
    if not data.get("areas"):
        raise SystemExit("progress data has no areas")
    for area in data["areas"]:
        if not area.get("name") or not area.get("milestones"):
            raise SystemExit("every area needs a name and milestones")
        for milestone in area["milestones"]:
            if milestone.get("state") not in STATE_LABEL:
                raise SystemExit(
                    f"invalid state for {area['name']}/{milestone.get('name')}: "
                    f"{milestone.get('state')!r}"
                )
    return data


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_svg(data: dict) -> str:
    width = 1200
    card_width = 548
    row_heights = [
        132 + 26 * max(len(a["milestones"]) for a in data["areas"][i:i + 2])
        for i in range(0, len(data["areas"]), 2)
    ]
    height = 304 + sum(h + 24 for h in row_heights) + 72
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Plaid engineering progress atlas</title>',
        '<desc id="desc">Detailed integrated, partial and open milestones. '
        'Retained finite evidence does not establish whole-ROM closure or native completion.</desc>',
        '<defs><linearGradient id="header" x2="1" y2="1">'
        '<stop stop-color="#123247"/><stop offset="1" stop-color="#111a2b"/>'
        '</linearGradient></defs>',
        f'<rect width="{width}" height="{height}" rx="18" fill="#0b1320"/>',
        '<rect width="1200" height="250" rx="18" fill="url(#header)"/>',
    ]

    def text(x, y, value, size=14, color="#a9b8ca", weight=400, anchor="start"):
        out.append(
            f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'
        )

    def rect(x, y, w, h, fill, radius=0, stroke="none"):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                   f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    palette = {"verified": "#58d5ab", "partial": "#ffc66d", "open": "#a9b8ca"}
    labels = {"verified": "DONE", "partial": "PARTIAL", "open": "OPEN"}
    text(40, 38, "PLAID  /  ENGINEERING ATLAS", 13, "#78dcca", 700)
    text(1160, 38, f'Reviewed {data.get("updated", "unknown")}', 13, anchor="end")
    text(40, 84, "The path from ROM to native gameplay", 32, "#f4f7fc", 700)
    text(40, 111, f'Current frontier: {data.get("frontier", "unknown")}', 16)
    for i, evidence in enumerate(data.get("evidence", [])):
        x = 40 + i * 286
        rect(x, 136, 262, 96, "#152538", 10, "#294052")
        text(x + 18, 171, evidence["value"], 27, "#f4f7fc", 700)
        text(x + 18, 194, evidence["label"], 13, "#d7e4f3", 600)
        text(x + 18, 214, evidence["detail"], 11)
    for x, state, label in [(40, "verified", "DONE · integrated bounded milestone"),
                            (410, "partial", "PARTIAL · proof / coverage remains"),
                            (790, "open", "OPEN · not yet demonstrated")]:
        rect(x, 265, 9, 9, palette[state], 2)
        text(x + 17, 274, label, 12)

    y = 304
    for row, row_height in enumerate(row_heights):
        for col, area in enumerate(data["areas"][row * 2:row * 2 + 2]):
            x = 40 + col * (card_width + 24)
            counts = {state: sum(m["state"] == state for m in area["milestones"])
                      for state in STATE_LABEL}
            rect(x, y, card_width, row_height, "#111e2f", 12, "#2a3b4f")
            text(x + 20, y + 30, f'{row * 2 + col + 1:02d}', 13, "#78dcca", 700)
            text(x + 54, y + 31, area["name"], 20, "#f4f7fc", 700)
            text(x + 20, y + 56,
                 f'{counts["verified"]} integrated   /   {counts["partial"]} partial   /   {counts["open"]} open', 12)
            cursor = x + 20
            for state in STATE_LABEL:
                segment = (card_width - 40) * counts[state] / len(area["milestones"])
                if segment:
                    rect(cursor, y + 70, segment, 4, palette[state])
                cursor += segment
            for i, milestone in enumerate(area["milestones"]):
                line_y = y + 99 + i * 26
                state = milestone["state"]
                out.append('<g class="milestone">')
                out.append(f'<title>{esc(area["name"])}: {esc(milestone["name"])} '
                           f'({STATE_LABEL[state]})</title>')
                text(x + 20, line_y, "✓" if state == "verified" else "◐" if state == "partial" else "○",
                     15, palette[state], 700)
                text(x + 43, line_y, milestone["name"], 14, "#d7e4f3")
                text(x + card_width - 20, line_y, labels[state], 10, palette[state], 700, "end")
                out.append('</g>')
            footer_y = y + row_height - 44
            text(x + 20, footer_y, "REMAINING", 10, "#ffc66d", 700)
            for i, line in enumerate(textwrap.wrap(area.get("remaining", ""), width=75)):
                text(x + 20, footer_y + 18 + i * 16, line, 12)
        y += row_height + 24
    text(40, y + 14, "Evidence is finite. Milestones have different scope; these counts are not a completion percentage.", 13)
    text(40, y + 38, "FIRST COMMERCIAL CLOSED SCOPE: OPEN     /     WHOLE-ROM CLOSURE: OPEN     /     native_complete: false",
         13, "#ffc66d", 600)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def icon(state: str) -> str:
    return {"verified": "✅", "partial": "🟨", "open": "⬜"}[state]


def render_details(data: dict) -> str:
    lines = [
        "# Plaid progress map",
        "",
        "This page is generated from [`docs/progress.json`](progress.json) by "
        "[`tools/progress.py`](../tools/progress.py).",
        "",
        "The map deliberately does **not** publish a single overall completion percentage. "
        "Plaid's subsystems have hard dependencies: a mostly green discovery pipeline is not "
        "equivalent to a mostly finished native recompiler.",
        "",
        "Legend:",
        "",
        "- ✅ **Verified** — verified and integrated on `main` for the stated milestone.",
        "- 🟨 **Partial** — implemented or experimentally supported, but proof/coverage is incomplete.",
        "- ⬜ **Open** — not implemented or not yet demonstrated.",
        "",
        f"Last progress-data update: **{data.get('updated', 'unknown')}**. "
        "Day-by-day numbers: [progress history](HISTORY.md).",
        "",
    ]
    lines += ["## Retained evidence", "", "| Evidence | Observed scope | Source |", "| --- | --- | --- |"]
    for evidence in data.get("evidence", []):
        source = "../" + evidence["source"] if evidence["source"].startswith("research/") else Path(evidence["source"]).name
        lines.append(f"| **{evidence['value']}** {evidence['label']} | {evidence['detail']} | [Receipt / status]({source}) |")
    lines += ["", "These are finite observations, not exhaustive execution coverage or a CLOSED certificate.", ""]
    for area in data["areas"]:
        lines += [f"## {area['name']}", "", "| Milestone | State |", "| --- | --- |"]
        for milestone in area["milestones"]:
            lines.append(
                f"| {milestone['name']} | {icon(milestone['state'])} {STATE_LABEL[milestone['state']]} |"
            )
        lines += ["", f"**Remaining:** {area.get('remaining', '')}", ""]
    lines += [
        "## Interpretation",
        "",
        "The status cells describe the maturity of explicitly named milestones, not title compatibility "
        "or the probability that an arbitrary ROM will work. A `partial` milestone stays partial until "
        "its remaining proof obligations are closed. Research branches do not turn a cell green until "
        "the relevant result is integrated and verified on `main`.",
        "",
        "The current engineering state is [`docs/STATUS.md`](STATUS.md) (history in [`STATUS-LOG.md`](STATUS-LOG.md)) and "
        "[`docs/NEXT.md`](NEXT.md).",
        "",
    ]
    return "\n".join(lines)


def milestone_counts(data: dict) -> dict:
    states = [m["state"] for a in data["areas"] for m in a["milestones"]]
    return {
        "milestones_verified": states.count("verified"),
        "milestones_partial": states.count("partial"),
        "milestones_declared": len(states),
    }


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def measure_isa() -> dict:
    exe = os.environ.get("PLAID_BIN") or str(
        ROOT / "target" / "debug" / ("plaid.exe" if os.name == "nt" else "plaid"))
    coverage = json.loads(subprocess.check_output([exe, "isa-coverage"], text=True))
    if coverage.get("format") != "plaid-isa-coverage-v0":
        raise SystemExit("unexpected isa-coverage output")
    COVERAGE.write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    rsp = json.loads(subprocess.check_output([exe, "rsp-coverage"], text=True))
    if rsp.get("format") != "plaid-rsp-coverage-v0":
        raise SystemExit("unexpected rsp-coverage output")
    RSP_COVERAGE.write_text(json.dumps(rsp, indent=2) + "\n", encoding="utf-8")
    return {"isa_lowered": coverage["lowered"], "isa_decoded": coverage["decoded"]}


def load_history() -> dict:
    if not HISTORY.exists():
        return {"version": 1, "points": []}
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    if history.get("version") != 1:
        raise SystemExit(f"unsupported history schema: {history.get('version')!r}")
    return history


def store(history: dict, point: dict) -> None:
    points = [p for p in history["points"] if p["date"] != point["date"]] + [point]
    history["points"] = sorted(points, key=lambda p: p["date"])
    HISTORY.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


def record(history: dict, data: dict) -> None:
    point = {"date": datetime.date.today().isoformat(), **measure_isa(), **milestone_counts(data)}
    store(history, point)
    print(f"recorded {point['date']}")


def backfill(history: dict) -> None:
    """Add missing past days from the last main commit of each day. Lowered
    forms are 0 by construction before crates/plaid-lower existed; later
    unmeasured days stay null rather than being guessed."""
    known = {p["date"] for p in history["points"]}
    decoded = next((p["isa_decoded"] for p in reversed(history["points"])
                    if p.get("isa_decoded")), None)
    last = {}
    for line in git("log", "--first-parent", "main", "--format=%cs %H").splitlines():
        day, sha = line.split()
        last.setdefault(day, sha)
    for day, sha in sorted(last.items()):
        if day in known or day >= datetime.date.today().isoformat():
            continue
        point = {"date": day, "commit": sha[:12]}
        try:
            point.update(milestone_counts(json.loads(git("show", f"{sha}:docs/progress.json"))))
        except subprocess.CalledProcessError:
            pass
        files = git("ls-tree", "-r", "--name-only", sha, "crates/").split()
        if not any(f.startswith("crates/plaid-lower/") for f in files):
            point.update({"isa_lowered": 0, "isa_decoded": decoded})
        store(history, point)
        print(f"backfilled {day}")


SERIES = [
    ("isa_decoded", "VR4300 forms decoded", "#8b9bb0", True),
    ("isa_lowered", "Lowered to native C", "#4f9cf7", False),
    ("milestones_declared", "Milestones declared", "#3f8f74", True),
    ("milestones_verified", "Milestones verified", "#58d5ab", False),
]


def render_history_svg(history: dict) -> str:
    points = history["points"]
    width, height = 1100, 400
    left, right, top, bottom = 56, 210, 28, 52
    plot_w, plot_h = width - left - right, height - top - bottom
    peak = max([p.get(key) or 0 for p in points for key, *_ in SERIES] + [1])
    step = 50 if peak <= 300 else 100
    y_max = -(-peak // step) * step

    def x(i: int) -> float:
        return left + (plot_w * i / (len(points) - 1) if len(points) > 1 else plot_w / 2)

    def y(v: float) -> float:
        return top + plot_h * (1 - v / y_max)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-labelledby="t d">',
        '<title id="t">Plaid progress history</title>',
        '<desc id="d">Lowered VR4300 instruction forms and verified milestones, one point per day.</desc>',
        f'<rect width="{width}" height="{height}" rx="14" fill="#0b1320"/>',
    ]
    font = 'font-family="Segoe UI,Arial,sans-serif"'
    for v in range(0, y_max + 1, step):
        out.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#1f2d40"/>')
        out.append(f'<text x="{left - 8}" y="{y(v) + 4:.1f}" fill="#7d8da3" font-size="11" {font} text-anchor="end">{v}</text>')
    for i, p in enumerate(points):
        out.append(f'<text x="{x(i):.1f}" y="{height - bottom + 20}" fill="#7d8da3" font-size="11" {font} '
                   f'text-anchor="middle">{p["date"][5:]}</text>')
    labels = []
    for key, name, color, dashed in SERIES:
        pts = [(x(i), y(p[key]), p) for i, p in enumerate(points) if p.get(key) is not None]
        if not pts:
            continue
        path = " ".join(f"{'M' if n == 0 else 'L'}{px:.1f},{py:.1f}" for n, (px, py, _) in enumerate(pts))
        if not dashed:
            out.append(f'<path d="{path} L{pts[-1][0]:.1f},{y(0):.1f} L{pts[0][0]:.1f},{y(0):.1f} Z" '
                       f'fill="{color}" fill-opacity="0.12"/>')
        out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{1.5 if dashed else 2.5}"'
                   f'{" stroke-dasharray=\"5 4\"" if dashed else ""}/>')
        if not dashed:
            for px, py, p in pts:
                out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{color}">'
                           f'<title>{p["date"]}: {esc(name)} {p[key]}</title></circle>')
        labels.append([pts[-1][1], f"{name} {pts[-1][2][key]}", color])
    labels.sort()
    for n in range(1, len(labels)):  # keep end labels from overlapping
        labels[n][0] = max(labels[n][0], labels[n - 1][0] + 16)
    for ly, text_, color in labels:
        out.append(f'<text x="{left + plot_w + 10}" y="{ly + 4:.1f}" fill="{color}" font-size="13" '
                   f'font-weight="600" {font}>{esc(text_)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def pct(a, b) -> str:
    return f"{100 * a / b:.1f}%" if a is not None and b else "—"


def cell(v) -> str:
    return "—" if v is None else str(v)


def render_history_md(history: dict) -> str:
    lines = [
        "# Plaid progress history",
        "",
        "[![Plaid progress history](history.svg)](history.json)",
        "",
        "One point per day, generated from [`history.json`](history.json) by "
        "[`tools/progress.py`](../tools/progress.py). Hover a point in the SVG for exact numbers.",
        "",
        "- **VR4300 forms lowered** — instruction forms of the pinned decoder that the VR4300 "
        "implements (pseudo-instructions and non-VR4300 forms excluded), counted as lowered only "
        "when a program using the form passes discovery, the guarded-scope solver and "
        "`plaid-lower` (`plaid isa-coverage`). Before `crates/plaid-lower` existed the count is 0 "
        "by construction.",
        "- **Milestones** — states in [`progress.json`](progress.json) at the last `main` commit of the day. "
        "The declared total grows as milestones are added; it is not a completion percentage.",
        "",
        "| Date | VR4300 forms lowered | % | Milestones verified | partial | declared |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for p in reversed(history["points"]):
        lowered, decoded = p.get("isa_lowered"), p.get("isa_decoded")
        isa = "—" if lowered is None else f"{lowered}/{cell(decoded)}"
        lines.append(f"| {p['date']} | {isa} | {pct(lowered, decoded)} | {cell(p.get('milestones_verified'))} "
                     f"| {cell(p.get('milestones_partial'))} | {cell(p.get('milestones_declared'))} |")
    lines += ["", "Back to the [progress map](PROGRESS.md) and the [status page](STATUS.md).", ""]
    return "\n".join(lines)


def isa_group(name: str) -> str:
    if name.startswith("c."):
        return "FPU compare"
    if name.startswith(("cvt.", "round.", "trunc.", "ceil.", "floor.")):
        return "FPU convert"
    if "." in name:
        return "FPU arith"
    if name in ("mfc1", "mtc1", "dmfc1", "dmtc1", "cfc1", "ctc1", "lwc1", "swc1", "ldc1", "sdc1") \
            or name.startswith("bc1"):
        return "COP1 move"
    if name in ("mfc0", "mtc0", "dmfc0", "dmtc0", "cfc0", "ctc0", "eret", "cache", "sync",
                "syscall", "break") or name.startswith("tlb"):
        return "COP0/system"
    if name[0] == "t":
        return "Trap"
    if name in ("j", "jal", "jr", "jalr") or name.startswith("b"):
        return "Branch/jump"
    if name in ("mult", "multu", "div", "divu", "dmult", "dmultu", "ddiv", "ddivu",
                "mfhi", "mflo", "mthi", "mtlo"):
        return "Mul/div"
    if name[0] in "ls" and name not in ("lui", "sll", "sllv", "slt", "slti", "sltiu", "sltu", "sra",
                                         "srav", "srl", "srlv", "sub", "subu"):
        return "Load/store"
    if name.startswith("d"):
        return "64-bit ALU"
    return "ALU"


PLAIN, CHECKED, UNCHECKED, OPEN = "#2ea043", "#d29922", "#db6d28", "#6e7681"
ISA_STATES = [
    ("plain", PLAIN, "Matches ares, no run-time assumption"),
    ("checked", CHECKED, "Matches ares; native code checks an assumption and aborts if it fails"),
    ("unchecked", UNCHECKED, "Matches ares; relies on an assumption nothing checks"),
    ("open", OPEN, "Not lowered"),
]


def isa_state(name: str, lowered: bool, rules: list) -> str:
    """Worst dependency wins: unchecked > checked > plain."""
    if not lowered:
        return "open"
    hits = {r["state"] for r in rules
            if name in r.get("mnemonics", []) or isa_group(name) in r.get("groups", [])}
    return "unchecked" if "unchecked" in hits else "checked" if "checked" in hits else "plain"


def stacked(x, y, w, h, segments) -> list:
    """segments: (count, color, tooltip); widths are proportional to counts."""
    total = sum(n for n, *_ in segments)
    out, cx = [], x
    for n, color, tip in segments:
        if n:
            sw = w * n / total
            out.append(f'<rect x="{cx:.1f}" y="{y}" width="{sw:.1f}" height="{h}" fill="{color}" '
                       f'stroke="#0d1117" stroke-opacity=".35" stroke-width=".6"><title>{esc(tip)}</title></rect>')
            cx += sw
    return out


def render_coverage_svg(coverage: dict, data: dict, rsp: dict | None, assumptions: dict) -> str:
    width, label_w, bar_w, row = 840, 150, 560, 24
    rules = assumptions["instruction_rules"]
    for r in rules:
        unknown = set(r.get("mnemonics", [])) - set(coverage["mnemonics"])
        if unknown:
            raise SystemExit(f"instruction_rules name unknown mnemonics: {sorted(unknown)}")
    out, y = [], 0

    def text(x, yy, value, cls="t"):
        out.append(f'<text x="{x}" y="{yy}" class="{cls}">{esc(value)}</text>')

    def legend(items):
        nonlocal y
        for color, label in items:
            out.append(f'<rect x="2" y="{y - 10}" width="11" height="11" fill="{color}"/>')
            text(20, y, label, "s")
            y += 18

    def group_rows(groups, total_label, order):
        """groups: name -> [state]; one stacked row per group, a bold total first."""
        nonlocal y
        every = [s for states in groups.values() for s in states]
        for label, states, cls in [(total_label, every, "b")] + [(g, groups[g], "t") for g in sorted(groups, key=lambda g: (-len(groups[g]), g))]:
            counts = {s: states.count(s) for s in order}
            text(2, y + 16, label, cls)
            out.extend(stacked(label_w, y, bar_w, 18 if cls == "b" else 16,
                               [(counts[s], COLORS[s], f"{label}: {counts[s]} {s}") for s in order]))
            text(label_w + bar_w + 10, y + 15, f"{len(states) - counts.get('open', 0)}/{len(states)}", cls)
            y += row + (6 if cls == "b" else 0)

    COLORS = {"plain": PLAIN, "checked": CHECKED, "unchecked": UNCHECKED, "open": OPEN,
              "verified": PLAIN, "partial": CHECKED}
    isa = {}
    for name, lowered in coverage["mnemonics"].items():
        isa.setdefault(isa_group(name), []).append(isa_state(name, lowered, rules))
    flat = [s for v in isa.values() for s in v]

    y = 22
    text(2, y, f"VR4300 instructions*: {coverage['lowered']} of {coverage['decoded']} forms lower to native C "
               f"({pct(coverage['lowered'], coverage['decoded'])}); {flat.count('plain')} with no run-time assumption", "h")
    y += 26
    legend([(c, label) for _, c, label in ISA_STATES])
    y += 6
    group_rows(isa, "All forms", [s for s, *_ in ISA_STATES])
    y += 14

    if rsp:
        groups = {}
        for name, m in rsp["mnemonics"].items():
            groups.setdefault(m["group"], []).append("plain" if m["lowered"] else "open")
        text(2, y + 14, f"RSP instructions*: {rsp['lowered']} of {rsp['documented']} lower and match ares "
                        f"({pct(rsp['lowered'], rsp['documented'])})", "h")
        y += 40
        text(2, y + 16, "In a real game", "b")
        out.extend(stacked(label_w, y, bar_w, 18, [(rsp["lowered"], UNCHECKED, "relies on the unproven RSP obligations below")]))
        text(label_w + bar_w + 10, y + 15, f"0/{rsp['lowered']}", "b")
        y += row + 6
        group_rows(groups, "Instruction semantics", ["plain", "open"])
        y += 10
        text(2, y + 14, "Instruction semantics only. A real game's RSP side also needs these, none fully done yet:", "b")
        y += 30
        for ob in assumptions["rsp_obligations"]:
            fill = PLAIN if ob["state"] == "done" else CHECKED if ob["state"].startswith("partial") else UNCHECKED
            out.append(f'<rect x="2" y="{y - 11}" width="12" height="12" rx="2" fill="{fill}"/>')
            text(22, y, f'{ob["name"]}: {ob["state"]}', "t")
            y += 20
        y += 14

    state = {"verified": "verified", "partial": "partial", "open": "open"}
    areas = {a["name"]: [state[m["state"]] for m in a["milestones"]] for a in data["areas"]}
    counts = milestone_counts(data)
    text(2, y + 14, f"Milestones*: {counts['milestones_verified']} verified, {counts['milestones_partial']} partial "
                    f"of {counts['milestones_declared']}", "h")
    y += 36
    out.append(f'<rect x="2" y="{y - 10}" width="11" height="11" fill="{PLAIN}"/>')
    text(20, y, "verified", "s")
    out.append(f'<rect x="110" y="{y - 10}" width="11" height="11" fill="{CHECKED}"/>')
    text(128, y, "partial", "s")
    out.append(f'<rect x="210" y="{y - 10}" width="11" height="11" fill="{OPEN}"/>')
    text(228, y, "open", "s")
    y += 14
    for name, states in [("All milestones", [s for v in areas.values() for s in v])] + list(areas.items()):
        c = {s: states.count(s) for s in ("verified", "partial", "open")}
        text(2, y + 16, name, "b" if name.startswith("All") else "t")
        out.extend(stacked(label_w, y, bar_w, 16, [(c[s], COLORS.get(s, OPEN), f"{name}: {c[s]} {s}") for s in c]))
        text(label_w + bar_w + 10, y + 15, f"{c['verified']}/{len(states)}", "t")
        y += row
    height = y + 10
    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="Plaid coverage and assumptions">',
        '<style>text{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;fill:#1f2328}'
        '.h{font-size:16px;font-weight:600}.b{font-size:13px;font-weight:600}.t{font-size:13px}'
        '.s{font-size:12px;fill:#59636e}'
        '@media (prefers-color-scheme:dark){text{fill:#e6edf3}.s{fill:#9198a1}}</style>',
    ]
    return "\n".join(head + out + ["</svg>"]) + "\n"


def shield_color(fraction: float) -> str:
    for limit, color in ((0.9, "#4c1"), (0.75, "#97ca00"), (0.5, "#a4a61d"), (0.25, "#dfb317")):
        if fraction >= limit:
            return color
    return "#e05d44"


def render_badge(label: str, value: str, color: str) -> str:
    lw, vw = 10 + round(6.5 * len(label)), 10 + round(6.5 * len(value))
    w = lw + vw
    font = 'font-family="Verdana,DejaVu Sans,sans-serif" font-size="11"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" '
        f'aria-label="{esc(label)}: {esc(value)}"><title>{esc(label)}: {esc(value)}</title>'
        f'<rect width="{lw}" height="20" fill="#555"/>'
        f'<rect x="{lw}" width="{vw}" height="20" fill="{color}"/>'
        f'<text x="{lw / 2}" y="14" fill="#fff" {font} text-anchor="middle">{esc(label)}</text>'
        f'<text x="{lw + vw / 2}" y="14" fill="#fff" {font} text-anchor="middle">{esc(value)}</text></svg>\n'
    )


def badges(history: dict, data: dict) -> dict:
    latest = history["points"][-1] if history["points"] else {}
    closed = next((e["value"] for e in data.get("evidence", [])
                   if e["label"] == "Commercial ROMs CLOSED"), "0")
    m = milestone_counts(data)
    out = {
        "milestones.svg": render_badge(
            "milestones*", f"{m['milestones_verified']}/{m['milestones_declared']}",
            shield_color(m["milestones_verified"] / m["milestones_declared"])),
        "closed.svg": render_badge("ROMs CLOSED", str(closed), "#e05d44" if closed == "0" else "#4c1"),
    }
    if latest.get("isa_lowered") is not None:
        lowered, decoded = latest["isa_lowered"], latest["isa_decoded"]
        out["isa.svg"] = render_badge("VR4300 forms lowered*", pct(lowered, decoded), shield_color(lowered / decoded))
    return out


# blocker classes drawn as their own segment; the rest fall into "other"
BLOCKER_GROUPS = [
    ("Unresolved indirect sites", ["unresolved_indirect_site"], "#d1495b"),
    ("Pointer tables unproven", ["pointer_table_immutability_unproven",
                                 "pointer_table_target_identity_unproven"], "#edae49"),
    ("Unsupported instructions", ["exception_or_unsupported_instruction"], "#00798c"),
    ("Runtime boundary", ["runtime_boundary_outside_scope"], "#8d6ab8"),
]


def load_assumptions() -> dict:
    data = json.loads(ASSUMPTIONS.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise SystemExit(f"unsupported assumptions schema: {data.get('version')!r}")
    for rom in data["roms"]:
        if set(data["singletons"]) - set(rom["whole_rom"]["by_class"]):
            raise SystemExit(f"{rom['id']}: missing singleton blocker classes")
    for x in data["assumptions"]:
        if x["state"] not in ("assumed", "retired"):
            raise SystemExit(f"invalid assumption state: {x['state']!r}")
    return data


def blocker_total(rom: dict) -> int:
    return sum(rom["whole_rom"]["by_class"].values())


def blocker_segments(rom: dict) -> list:
    """(label, count, color) per group; every other class is 'Other'."""
    classes = rom["whole_rom"]["by_class"]
    named = {c for _, cs, _ in BLOCKER_GROUPS for c in cs}
    segs = [(label, sum(classes.get(c, 0) for c in cs), color) for label, cs, color in BLOCKER_GROUPS]
    segs.append(("Other (global obligations)", sum(n for c, n in classes.items() if c not in named), "#6e7681"))
    return segs


def closed_sites(rom: dict) -> int:
    return rom["indirect_sites"] - rom["whole_rom"]["by_class"]["unresolved_indirect_site"]


def retired_count(a: dict) -> int:
    return sum(x["state"] == "retired" for x in a["assumptions"])


def render_assumptions_svg(a: dict) -> str:
    width, left, bar_w, row = 840, 270, 420, 72
    height = 116 + row * len(a["roms"]) + 44
    peak = max(blocker_total(r) for r in a["roms"])
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="Distance to no-assumption CLOSED">',
        '<style>text{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;fill:#1f2328}'
        '.title{font-size:17px}.sub{font-size:12px;fill:#59636e}.n{font-size:13px;font-weight:600}'
        '@media (prefers-color-scheme:dark){text{fill:#e6edf3}.sub{fill:#9198a1}}</style>',
        f'<text x="2" y="22" class="title">Whole-ROM blockers with no assumptions (measured {esc(a["measured"])})</text>',
        f'<text x="2" y="44" class="title">Assumptions retired: {retired_count(a)}/{len(a["assumptions"])}</text>',
    ]
    lx = 2
    for label, _, color in blocker_segments(a["roms"][0]):
        out.append(f'<rect x="{lx}" y="62" width="10" height="10" fill="{color}"/>'
                   f'<text x="{lx + 15}" y="71" class="sub">{esc(label)}</text>')
        lx += 15 + int(len(label) * 6.2) + 14
    for i, rom in enumerate(a["roms"]):
        y = 96 + i * row
        out.append(f'<text x="2" y="{y + 15}" class="n">{esc(rom["name"])}</text>')
        out.append(f'<text x="2" y="{y + 34}" class="sub">{rom["blocks"]:,} blocks, {rom["indirect_sites"]:,} indirect sites</text>')
        out.append(f'<text x="2" y="{y + 50}" class="sub">{closed_sites(rom):,} sites closed without assumptions</text>')
        x = left
        for label, n, color in blocker_segments(rom):
            w = bar_w * n / peak
            if n:
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" height="26" fill="{color}">'
                           f'<title>{esc(rom["name"])}: {esc(label)} {n:,}</title></rect>')
            x += w
        out.append(f'<text x="{x + 8:.1f}" y="{y + 18}" class="n">{blocker_total(rom):,}</text>')
    y = 96 + row * len(a["roms"])
    out.append(f'<text x="2" y="{y + 8}" class="sub">A bar reaches zero only when the whole ROM closes with no assumption. '
               f'Bars share one scale.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_assumptions_block(a: dict) -> str:
    L = [BEGIN, "",
         "### Distance to no-assumption CLOSED", "",
         "[![whole-ROM blockers by class](docs/assumptions.svg)](docs/assumptions.json)", "",
         f"No commercial ROM is `CLOSED` whole-ROM without assumptions. Assumptions retired: "
         f"**{retired_count(a)}/{len(a['assumptions'])}**. Measured {a['measured']} with `{a['command']}`; "
         "data in [`docs/assumptions.json`](docs/assumptions.json), generated by `tools/progress.py`.", "",
         "| ROM | Blocks | Indirect sites closed with no assumption | Whole-ROM blockers | Scoped results |",
         "| --- | --- | --- | --- | --- |"]
    for r in a["roms"]:
        scopes = "; ".join(
            f"`{s['scope']}` **{s['status']}**" + ("" if s["blockers"] == 0 else f" ({s['blockers']:,} blockers)")
            + (f", {s['assumptions']} assumptions" if s["assumptions"] else "")
            for s in r["scopes"])
        L.append(f"| {r['name']} | {r['blocks']:,} | {closed_sites(r):,} of {r['indirect_sites']:,} | "
                 f"{r['whole_rom']['status']}, {blocker_total(r):,} | {scopes} |")
    classes = []
    for r in a["roms"]:
        classes += [c for c in r["whole_rom"]["by_class"] if c not in classes]
    L += ["", "Whole-ROM blockers by class:", "",
          "| Class | " + " | ".join(r["id"] for r in a["roms"]) + " |",
          "| --- | " + " | ".join("---:" for _ in a["roms"]) + " |"]
    for c in sorted(classes, key=lambda c: -max(r["whole_rom"]["by_class"].get(c, 0) for r in a["roms"])):
        L.append(f"| `{c}` | " + " | ".join(f"{r['whole_rom']['by_class'].get(c, 0):,}" for r in a["roms"]) + " |")
    L += ["", "Assumptions behind the SM64 `--address-taken` result. \"Fault n\" means the native artifact "
          "tests it at run time and aborts with that code; **unchecked** ones are trusted.", "",
          "| # | Assumption | Run-time check | State | Retired when |", "| ---: | --- | --- | --- | --- |"]
    for i, x in enumerate(a["assumptions"], 1):
        check = "fault " + "/".join(map(str, x["faults"])) if x["checked"] else "**unchecked**"
        L.append(f"| {i} | {x['name']} | {check} | {x['state']} | {x['retire']} |")
    L += ["", "Inputs given by hand, outside the solver:", ""] + [f"- {h}" for h in a["hand_inputs"]] + ["", END]
    return "\n".join(L)


def splice_readme(text: str, block: str) -> str:
    if BEGIN not in text or END not in text:
        raise SystemExit(f"README.md needs the {BEGIN} / {END} markers")
    return text.split(BEGIN, 1)[0] + block + text.split(END, 1)[1]


def write_or_check(path: Path, content: str, check: bool) -> bool:
    if check:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            print(f"stale generated file: {path.relative_to(ROOT)}")
            return False
        return True
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated files do not match docs/progress.json and docs/history.json",
    )
    parser.add_argument("--record", action="store_true",
                        help="measure the current tree and store today's history point")
    parser.add_argument("--backfill", action="store_true",
                        help="add missing past days to docs/history.json from git")
    args = parser.parse_args()

    data = load()
    history = load_history()
    if args.backfill and not args.check:
        backfill(history)
    if args.record and not args.check:
        record(history, data)
    ok = True
    ok &= write_or_check(SVG, render_svg(data), args.check)
    ok &= write_or_check(DETAILS, render_details(data), args.check)
    ok &= write_or_check(HISTORY_SVG, render_history_svg(history), args.check)
    ok &= write_or_check(HISTORY_MD, render_history_md(history), args.check)
    if not args.check:
        BADGES.mkdir(exist_ok=True)
    assumptions = load_assumptions()
    if COVERAGE.exists():
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        rsp = json.loads(RSP_COVERAGE.read_text(encoding="utf-8")) if RSP_COVERAGE.exists() else None
        ok &= write_or_check(COVERAGE_SVG, render_coverage_svg(coverage, data, rsp, assumptions), args.check)
    ok &= write_or_check(ASSUMPTIONS_SVG, render_assumptions_svg(assumptions), args.check)
    ok &= write_or_check(README, splice_readme(README.read_text(encoding="utf-8"),
                                               render_assumptions_block(assumptions)), args.check)
    for name, content in badges(history, data).items():
        ok &= write_or_check(BADGES / name, content, args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
