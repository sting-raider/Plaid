#!/usr/bin/env python3
"""Generate Plaid's README progress map from docs/progress.json."""

from __future__ import annotations

import argparse
import html
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "progress.json"
SVG = ROOT / "docs" / "progress.svg"
DETAILS = ROOT / "docs" / "PROGRESS.md"

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
        f"Last progress-data update: **{data.get('updated', 'unknown')}**.",
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
        "The authoritative detailed engineering state remains [`docs/STATUS.md`](STATUS.md) and "
        "[`docs/NEXT.md`](NEXT.md).",
        "",
    ]
    return "\n".join(lines)


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
        help="fail if generated files do not match docs/progress.json",
    )
    args = parser.parse_args()

    data = load()
    ok = True
    ok &= write_or_check(SVG, render_svg(data), args.check)
    ok &= write_or_check(DETAILS, render_details(data), args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
