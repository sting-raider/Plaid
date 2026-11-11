import { useEffect, useState } from "react";
import { api, DEFAULTS_ID, Game, SaveFile, Settings } from "./api";
import { ControllerConfig } from "./controller";
import { Folder, Info, Play } from "./icons";

const ASPECTS: [Settings["aspect"], string][] = [
  ["4:3", "Original 4:3"],
  ["16:9", "Widescreen 16:9"],
  ["21:9", "Ultrawide 21:9"],
  ["stretch", "Stretch to window"],
];

export const Switch = ({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) => (
  <button className={`switch ${on ? "on" : ""}`} onClick={() => onChange(!on)} aria-pressed={on} />
);

function Graphics({ s, set }: { s: Settings; set: (p: Partial<Settings>) => void }) {
  return (
    <div className="box">
      <div className="set-row"><div className="txt"><b>N64 mode</b><span>The original look: 4:3 at the console's own resolution, no upscaling.</span></div><Switch on={s.n64Mode} onChange={(n64Mode) => set({ n64Mode })} /></div>
      <div className={`set-row ${s.n64Mode ? "disabled" : ""}`}>
        <div className="txt"><b>Aspect ratio</b><span>How the picture fills the window.</span></div>
        <select className="input" value={s.aspect} onChange={(e) => set({ aspect: e.target.value as Settings["aspect"] })}>
          {ASPECTS.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
      </div>
      <div className={`set-row ${s.n64Mode ? "disabled" : ""}`}>
        <div className="txt"><b>Internal resolution</b><span>{s.resolutionScale}× native ({240 * s.resolutionScale}p)</span></div>
        <input type="range" min={1} max={8} value={s.resolutionScale} onChange={(e) => set({ resolutionScale: +e.target.value })} style={{ width: 200 }} />
      </div>
      <div className="set-row"><div className="txt"><b>V-Sync</b><span>Lock presentation to the display to avoid tearing.</span></div><Switch on={s.vsync} onChange={(vsync) => set({ vsync })} /></div>
      <div className="set-row"><div className="txt"><b>Start in fullscreen</b><span>Alt+Enter toggles while playing.</span></div><Switch on={s.fullscreen} onChange={(fullscreen) => set({ fullscreen })} /></div>
    </div>
  );
}

export function Saves({ game }: { game: Game }) {
  const [files, setFiles] = useState<SaveFile[] | null>(null);
  useEffect(() => { api.saves(game.id).then(setFiles).catch(() => setFiles([])); }, [game.id]);
  return (
    <div className="box">
      <div className="box-head"><span className="label">Save data</span><span className="spacer" />
        <button className="btn" onClick={() => api.openFolder(game.saveDir)}><Folder size={15} />Open folder</button></div>
      <div className="box-body">
        <div className="mono faint" style={{ marginBottom: 12, userSelect: "text" }}>{game.saveDir}</div>
        {files === null ? <span className="faint">Reading…</span> : files.length === 0 ? <span className="faint">No saves yet. They appear after the game saves for the first time.</span> : (
          <dl className="facts">{files.flatMap((f) => [<dt key={f.name}>{f.kind}</dt>, <dd key={f.name + "v"} className="mono">{f.name} · {(f.bytes / 1024).toFixed(1)} KB</dd>])}</dl>
        )}
      </div>
    </div>
  );
}

export type SettingsTab = "controls" | "graphics";

/** Controls or graphics settings for a game, or the defaults when `game` is null. */
export function SettingsPanel({ game, tab }: { game: Game | null; tab: SettingsTab }) {
  const id = game?.id ?? DEFAULTS_ID;
  const [s, setS] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(true);
  useEffect(() => { api.settings(id).then((v) => { setS(v); setSaved(true); }); }, [id]);
  if (!s) return null;
  const set = (p: Partial<Settings>) => { setS({ ...s, ...p }); setSaved(false); };
  const inherit = game !== null && s.useDefaults;
  return (
    <>
      <div className="row">
        {game && (
          <label className="row"><Switch on={!s.useDefaults} onChange={(v) => set({ useDefaults: !v })} />
            <span className="muted">Custom settings for this game</span></label>
        )}
        <span className="spacer" />
        {!saved && <span className="faint">Unsaved changes</span>}
        <button className="btn primary" disabled={saved} onClick={() => api.saveSettings(id, s).then(() => setSaved(true))}>Save</button>
      </div>
      {inherit ? (
        <div className="notice"><Info size={15} /><span>This game follows the default settings. Turn on custom settings to change them for this game only.</span></div>
      ) : (
        <>
          {tab === "controls" && <ControllerConfig s={s} set={set} />}
          {tab === "graphics" && <Graphics s={s} set={set} />}
        </>
      )}
    </>
  );
}

const DEVICE_NAMES: Record<string, string> = {
  keyboard: "Keyboard", xbox: "Xbox controller", ds4: "DualShock 4", dualsense: "DualSense",
  switchpro: "Switch Pro Controller", n64usb: "N64 USB controller", generic: "Generic gamepad",
};

/** Shown before launch: who is plugged in and how the picture is set up. */
export function PlaySheet({ game, onClose, onPlay, onSettings }: { game: Game; onClose: () => void; onPlay: () => void; onSettings: () => void }) {
  const [s, setS] = useState<Settings | null>(null);
  useEffect(() => { api.settings(game.id).then(async (own) => setS(own.useDefaults ? await api.settings(DEFAULTS_ID) : own)); }, [game.id]);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === "Enter") onPlay(); if (e.key === "Escape") onClose(); }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, []);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog">
        <div className="dialog-body">
          <div className="label">Ready to play</div>
          <h2 style={{ fontSize: 18 }}>{game.title}</h2>
          <div className="box">
            {s?.players.map((p, i) => (
              <div className="set-row" key={i} style={{ padding: "9px 12px" }}>
                <span className={`dot ${p.connected ? "green" : ""}`} />
                <span className="pixel" style={{ width: 70 }}>Player {i + 1}</span>
                <span className={p.connected ? "" : "faint"}>{p.connected ? DEVICE_NAMES[p.type] : "Not connected"}</span>
              </div>
            ))}
          </div>
          <div className="faint">{s?.n64Mode ? "N64 mode" : <>{ASPECTS.find((a) => a[0] === s?.aspect)?.[1]} · {s?.resolutionScale}× resolution</>} · {s?.fullscreen ? "fullscreen" : "windowed"}</div>
        </div>
        <div className="dialog-foot">
          <button className="btn ghost" onClick={onSettings}>Settings</button>
          <span className="spacer" />
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={onPlay}><Play size={14} />Launch</button>
        </div>
      </div>
    </div>
  );
}
