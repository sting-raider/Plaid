---
name: plaid-launcher
description: Plaid launcher app (apps/plaid-launcher, Tauri + React). Use when changing its UI, its update flow, or publishing a launcher release.
---

# Plaid launcher

The launcher is a Tauri 2 + React app on branch `claude/launcher`. Its bar is T3 Code's desktop app (MIT, `pingdotgg/t3code`): quiet, precise UI, an honest update flow, terse release notes. Ownership: the launcher is ours; the game runtime (`runtime/`, `runtime/rt64`) and the recompiler belong to backend workers, so a launcher feature that needs runtime support ships only after that support is on `main`.

## Shipping a release

1. Every user-visible claim is **verified** in the installed build by hand: launch it, use the feature, see it work. A feature that depends on unlanded backend work is not in the release.
2. Write `apps/plaid-launcher/release-notes/<version>.md` in the notes format below.
3. Bump `version` in `src-tauri/tauri.conf.json` and `package.json`; commit; push `claude/launcher`.
4. Run `python apps/plaid-launcher/release.py apps/plaid-launcher/release-notes/<version>.md`. It builds, signs (key at `~/.tauri/plaid-launcher.key`), publishes `launcher-v<version>` as the latest GitHub release and uploads `latest.json`, which installed apps poll.
5. Done when the feed (`https://github.com/sting-raider/Plaid/releases/latest/download/latest.json`) serves the new version and an installed older build offers it and updates to it.

## Release notes format

Modelled on T3 Code's `scripts/generate-release-notes.ts`:

- At most 7 bullets, each `- **Short feature name.** One sentence, 20 words or fewer, in the player's words.`
- A bullet earns its place as a new capability, a removed limitation or a large time saving. Minor fixes fold into one closing line: `Plus N more fixes.`
- `## Known limitations` lists what a player might expect but will not get yet, plainly.
- Plain and factual: the reader learns what changed and what to do.

The in-app panel shows the same bullets (release.py strips the Markdown).

## Update control (sidebar footer)

One round icon button (`icon-btn` styling, 32 px) whose icon tracks the update state, T3's `SidebarUpdatePill` pattern:

| State | Icon | Click |
|---|---|---|
| up to date | refresh | check now (icon spins while checking) |
| checking | refresh, spinning | none |
| available | arrow-up with a dot badge | download and install, then relaunch |
| downloading | progress ring, percentage in the status text | none |
| error | refresh with a red dot | retry; the toast names what failed |

- Hover (or keyboard focus) opens the what's-new popover after ~80 ms and keeps it open across a 150 ms close delay; the click always performs the action, never toggles the popover.
- Two update sources feed one control: app releases (Tauri updater) and recompiler changes (`origin/main` commits, from `check_updates`). The popover lists both.
- Updates install with `installMode: "quiet"`; progress shows in Plaid's own UI.

## Motion and polish

- Popovers and tooltips: fade plus `scale(0.98)` to `scale(1)`, 150 ms, `var(--ease)`; origin at the trigger; shadow `0 16px 40px -18px rgb(0 0 0 / 55%)`.
- Spinners rotate only while work is actually running, with a 600 ms minimum so a fast operation still reads as done.
- Every animation has a `@media (prefers-reduced-motion: reduce)` fallback with no movement.
- Icons come from `src/icons.tsx` (stroke icons, 16 px in controls); controls reuse `.btn`, `.icon-btn`, `.link`, `.input` from `src/styles.css`.
- Focus is visible on every control (`:focus-visible` ring); icon-only buttons carry an `aria-label`.
- Toasts are short and specific: a title of what happened ("Could not check for updates") and the error text as detail.
