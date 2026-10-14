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
import math
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
    text(40, 111, "Current frontier: first commercial CLOSED scope (OoT blockers)", 16)
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


def squarify(items: list, x: float, y: float, w: float, h: float) -> list:
    """Squarified treemap: items are (key, area) sorted by area, descending."""
    out, items = [], list(items)
    while items:
        short = min(w, h)

        def worst(row):
            total = sum(a for _, a in row)
            return max(max(short * short * a / total ** 2, total ** 2 / (short * short * a))
                       for _, a in row)

        row, rest = [items[0]], items[1:]
        while rest and worst(row + [rest[0]]) <= worst(row):
            row.append(rest.pop(0))
        total = sum(a for _, a in row)
        if w >= h:
            rw, cy = total / h, y
            for key, a in row:
                out.append((key, x, cy, rw, a / rw))
                cy += a / rw
            x, w = x + rw, w - rw
        else:
            rh, cx = total / w, x
            for key, a in row:
                out.append((key, cx, y, a / rh, rh))
                cx += a / rh
            y, h = y + rh, h - rh
        items = rest
    return out


CELL = {"done": "#2ea043", "partial": "#bf8700", "open": "#6e7681"}


def treemap(groups: dict, x0: float, y0: float, w: float, h: float) -> list:
    """groups: name -> [(item, state)]; one cell per item, done first."""
    order = sorted(groups, key=lambda g: (-len(groups[g]), g))
    total = sum(len(groups[g]) for g in order)
    rects = squarify([(g, len(groups[g]) * w * h / total) for g in order], x0, y0, w, h)
    rank = {"done": 0, "partial": 1, "open": 2}
    out = []
    for g, gx, gy, gw, gh in rects:
        items = sorted(groups[g], key=lambda it: (rank[it[1]], it[0]))
        cols = max(1, round(math.sqrt(len(items) * gw / gh)))
        rows = math.ceil(len(items) / cols)
        cw, ch = gw / cols, gh / rows
        last = len(items) - (rows - 1) * cols  # the last row stretches to fill
        for n, (item, state) in enumerate(items):
            row, col = divmod(n, cols)
            w_ = cw if row < rows - 1 else gw / last
            cx, cy = gx + col * w_, gy + row * ch
            out.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{w_:.1f}" height="{ch:.1f}" '
                       f'fill="{CELL[state]}" stroke="#0d1117" stroke-opacity="0.35" stroke-width="0.6">'
                       f'<title>{esc(g)}: {esc(item)} ({state})</title></rect>')
        out.append(f'<rect x="{gx:.1f}" y="{gy:.1f}" width="{gw:.1f}" height="{gh:.1f}" '
                   f'fill="none" stroke="#0d1117" stroke-width="2"/>')
        label = g if len(g) * 6.6 < gw - 6 else g[:max(0, int((gw - 6) / 6.6) - 1)] + "…"
        if gw > 24 and gh > 16 and len(label) > 1:
            out.append(f'<text x="{gx + 4:.1f}" y="{gy + 13:.1f}" class="cell">{esc(label)}</text>')
    return out


def render_coverage_svg(coverage: dict, data: dict) -> str:
    isa = {}
    for name, lowered in coverage["mnemonics"].items():
        isa.setdefault(isa_group(name), []).append((name, "done" if lowered else "open"))
    state = {"verified": "done", "partial": "partial", "open": "open"}
    ms = {a["name"]: [(m["name"], state[m["state"]]) for m in a["milestones"]] for a in data["areas"]}
    counts = milestone_counts(data)
    # stacked, one full-width map per row, so labels stay readable at README width
    width, map_h, top, gap = 840, 300, 30, 26
    map_w, second = width, top + map_h + gap + top
    height = second + map_h
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="Plaid coverage maps">',
        '<style>text{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}'
        '.title{font-size:17px;fill:#1f2328}.cell{font-size:12px;fill:#fff;'
        'paint-order:stroke;stroke:#0d1117;stroke-width:2px;stroke-opacity:.45}'
        '@media (prefers-color-scheme:dark){.title{fill:#e6edf3}}</style>',
        f'<text x="2" y="22" class="title">VR4300 instructions*: '
        f'{pct(coverage["lowered"], coverage["decoded"])} ({coverage["lowered"]}/{coverage["decoded"]})</text>',
        f'<text x="2" y="{second - 8}" class="title">Milestones*: '
        f'{counts["milestones_verified"]} verified, {counts["milestones_partial"]} partial '
        f'({counts["milestones_declared"]})</text>',
    ]
    out += treemap(isa, 0, top, map_w, map_h)
    out += treemap(ms, 0, second, map_w, map_h)
    out.append("</svg>")
    return "\n".join(out) + "\n"


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
        out["isa.svg"] = render_badge("VR4300*", pct(lowered, decoded), shield_color(lowered / decoded))
    return out


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
    if COVERAGE.exists():
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        ok &= write_or_check(COVERAGE_SVG, render_coverage_svg(coverage, data), args.check)
    for name, content in badges(history, data).items():
        ok &= write_or_check(BADGES / name, content, args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
