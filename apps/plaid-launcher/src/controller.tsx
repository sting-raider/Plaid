import { useEffect, useRef, useState } from "react";
import { bindingLabel, defaultBindings, Device, newPlayer, Player, Settings } from "./api";

const TYPES: [Device, string][] = [
  ["keyboard", "Keyboard"],
  ["xbox", "Xbox controller"],
  ["ds4", "DualShock 4"],
  ["dualsense", "DualSense"],
  ["switchpro", "Switch Pro Controller"],
  ["n64usb", "N64 USB controller"],
  ["generic", "Generic gamepad"],
];

const GROUPS: { title: string; color?: string; keys: [string, string][] }[] = [
  { title: "Control stick", keys: [["stickUp", "Up"], ["stickDown", "Down"], ["stickLeft", "Left"], ["stickRight", "Right"]] },
  { title: "D-pad", keys: [["dUp", "Up"], ["dDown", "Down"], ["dLeft", "Left"], ["dRight", "Right"]] },
  { title: "Buttons", keys: [["a", "A"], ["b", "B"], ["start", "Start"], ["z", "Z trigger"]] },
  { title: "Shoulders", keys: [["l", "L"], ["r", "R"]] },
  { title: "C buttons", color: "var(--n-yellow)", keys: [["cUp", "C Up"], ["cDown", "C Down"], ["cLeft", "C Left"], ["cRight", "C Right"]] },
];

export function keyName(key: string) {
  const names: Record<string, string> = { ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→", " ": "Space" };
  return names[key] ?? (key.length === 1 ? key.toUpperCase() : key);
}

/** The gamepad a player slot reads: the slot's index among connected pads. */
function padFor(slot: number): Gamepad | null {
  return navigator.getGamepads().filter((p): p is Gamepad => !!p)[slot] ?? null;
}

function useGamepads() {
  const [pads, setPads] = useState<string[]>([]);
  useEffect(() => {
    const read = () => setPads(navigator.getGamepads().filter((p): p is Gamepad => !!p).map((p) => p.id.replace(/\(.*?\)/g, "").trim() || "Gamepad"));
    read();
    const t = setInterval(read, 1000);
    return () => clearInterval(t);
  }, []);
  return pads;
}

/** Which N64 inputs are held right now, and the stick position, for the live diagram. */
function useLive(player: Player, slot: number, paused: boolean) {
  const [held, setHeld] = useState<Set<string>>(new Set());
  const [stick, setStick] = useState({ x: 0, y: 0 });
  const keys = useRef(new Set<string>());
  useEffect(() => {
    if (player.type !== "keyboard") return;
    const down = (e: KeyboardEvent) => keys.current.add(keyName(e.key));
    const up = (e: KeyboardEvent) => keys.current.delete(keyName(e.key));
    const clear = () => keys.current.clear();
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); window.removeEventListener("blur", clear); };
  }, [player.type]);
  useEffect(() => {
    let frame = 0;
    const tick = () => {
      const pad = player.type === "keyboard" ? null : padFor(slot);
      const level = (v: string): number => {
        if (!v) return 0;
        if (player.type === "keyboard") return keys.current.has(v) ? 1 : 0;
        if (!pad) return 0;
        const b = /^Button (\d+)$/.exec(v);
        if (b) return pad.buttons[+b[1]]?.value ?? 0;
        const a = /^Axis (\d+)([+-])$/.exec(v);
        if (!a) return 0;
        const x = (pad.axes[+a[1]] ?? 0) * (a[2] === "+" ? 1 : -1);
        return x > player.deadzone / 100 ? Math.min(1, x * (player.range / 100)) : 0;
      };
      const next = new Set<string>();
      for (const [k, v] of Object.entries(player.bindings)) if (!paused && level(v) > 0.5) next.add(k);
      const b = player.bindings;
      setStick({ x: paused ? 0 : level(b.stickRight) - level(b.stickLeft), y: paused ? 0 : level(b.stickDown) - level(b.stickUp) });
      setHeld((old) => (old.size === next.size && [...next].every((k) => old.has(k)) ? old : next));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [player, slot, paused]);
  return { held, stick };
}

/** Waits for the next key or gamepad input and reports it in binding form. */
function useCapture(target: string | null, type: Device, slot: number, onInput: (value: string | null) => void) {
  const cb = useRef(onInput);
  cb.current = onInput;
  useEffect(() => {
    if (!target) return;
    const key = (e: KeyboardEvent) => {
      e.preventDefault();
      if (e.key === "Escape") return cb.current(null);
      if (type === "keyboard") cb.current(keyName(e.key));
    };
    window.addEventListener("keydown", key);
    let frame = 0;
    if (type !== "keyboard") {
      const pad = padFor(slot);
      const startButtons = pad?.buttons.map((b) => b.pressed) ?? [];
      const startAxes = pad?.axes.slice() ?? [];
      const poll = () => {
        const p = padFor(slot);
        if (p) {
          const b = p.buttons.findIndex((btn, i) => btn.pressed && !startButtons[i]);
          if (b >= 0) return cb.current(`Button ${b}`);
          const a = p.axes.findIndex((v, i) => Math.abs(v) > 0.6 && Math.abs(startAxes[i] ?? 0) < 0.3);
          if (a >= 0) return cb.current(`Axis ${a}${p.axes[a] > 0 ? "+" : "-"}`);
        }
        frame = requestAnimationFrame(poll);
      };
      frame = requestAnimationFrame(poll);
    }
    return () => { window.removeEventListener("keydown", key); cancelAnimationFrame(frame); };
  }, [target, type, slot]);
}

/** An original top-down drawing of a three-handled N64-style controller. */
export function N64Pad({ held, stick, focus }: { held: Set<string>; stick: { x: number; y: number }; focus: string | null }) {
  const on = (k: string) => held.has(k) || focus === k;
  const face = (k: string, color: string) => ({
    fill: color, fillOpacity: on(k) ? 1 : 0.28, stroke: on(k) ? "#fff" : color, strokeOpacity: on(k) ? 0.9 : 0.55, strokeWidth: 1.5,
    style: { transition: "fill-opacity 60ms, stroke 60ms" },
  });
  const grey = (k: string) => ({ fill: on(k) ? "#f1f3f7" : "#1c1c20", stroke: on(k) ? "#fff" : "rgba(255,255,255,0.22)", strokeWidth: 1.2 });
  const body = (
    <>
      <rect x="36" y="46" width="368" height="118" rx="58" />
      <rect x="58" y="110" width="92" height="176" rx="46" />
      <rect x="184" y="120" width="72" height="180" rx="36" />
      <rect x="290" y="110" width="92" height="176" rx="46" />
    </>
  );
  const c = (k: string, cx: number, cy: number, rot: number) => (
    <g>
      <circle cx={cx} cy={cy} r="11" {...face(k, "#f5c542")} />
      <polygon points="0,-4.5 4,2.5 -4,2.5" transform={`translate(${cx} ${cy}) rotate(${rot})`} fill={on(k) ? "#000" : "#f5c542"} fillOpacity={on(k) ? 0.8 : 0.9} />
    </g>
  );
  return (
    <svg viewBox="0 0 440 320" role="img" aria-label="Controller input test">
      <rect x="56" y="34" width="100" height="26" rx="10" {...grey("l")} />
      <rect x="284" y="34" width="100" height="26" rx="10" {...grey("r")} />
      <rect x="198" y="286" width="44" height="24" rx="7" {...grey("z")} />
      <text x="220" y="302" textAnchor="middle" fontFamily="Silkscreen" fontSize="9" fill={on("z") ? "#000" : "#6b6b6f"}>Z</text>
      <g fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="3">{body}</g>
      <g fill="#0d0d10">{body}</g>
      {/* D-pad */}
      <rect x="95" y="103" width="18" height="18" fill="#1c1c20" />
      <rect x="95" y="80" width="18" height="24" rx="3" {...grey("dUp")} />
      <rect x="95" y="120" width="18" height="24" rx="3" {...grey("dDown")} />
      <rect x="72" y="103" width="24" height="18" rx="3" {...grey("dLeft")} />
      <rect x="112" y="103" width="24" height="18" rx="3" {...grey("dRight")} />
      {/* Start */}
      <circle cx="220" cy="104" r="10" {...face("start", "#e5484d")} />
      {/* stick */}
      <circle cx="220" cy="190" r="30" fill="#070709" stroke="rgba(255,255,255,0.14)" />
      <circle cx={220 + stick.x * 12} cy={190 + stick.y * 12} r="17" fill={stick.x || stick.y ? "#f1f3f7" : "#26262b"} stroke="rgba(255,255,255,0.3)" style={{ transition: "cx 50ms, cy 50ms" }} />
      {/* A / B */}
      <circle cx="330" cy="130" r="15" {...face("a", "#3e7bfa")} />
      <text x="330" y="134.5" textAnchor="middle" fontFamily="Silkscreen" fontSize="12" fill={on("a") ? "#fff" : "#9db8ff"}>A</text>
      <circle cx="300" cy="100" r="15" {...face("b", "#30a46c")} />
      <text x="300" y="104.5" textAnchor="middle" fontFamily="Silkscreen" fontSize="12" fill={on("b") ? "#fff" : "#8fd9b3"}>B</text>
      {/* C buttons */}
      {c("cUp", 362, 64, 0)}
      {c("cDown", 362, 108, 180)}
      {c("cLeft", 340, 86, -90)}
      {c("cRight", 384, 86, 90)}
    </svg>
  );
}

export function ControllerConfig({ s, set }: { s: Settings; set: (p: Partial<Settings>) => void }) {
  const [slot, setSlot] = useState(0);
  const [listening, setListening] = useState<string | null>(null);
  const pads = useGamepads();
  const player = s.players[slot];
  const setPlayer = (p: Partial<Player>) => set({ players: s.players.map((old, i) => (i === slot ? { ...old, ...p } : old)) });
  const live = useLive(player, slot, listening !== null);
  useCapture(listening, player.type, slot, (value) => {
    if (listening && value) setPlayer({ bindings: { ...player.bindings, [listening]: value } });
    setListening(null);
  });
  const pad = player.type === "keyboard" ? null : pads[slot];

  const group = (g: (typeof GROUPS)[number]) => (
    <div className="group" key={g.title}>
      <div className="label">{g.color && <span className="dot" style={{ background: g.color }} />}{g.title}</div>
      {g.keys.map(([k, name]) => {
        const value = player.bindings[k] ?? "";
        return (
          <div className={`bind ${live.held.has(k) ? "lit" : ""}`} key={k}>
            <span>{name}</span>
            <button
              className={`key ${listening === k ? "listen" : value ? "" : "empty"}`}
              onClick={() => setListening(k)}
              onContextMenu={(e) => { e.preventDefault(); setPlayer({ bindings: { ...player.bindings, [k]: "" } }); }}
              title="Click to rebind, right-click to clear"
            >
              {listening === k ? "Press input" : value ? bindingLabel(player.type, value) : "Unbound"}
            </button>
          </div>
        );
      })}
      {g.title === "Control stick" && (
        <>
          <div className="slider"><div className="row"><span className="faint">Dead zone</span><span>{player.deadzone}%</span></div>
            <input type="range" min={0} max={40} value={player.deadzone} onChange={(e) => setPlayer({ deadzone: +e.target.value })} /></div>
          <div className="slider"><div className="row"><span className="faint">Range</span><span>{player.range}%</span></div>
            <input type="range" min={50} max={150} value={player.range} onChange={(e) => setPlayer({ range: +e.target.value })} /></div>
        </>
      )}
    </div>
  );

  return (
    <>
      <div className="ctl-top">
        <div className="players">
          {s.players.map((p, i) => (
            <button key={i} className={slot === i ? "on" : ""} onClick={() => { setSlot(i); setListening(null); }}>
              <span className={`dot ${p.connected ? "green" : ""}`} />Player {i + 1}
            </button>
          ))}
        </div>
        <label className="row" style={{ marginLeft: 6 }}>
          <button className={`switch ${player.connected ? "on" : ""}`} onClick={() => setPlayer({ connected: !player.connected })} />
          <span className="muted">Connected</span>
        </label>
        <span className="spacer" />
        <select className="input" value={player.type} onChange={(e) => { const type = e.target.value as Device; setPlayer({ type, bindings: defaultBindings(type) }); }}>
          {TYPES.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <button className="btn ghost" onClick={() => setPlayer(newPlayer(player.connected, player.type))}>Restore defaults</button>
        <button className="btn ghost" onClick={() => setPlayer({ bindings: Object.fromEntries(Object.keys(player.bindings).map((k) => [k, ""])) })}>Clear</button>
      </div>
      <div className="ctl-grid">
        <div>{group(GROUPS[0])}{group(GROUPS[1])}</div>
        <div className="pad-stage">
          <N64Pad held={live.held} stick={live.stick} focus={listening} />
          <div className="row" style={{ gap: 7 }}>
            <span className={`dot ${player.type === "keyboard" || pad ? "green" : ""}`} />
            <span className="pixel faint">
              {player.type === "keyboard" ? "Keyboard · press keys to test" : pad ? `${pad} · press buttons to test` : `No gamepad for player ${slot + 1}`}
            </span>
          </div>
        </div>
        <div>{group(GROUPS[2])}{group(GROUPS[3])}{group(GROUPS[4])}</div>
      </div>
    </>
  );
}
