// The update button, modelled on T3 Code's SidebarUpdatePill (pingdotgg/t3code, MIT):
// check -> download on click (progress ring) -> "restart to install" on click.
import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { ask } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type UpdateInfo } from "./api";
import { DEV } from "./stage";
import { Check, CircleArrowUp, Download, ExternalLink, Refresh, RotateCw } from "./icons";

export type Notice = { title: string; detail?: ReactNode; error?: boolean };

const REPO = "https://github.com/sting-raider/Plaid";
const FIRST_CHECK_MS = 15_000; // T3 Code's cadence: shortly after start, then every 4 minutes
const CHECK_EVERY_MS = 4 * 60_000;

type Phase = "idle" | "downloading" | "downloaded" | "installing";
type Failure = { step: "recompiler" | "download" | "install"; message: string } | null;

const releaseUrl = (version: string) => `${REPO}/releases/tag/launcher-v${version}`;

/** "today" or "3d ago" from the feed date; Tauri hands it over as "YYYY-MM-DD ...". */
function age(date: string | undefined): string | null {
  const day = /^(\d{4})-(\d{2})-(\d{2})/.exec(date ?? "");
  if (!day) return null;
  const now = new Date();
  const days = Math.round((Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) - Date.UTC(+day[1], +day[2] - 1, +day[3])) / 86_400_000);
  return days <= 0 ? "today" : `${days}d ago`;
}

export function useUpdates(notify: (n: Notice) => void, background: boolean) {
  const [plaid, setPlaid] = useState<UpdateInfo | null>(null);
  const [offline, setOffline] = useState(false);
  const [app, setApp] = useState<Update | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [pct, setPct] = useState(0);
  const [failed, setFailed] = useState<Failure>(null);
  const [checking, setChecking] = useState(false);
  const [pending, setPending] = useState(false);
  // a download in flight or a downloaded update must not be swapped out by a background check
  const locked = useRef(false);

  /** Checks main for recompiler changes and GitHub releases for a new app. */
  const checkAll = async () => {
    if (locked.current) return null;
    const timeout = new Promise<null>((r) => setTimeout(() => r(null), 6000));
    const [u, a] = await Promise.all([
      Promise.race([api.checkUpdates().catch(() => null), timeout]),
      DEV ? null : check().catch(() => null), // dev builds never replace themselves with a release
    ]);
    if (locked.current) return u;
    setPlaid(u);
    setOffline(!u && !a);
    setApp(a);
    return u;
  };
  const checkRef = useRef(checkAll);
  checkRef.current = checkAll;

  useEffect(() => {
    if (!background) return;
    const first = setTimeout(() => checkRef.current(), FIRST_CHECK_MS);
    const every = setInterval(() => checkRef.current(), CHECK_EVERY_MS);
    return () => { clearTimeout(first); clearInterval(every); };
  }, [background]);

  const behind = plaid?.behind ?? 0;
  const action: "check" | "download" | "install" =
    phase === "downloaded" || phase === "installing" ? "install" : app || behind ? "download" : "check";

  const label =
    checking ? "Checking for updates…"
    : phase === "downloading" ? `Downloading update ${app?.version ?? ""} · ${pct}%`
    : phase === "installing" ? `Installing ${app?.version ?? "update"}. Plaid restarts by itself.`
    : failed?.step === "install" && app ? `Install failed for ${app.version}. Click to retry.`
    : phase === "downloaded" && app ? `Update ${app.version} downloaded. Click to restart and install.`
    : failed?.step === "recompiler" ? "Recompiler update failed. Click to retry."
    : failed ? `Download failed${app ? ` for ${app.version}` : ""}. Click to retry.`
    : app ? `Update ${app.version} ready to download`
    : behind ? `${behind} recompiler change${behind > 1 ? "s" : ""} ready`
    : offline ? "Offline · could not check for updates"
    : plaid ? `Up to date · ${plaid.current}` : "Up to date";

  const dot = failed ? "red" : action !== "check" ? "yellow" : offline ? "" : "green";
  // the footer has room for a few words; the button's label and the popover say the rest
  const status =
    checking ? "Checking…"
    : phase === "downloading" ? `Downloading · ${pct}%`
    : phase === "installing" ? "Installing…"
    : failed ? "Update failed"
    : action === "install" ? "Restart to update"
    : action === "download" ? (app ? `Update ${app.version} available` : "Recompiler update available")
    : offline ? "Offline"
    : plaid ? `Up to date · ${plaid.current}` : "Up to date";

  const download = async () => {
    locked.current = true;
    setFailed(null);
    try {
      if (behind) {
        await api.updatePlaid().catch((e) => { throw { step: "recompiler", message: String(e) }; });
        setPlaid(plaid ? { ...plaid, behind: 0, changes: [] } : plaid);
        if (!app) {
          notify({ title: "Recompiler updated", detail: "Games pick up the changes on their next compile." });
          locked.current = false;
          return;
        }
      }
      if (app) {
        let total = 0, got = 0;
        setPct(0);
        setPhase("downloading");
        await app.download((e) => {
          if (e.event === "Started") total = e.data.contentLength ?? 0;
          if (e.event === "Progress" && total) { got += e.data.chunkLength; setPct(Math.min(100, Math.round((got / total) * 100))); }
        });
        setPhase("downloaded");
        notify({
          title: "Update downloaded",
          detail: <>Restart Plaid from the update button to install it.{" "}
            <button className="link" onClick={() => openUrl(releaseUrl(app.version))}>Read more <ExternalLink /></button></>,
        });
      }
    } catch (e) {
      const f = (e as Failure)?.step ? (e as Failure)! : { step: "download" as const, message: String(e) };
      setPhase("idle");
      setFailed(f);
      locked.current = false;
      notify({ title: f.step === "recompiler" ? "Could not update the recompiler" : "Could not download update", detail: f.message, error: true });
    }
  };

  const install = async () => {
    if (!app) return;
    const ok = await ask(`Install update ${app.version} and restart Plaid?\n\nA build in progress will stop. Games you are playing keep running.`,
      { title: "Restart to update", kind: "info", okLabel: "Restart and install", cancelLabel: "Not now" }).catch(() => false);
    if (!ok) return;
    setFailed(null);
    setPhase("installing");
    try {
      // the installer runs silently and reopens Plaid itself (/R); relaunch covers platforms that return
      await app.install();
      await relaunch();
    } catch (e) {
      setPhase("downloaded");
      setFailed({ step: "install", message: String(e) });
      notify({ title: "Could not install update", detail: String(e), error: true });
    }
  };

  const onClick = async () => {
    if (pending || checking || phase === "downloading" || phase === "installing") return;
    setPending(true);
    try {
      if (action === "install") await install();
      else if (action === "download") await download();
      else {
        setChecking(true);
        await Promise.all([checkAll(), new Promise((r) => setTimeout(r, 600))]); // one full turn, so a fast check still reads as done
        setChecking(false);
      }
    } finally { setPending(false); }
  };

  const icon =
    checking || phase === "installing" ? <Refresh size={16} />
    : phase === "downloading" ? <DownloadRing pct={pct} />
    : action === "install" ? <span className="upd-glyph"><RotateCw size={16} /><span className="upd-check"><Check size={8} /></span></span>
    : app ? <span className="upd-glyph"><Download size={16} /><span className="upd-dot" /></span>
    : behind ? <CircleArrowUp size={16} />
    : <Refresh size={16} />;

  const control = (
    <div className="update-wrap">
      {action !== "check" && <ReleaseNotes app={app} plaid={plaid} title={label} error={failed?.message} available={action === "download" && phase === "idle" && !failed} />}
      <button
        className={`icon-btn update-btn ${action !== "check" || phase === "downloading" ? "active" : ""} ${checking || phase === "installing" ? "spin" : ""}`}
        aria-label={label}
        title={action === "check" ? label : undefined}
        aria-disabled={checking || phase === "downloading" || phase === "installing" || undefined}
        onClick={onClick}
      >
        {icon}
        {failed && <span className="upd-error" />}
      </button>
    </div>
  );

  return { label, status, dot, control, checkAll };
}

/** T3 Code's downloading icon: a 32 px progress ring around the download glyph. */
function DownloadRing({ pct }: { pct: number }) {
  const r = 14, c = 2 * Math.PI * r;
  return (
    <span className="upd-ring">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r={r} fill="none" className="track" strokeWidth="1.5" />
        <circle cx="16" cy="16" r={r} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} className="bar" />
      </svg>
      <Download size={14} />
    </span>
  );
}

function ReleaseNotes({ app, plaid, title, error, available }: { app: Update | null; plaid: UpdateInfo | null; title: string; error?: string; available: boolean }) {
  const notes = (app?.body ?? "").split(/\r?\n/).map((l) => l.replace(/^\s*[-*]\s*/, "").trim()).filter(Boolean);
  const when = age(app?.date);
  const behind = plaid?.behind ?? 0;
  return (
    <div className="update-panel" role="dialog" aria-label="Update release notes"><div className="update-card">
      <div>
        <div className="update-head">{available && app ? "Update ready to download" : title}</div>
        {available && app && <div className="update-meta">{when ? `${app.version} · ${when}` : app.version}</div>}
        {error && <div className="update-error">{error}</div>}
      </div>
      <div className="update-body">
        {app && <section>
          {behind > 0 && <div className="update-sub">Plaid app {app.version}</div>}
          {notes.length > 0 && <ul>{notes.map((n, i) => { const m = /^\*\*([^*]+)\*\*\s*(.*)$/.exec(n); return <li key={i}>{m ? <><strong>{m[1]}</strong> {m[2]}</> : n}</li>; })}</ul>}
          <button className="update-link" onClick={() => openUrl(releaseUrl(app.version))}>View release on GitHub <ExternalLink /></button>
        </section>}
        {behind > 0 && plaid && <section>
          <div className="update-sub">Recompiler · {behind} change{behind > 1 ? "s" : ""} on main</div>
          <ul>{plaid.changes.map((c) => <li key={c.sha}>{c.subject} <span className="update-meta">{c.sha} · {c.when}</span></li>)}</ul>
          {plaid.changes.length < behind && <button className="update-link" onClick={() => openUrl(`${REPO}/commits/main`)}>{behind - plaid.changes.length} more on GitHub <ExternalLink /></button>}
        </section>}
      </div>
    </div></div>
  );
}
