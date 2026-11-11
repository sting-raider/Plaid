import { useEffect, useMemo, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { api, CompileEvent, Config, coverFor, Game, PHASES, Progress } from "./api";
import { Boot } from "./Boot";
import { PlaySheet, Saves, SettingsPanel, SettingsTab } from "./settings";
import { Back, Check, Close, Folder, Gear, Grid, Hammer, Logo, Maximize, Minimize, Play, Refresh, Search } from "./icons";
import { useUpdates, type Notice } from "./update";
import { DEV, StageBackdrop } from "./stage";
import "./styles.css";

interface Build { id: string; progress: Progress; logs: string[]; status: "running" | "done" | "failed" | "cancelled"; message?: string; started: number; lastOutput: number }

const win = getCurrentWindow();

function TitleBar() {
  return (
    <div className={`titlebar ${DEV ? "dev" : ""}`}>
      <StageBackdrop />
      <div className="brand"><Logo size={15} />Plaid{DEV && <span className="stage-pill">Dev</span>}</div>
      <div className="drag" data-tauri-drag-region />
      <button className="win-btn" onClick={() => win.minimize()} aria-label="Minimize"><Minimize /></button>
      <button className="win-btn" onClick={() => win.toggleMaximize()} aria-label="Maximize"><Maximize /></button>
      <button className="win-btn close" onClick={() => win.close()} aria-label="Close"><Close /></button>
    </div>
  );
}

function useCover(id: string) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => { let live = true; coverFor(id).then((s) => live && setSrc(s)); return () => { live = false; }; }, [id]);
  return src;
}

function Cover({ game }: { game: Game }) {
  const src = useCover(game.id);
  if (src) return <img src={src} alt="" draggable={false} />;
  return <div className="placeholder"><span className="label">{game.region}</span><b>{game.title}</b></div>;
}

function Status({ game, build }: { game: Game; build?: Build }) {
  if (build?.status === "running") return <><span className="dot busy" />Compiling · {Math.floor(build.progress.percent)}%</>;
  if (!game.compiled) return <><span className="dot" />Not compiled</>;
  return <><span className="dot green" />Ready</>;
}

function Setup({ config, onDone }: { config: Config; onDone: (c: Config) => void }) {
  const [romDir, setRomDir] = useState(config.romDir ?? "");
  const [root, setRoot] = useState(config.plaidRoot);
  const [error, setError] = useState("");
  // the recompiler folder is asked for only when the built-in one is not a Plaid checkout
  const [askRoot, setAskRoot] = useState(false);
  const pick = async (set: (v: string) => void) => { const d = await open({ directory: true }); if (typeof d === "string") set(d); };
  const save = async () => {
    const next = { ...config, romDir, plaidRoot: root };
    try { await api.setConfig(next); onDone(next); } catch (e) { setError(String(e)); if (String(e).includes("not a Plaid checkout")) setAskRoot(true); }
  };
  return (
    <div className="setup">
      <div className="setup-card">
        <div className="stripe" style={{ width: 44 }}><i style={{ background: "var(--n-red)" }} /><i style={{ background: "var(--n-blue)" }} /><i style={{ background: "var(--n-green)" }} /><i style={{ background: "var(--n-yellow)" }} /></div>
        <div>
          <h1>Set up your library</h1>
          <p className="muted" style={{ margin: "6px 0 0" }}>Point Plaid at the folder that holds your N64 ROMs. They stay where they are; Plaid only reads them.</p>
        </div>
        <div className="row" style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}>
          <span className="label">ROM folder</span>
          <button className="picker" onClick={() => pick(setRomDir)}><Folder size={16} /><span className={`path ${romDir ? "" : "faint"}`}>{romDir || "Choose a folder with .z64, .v64 or .n64 files"}</span><span className="faint">Browse</span></button>
        </div>
        {askRoot && <div className="row" style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}>
          <span className="label">Plaid recompiler folder</span>
          <button className="picker" onClick={() => pick(setRoot)}><Folder size={16} /><span className="path mono">{root}</span><span className="faint">Change</span></button>
        </div>}
        {error && <div className="error">{error}</div>}
        <div className="row"><span className="spacer" /><button className="btn primary lg" disabled={!romDir} onClick={save}>Continue</button></div>
      </div>
    </div>
  );
}

function BuildPanel({ build, onCancel }: { build: Build; onCancel: () => void }) {
  const log = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (build.status !== "running") return; const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, [build.status]);
  useEffect(() => { log.current?.scrollTo(0, log.current.scrollHeight); }, [build.logs.length]);
  const secs = Math.floor((now - build.started) / 1000);
  const pct = build.status === "done" ? 100 : build.progress.percent;
  const lit = Math.round((pct / 100) * 32);
  const title = { running: build.progress.label, done: "Native build ready", failed: "Build stopped", cancelled: "Cancelled" }[build.status];
  return (
    <div className="box">
      <div className="box-body">
        <div className="build-head">
          <span className="pct">{String(Math.floor(pct)).padStart(3, " ")}%</span>
          <span style={{ fontWeight: 500 }}>{title}</span>
          <span className="spacer" />
          {build.status === "running" && now - build.lastOutput > 25000 && <span className="faint">Still working. This step can take a few minutes.</span>}
          {build.status === "running" && <><span className="mono faint">{Math.floor(secs / 60)}:{String(secs % 60).padStart(2, "0")}</span><button className="btn ghost" onClick={onCancel}>Cancel</button></>}
        </div>
        <div className={`blocks ${build.status === "done" ? "done" : build.status === "failed" ? "failed" : ""}`}>
          {Array.from({ length: 32 }, (_, i) => <i key={i} className={i < lit ? "on" : ""} />)}
        </div>
        <ul className="steps">
          {PHASES.map((p, i) => {
            const state = build.status === "done" || i < build.progress.phase ? "done" : i === build.progress.phase && build.status === "running" ? "now" : "";
            return <li key={p} className={state}><span className="step-mark">{state === "done" && <Check size={10} />}</span>{p}</li>;
          })}
        </ul>
        {build.message && <div className="error mono" style={{ marginTop: 14, maxHeight: 160, overflow: "auto" }}>{build.message}</div>}
        <div className="log mono" ref={log}>
          {build.logs.map((l, i) => <div key={i} className={l.startsWith("+") ? "cmd" : ""}>{l.length > 220 ? l.slice(0, 220) + " …" : l}</div>)}
        </div>
      </div>
    </div>
  );
}

type GameTab = "overview" | SettingsTab | "saves";

function About({ id }: { id: string }) {
  const [info, setInfo] = useState<Awaited<ReturnType<typeof api.info>> | null>(null);
  useEffect(() => { setInfo(null); api.info(id).then(setInfo).catch(() => {}); }, [id]);
  if (!info?.extract) return null;
  return (
    <div className="game-about">
      <div className="label">About{info.description ? ` · ${info.description}` : ""}</div>
      <p>{info.extract}</p>
      {info.url && <button className="link" onClick={() => openUrl(info.url)}>Read more on Wikipedia</button>}
    </div>
  );
}

type EngineState = { ready: true } | { ready: false; done: number; total: number; error?: string };

function GamePage({ game, build, engine, onBack, onCompile, onCancel, onPlay, onRetryEngine }: {
  game: Game; build?: Build; engine: EngineState; onBack: () => void; onCompile: () => void; onCancel: () => void; onPlay: () => void; onRetryEngine: () => void;
}) {
  const [tab, setTab] = useState<GameTab>("overview");
  const running = build?.status === "running";
  const tabs: [GameTab, string][] = [["overview", "Overview"], ["controls", "Controls"], ["graphics", "Graphics"], ["experimental", "Experimental"], ["saves", "Saves"]];
  return (
    <>
      <div className="header">
        <button className="btn ghost" onClick={onBack} style={{ marginLeft: -10 }}><Back size={16} />Library</button>
      </div>
      <div className="content">
        <div className="game-top">
          <div className="game-cover"><Cover game={game} /></div>
          <div className="game-info">
            <div className="row muted" style={{ gap: 7 }}><Status game={game} build={build} /></div>
            <h1>{game.title}</h1>
            <div className="meta-line">
              <span>{game.region}</span><span className="sep">·</span><span className="mono">{game.gameCode}</span><span className="sep">·</span><span>{game.sizeMb.toFixed(0)} MB</span>
              {game.nativeComplete === true && <><span className="sep">·</span><span>Fully native</span></>}
              {game.nativeComplete === false && <><span className="sep">·</span><span title="Unproven indirect jumps are checked at run time; still no emulation">Run-time dispatch ({game.residualSites} sites)</span></>}
            </div>
            <div className="row" style={{ marginTop: 6 }}>
              {game.compiled && !running && <button className="btn primary lg" onClick={onPlay}><Play size={15} />Play</button>}
              {!engine.ready && !running && <button className={`btn lg ${game.compiled ? "" : "primary"}`} disabled={!engine.error} onClick={onRetryEngine}>
                {engine.error ? <><Refresh size={15} />Retry download</> : <><Hammer size={15} />Downloading recompiler{engine.total ? ` · ${Math.floor((engine.done / engine.total) * 100)}%` : "…"}</>}
              </button>}
              {engine.ready && !game.compiled && !running && <button className="btn primary lg" onClick={() => { setTab("overview"); onCompile(); }}><Hammer size={15} />Compile</button>}
              {engine.ready && game.compiled && !running && <button className="btn lg" onClick={() => { setTab("overview"); onCompile(); }}><Refresh size={15} />Recompile</button>}
            </div>
            {!engine.ready && engine.error && <div className="error">{engine.error}</div>}
          </div>
          <About id={game.id} />
        </div>
        <div className="tabs">{tabs.map(([t, name]) => <button key={t} className={`tab ${tab === t ? "on" : ""}`} onClick={() => setTab(t)}>{name}</button>)}</div>
        <div className="page">
          {tab === "overview" && (
            <>
              {build ? <BuildPanel build={build} onCancel={onCancel} /> : (
                <div className="notice" style={{ fontSize: 13 }}>
                  {game.compiled
                    ? "This game is recompiled to native code for your PC. Recompile after updating Plaid to pick up fixes."
                    : "Plaid reads the game's code, proves where every jump goes, translates it to C and compiles a native executable, with no emulator inside. The first build takes a few minutes; a short test run opens a window at the end."}
                </div>
              )}
              <div className="box">
                <div className="box-head"><span className="label">Cartridge</span></div>
                <div className="box-body">
                  <dl className="facts">
                    <dt>File</dt><dd title={game.path}>{game.fileName}</dd>
                    <dt>Internal name</dt><dd>{game.internalName || "—"}</dd>
                    <dt>Game code</dt><dd className="mono">{game.gameCode} · rev {game.version}</dd>
                    <dt>Format</dt><dd>.{game.byteOrder}{game.byteOrder !== "z64" ? " (converted for the build)" : ""}</dd>
                  </dl>
                </div>
              </div>
            </>
          )}
          {(tab === "controls" || tab === "graphics" || tab === "experimental") && <SettingsPanel game={game} tab={tab} />}
          {tab === "saves" && <Saves game={game} />}
        </div>
      </div>
    </>
  );
}

function AppSettings({ config, onSave }: { config: Config; onSave: (c: Config) => void }) {
  const [tab, setTab] = useState<"general" | SettingsTab>("general");
  const [c, setC] = useState(config);
  const [msg, setMsg] = useState("");
  const [bundled, setBundled] = useState(true);
  useEffect(() => { api.engineBundled().then(setBundled).catch(() => setBundled(false)); }, []);
  const pick = async (key: "romDir" | "plaidRoot") => { const d = await open({ directory: true }); if (typeof d === "string") setC({ ...c, [key]: d }); };
  const tabs: ["general" | SettingsTab, string][] = [["general", "General"], ["controls", "Default controls"], ["graphics", "Default graphics"], ["experimental", "Experimental"]];
  return (
    <>
      <div className="header"><h2>Settings</h2></div>
      <div className="content">
        <div className="tabs" style={{ paddingTop: 4 }}>{tabs.map(([t, name]) => <button key={t} className={`tab ${tab === t ? "on" : ""}`} onClick={() => setTab(t)}>{name}</button>)}</div>
        <div className="page">
          {tab === "general" ? (
            <>
              <div className="box">
                <div className="set-row"><div className="txt"><b>ROM folder</b><span className="mono">{c.romDir}</span></div><button className="btn" onClick={() => pick("romDir")}><Folder size={15} />Change</button></div>
                {!bundled && <div className="set-row"><div className="txt"><b>Recompiler folder</b><span className="mono">{c.plaidRoot}</span></div><button className="btn" onClick={() => pick("plaidRoot")}><Folder size={15} />Change</button></div>}
                <div className="set-row"><div className="txt"><b>Test run after each build</b><span>{c.validationSeconds} seconds</span></div>
                  <input type="range" min={5} max={60} step={5} value={c.validationSeconds} onChange={(e) => setC({ ...c, validationSeconds: +e.target.value })} style={{ width: 200 }} /></div>
              </div>
              {msg && <div className="error">{msg}</div>}
              <div className="row"><button className="btn primary" onClick={() => api.setConfig(c).then(() => { onSave(c); setMsg(""); }).catch((e) => setMsg(String(e)))}>Save</button></div>
            </>
          ) : <SettingsPanel game={null} tab={tab} />}
        </div>
      </div>
    </>
  );
}

type View = "all" | "ready" | "todo" | "settings";

export default function App() {
  const [booted, setBooted] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [games, setGames] = useState<Game[]>([]);
  const [view, setView] = useState<View>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [builds, setBuilds] = useState<Record<string, Build>>({});
  const [playing, setPlaying] = useState<Game | null>(null);
  const [toast, setNotice] = useState<Notice | null>(null);
  const setToast = (t: string | Notice) => setNotice(typeof t === "string" ? { title: t } : t);
  const updates = useUpdates(setToast, booted);

  const [scanning, setScanning] = useState(false);
  const rescan = () => {
    setScanning(true);
    // spin at least one turn so a fast scan still reads as a refresh
    return Promise.all([api.scan().then(setGames).catch((e) => setToast(String(e))), new Promise((r) => setTimeout(r, 600))])
      .finally(() => setScanning(false));
  };

  const startup = async (status: (s: string) => void) => {
    const c = await api.getConfig();
    setConfig(c);
    const u = await updates.checkAll();
    if (c.romDir) { status("Reading cartridges"); await api.scan().then(setGames).catch(() => {}); }
    return u?.behind ? `${u.behind} update${u.behind > 1 ? "s" : ""} available` : u ? "Up to date" : "Offline · skipped update check";
  };

  useEffect(() => {
    const off = listen<CompileEvent>("compile", ({ payload: e }) => {
      setBuilds((all) => {
        const b = all[e.id] ?? { id: e.id, progress: { phase: 0, label: PHASES[0], percent: 0 }, logs: [], status: "running", started: Date.now(), lastOutput: Date.now() };
        const next: Build = { ...b };
        if (e.kind === "progress") next.progress = e.progress;
        if (e.kind === "log") { next.logs = [...b.logs.slice(-400), e.line]; next.lastOutput = Date.now(); }
        if (e.kind === "done") next.status = "done";
        if (e.kind === "failed") { next.status = "failed"; next.message = e.message; }
        if (e.kind === "cancelled") next.status = "cancelled";
        return { ...all, [e.id]: next };
      });
      if (e.kind === "done" || e.kind === "failed" || e.kind === "cancelled") rescan();
      if (e.kind === "done") setToast("Native build ready.");
    });
    return () => { off.then((f) => f()); };
  }, []);

  // a release app downloads its recompiler once, in the background, on first run
  const [engine, setEngine] = useState<EngineState>({ ready: true });
  const getEngine = () => {
    setEngine({ ready: false, done: 0, total: 0 });
    api.installEngine()
      .then(() => setEngine({ ready: true }))
      .catch((e) => setEngine((s) => ({ ...(s.ready ? { done: 0, total: 0 } : s), ready: false, error: String(e) })));
  };
  useEffect(() => { if (booted) api.engineReady().then((r) => { if (!r) getEngine(); }).catch(() => {}); }, [booted]);
  useEffect(() => {
    const off = listen<{ done: number; total: number }>("engine", ({ payload }) => setEngine((s) => (s.ready ? s : { ready: false, ...payload })));
    return () => { off.then((f) => f()); };
  }, []);

  useEffect(() => { if (!toast) return; const t = setTimeout(() => setNotice(null), toast.detail ? 8000 : 4500); return () => clearTimeout(t); }, [toast]);

  const shown = useMemo(() => games.filter((g) =>
    (view === "all" || view === "settings" || (view === "ready" ? g.compiled : !g.compiled)) && g.title.toLowerCase().includes(query.toLowerCase())), [games, view, query]);

  if (!booted) return <Boot work={startup} onDone={() => setBooted(true)} />;
  if (!config) return null;
  if (!config.romDir) return <div className="app"><TitleBar /><Setup config={config} onDone={(c) => { setConfig(c); rescan(); }} /></div>;

  const game = games.find((g) => g.id === selected);
  const compile = (id: string) => {
    setBuilds((all) => ({ ...all, [id]: { id, progress: { phase: 0, label: PHASES[0], percent: 0 }, logs: [], status: "running", started: Date.now(), lastOutput: Date.now() } }));
    api.compile(id).catch((e) => { setToast(String(e)); setBuilds((all) => { const { [id]: _, ...rest } = all; return rest; }); });
  };
  const ready = games.filter((g) => g.compiled).length;
  const nav = (v: View) => { setView(v); setSelected(null); };

  return (
    <div className="app">
      <TitleBar />
      <div className="shell">
        <aside className="sidebar">
          <button className={`side-row ${view === "all" && !game ? "active" : ""}`} onClick={() => nav("all")}><Grid size={15} />All games<span className="count">{games.length}</span></button>
          <button className={`side-row ${view === "ready" && !game ? "active" : ""}`} onClick={() => nav("ready")}><Play size={14} />Ready to play<span className="count">{ready}</span></button>
          <button className={`side-row ${view === "todo" && !game ? "active" : ""}`} onClick={() => nav("todo")}><Hammer size={15} />Not compiled<span className="count">{games.length - ready}</span></button>
          <button className={`side-row ${view === "settings" && !game ? "active" : ""}`} onClick={() => nav("settings")}><Gear size={15} />Settings</button>
          <div className="side-section label">Library</div>
          <div className="side-list">
            {games.map((g) => <SideGame key={g.id} game={g} active={selected === g.id} busy={builds[g.id]?.status === "running"} onClick={() => setSelected(g.id)} />)}
          </div>
          <div className="side-foot">
            <span className={`dot ${updates.dot}`} />
            <span className="side-foot-text" title={updates.label}>{updates.status}</span>
            {updates.control}
          </div>
        </aside>

        <main className="main">
          {game ? (
            <GamePage key={game.id} game={game} build={builds[game.id]} engine={engine} onRetryEngine={getEngine} onBack={() => setSelected(null)} onCompile={() => compile(game.id)}
              onCancel={() => api.cancel().catch((e) => setToast(String(e)))} onPlay={() => setPlaying(game)} />
          ) : view === "settings" ? (
            <AppSettings config={config} onSave={(c) => { setConfig(c); rescan(); setToast("Settings saved."); }} />
          ) : (
            <>
              <div className="header">
                <h2>{{ all: "All games", ready: "Ready to play", todo: "Not compiled" }[view]}</h2>
                <span className="spacer" />
                <div className="search"><Search size={14} /><input className="input" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
                <button className={`icon-btn ${scanning ? "spin" : ""}`} title="Rescan ROM folder" onClick={rescan}><Refresh size={16} /></button>
              </div>
              <div className="content">
                {shown.length === 0 ? (
                  <div className="empty">
                    <Folder size={28} />
                    <div>{games.length ? "Nothing matches." : <>No ROMs found in <span className="mono">{config.romDir}</span></>}</div>
                    {!games.length && <button className="btn" onClick={() => nav("settings")}>Choose another folder</button>}
                  </div>
                ) : (
                  <div className="grid">
                    {shown.map((g) => (
                      <button key={g.id} className="card" onClick={() => setSelected(g.id)} onDoubleClick={() => g.compiled && setPlaying(g)}>
                        <div className="cover"><Cover game={g} /></div>
                        <div className="title">{g.title}</div>
                        <div className="meta"><Status game={g} build={builds[g.id]} /></div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>

      {playing && <PlaySheet game={playing} onClose={() => setPlaying(null)} onSettings={() => { setPlaying(null); setSelected(playing.id); }}
        onPlay={() => { api.play(playing.id).catch((e) => setToast(String(e))); setPlaying(null); }} />}
      {toast && <div className="toast" role="status"><span className={`dot ${toast.error ? "red" : "green"}`} /><div><div>{toast.title}</div>{toast.detail && <div className="toast-detail">{toast.detail}</div>}</div></div>}
    </div>
  );
}

function SideGame({ game, active, busy, onClick }: { game: Game; active: boolean; busy: boolean; onClick: () => void }) {
  const src = useCover(game.id);
  return (
    <button className={`side-row ${active ? "active" : ""}`} onClick={onClick}>
      <span className="thumb" style={{ backgroundImage: src ? `url(${src})` : undefined }} />
      <span className="name">{game.title}</span>
      <span className={`dot ${busy ? "busy" : game.compiled ? "green" : ""}`} />
    </button>
  );
}
