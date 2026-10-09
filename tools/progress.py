#!/usr/bin/env python3
"""Generate Plaid's README progress map from docs/progress.json."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "progress.json"
SVG = ROOT / "docs" / "progress.svg"
DETAILS = ROOT / "docs" / "PROGRESS.md"

COLORS = {
    "background": "#0d1117",
    "panel": "#161b22",
    "border": "#30363d",
    "text": "#f0f6fc",
    "muted": "#8b949e",
    "verified": "#2ea043",
    "partial": "#d29922",
    "open": "#6e7681",
}

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
    width = 1100
    height = 150 + len(data["areas"]) * 70
    label_x = 24
    bar_x = 270
    bar_width = width - bar_x - 30
    bar_height = 28

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Plaid progress map</title>',
        '<desc id="desc">Verified, partial and open milestones for Plaid subsystems.</desc>',
        f'<rect width="{width}" height="{height}" rx="12" fill="{COLORS["background"]}"/>',
        f'<text x="24" y="34" fill="{COLORS["text"]}" font-family="ui-sans-serif,system-ui,sans-serif" '
        'font-size="22" font-weight="700">Plaid progress map</text>',
        f'<text x="24" y="57" fill="{COLORS["muted"]}" font-family="ui-sans-serif,system-ui,sans-serif" '
        f'font-size="12">Auditable milestone counts · updated {esc(data.get("updated", "unknown"))}</text>',
    ]

    x = 24
    for state, label in (
        ("verified", "verified / integrated"),
        ("partial", "partial / bounded"),
        ("open", "open"),
    ):
        out.append(f'<rect x="{x}" y="74" width="14" height="14" rx="3" fill="{COLORS[state]}"/>')
        out.append(
            f'<text x="{x + 20}" y="86" fill="{COLORS["muted"]}" '
            f'font-family="ui-sans-serif,system-ui,sans-serif" font-size="11">{esc(label)}</text>'
        )
        x += 188 if state == "verified" else 154

    for index, area in enumerate(data["areas"]):
        y = 112 + index * 70
        milestones = area["milestones"]
        counts = {state: 0 for state in STATE_LABEL}
        for milestone in milestones:
            counts[milestone["state"]] += 1
        total = len(milestones)

        out.append(
            f'<text x="{label_x}" y="{y + 16}" fill="{COLORS["text"]}" '
            'font-family="ui-sans-serif,system-ui,sans-serif" font-size="14" font-weight="650">'
            f'{esc(area["name"])}</text>'
        )
        out.append(
            f'<text x="{label_x}" y="{y + 36}" fill="{COLORS["muted"]}" '
            'font-family="ui-sans-serif,system-ui,sans-serif" font-size="11">'
            f'{counts["verified"]} verified · {counts["partial"]} partial · {counts["open"]} open</text>'
        )
        out.append(
            f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="5" '
            f'fill="{COLORS["panel"]}" stroke="{COLORS["border"]}"/>'
        )

        cursor = bar_x
        for state in ("verified", "partial", "open"):
            count = counts[state]
            if not count:
                continue
            segment = bar_width * count / total
            out.append(
                f'<rect x="{cursor:.2f}" y="{y}" width="{segment:.2f}" height="{bar_height}" '
                f'fill="{COLORS[state]}"><title>{esc(area["name"])}: {count}/{total} {state}</title></rect>'
            )
            if segment >= 58:
                out.append(
                    f'<text x="{cursor + segment / 2:.2f}" y="{y + 19}" fill="{COLORS["text"]}" '
                    'text-anchor="middle" font-family="ui-sans-serif,system-ui,sans-serif" '
                    f'font-size="11" font-weight="650">{count}/{total}</text>'
                )
            cursor += segment

    out.append(
        f'<text x="24" y="{height - 20}" fill="{COLORS["muted"]}" '
        'font-family="ui-sans-serif,system-ui,sans-serif" font-size="11">'
        'Milestone maturity, not overall project completion. '
        'native_complete remains false until required closure obligations are proven.</text>'
    )
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
    for area in data["areas"]:
        lines += [f"## {area['name']}", "", "| Milestone | State |", "| --- | --- |"]
        for milestone in area["milestones"]:
            lines.append(
                f"| {milestone['name']} | {icon(milestone['state'])} {STATE_LABEL[milestone['state']]} |"
            )
        lines.append("")
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
