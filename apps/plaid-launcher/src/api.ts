import { invoke } from "@tauri-apps/api/core";

export interface Config {
  romDir: string | null;
  plaidRoot: string;
  validationSeconds: number;
}

export interface Game {
  id: string;
  title: string;
  fileName: string;
  path: string;
  internalName: string;
  gameCode: string;
  region: string;
  version: number;
  byteOrder: "z64" | "v64" | "n64";
  sizeMb: number;
  compiled: boolean;
  nativeComplete: boolean | null;
  residualSites: number | null;
  saveDir: string;
}

export interface Progress {
  phase: number;
  label: string;
  percent: number;
}

export type CompileEvent =
  | { kind: "progress"; id: string; progress: Progress }
  | { kind: "log"; id: string; line: string }
  | { kind: "done"; id: string }
  | { kind: "failed"; id: string; message: string }
  | { kind: "cancelled"; id: string };

export interface SaveFile {
  name: string;
  kind: string;
  bytes: number;
}

/** Mirrors PHASES in src-tauri/src/progress.rs. */
export const PHASES = [
  "Preparing the recompiler",
  "Reading the ROM header",
  "Finding code in the ROM",
  "Identifying libultra functions",
  "Discovering code",
  "Proving control flow",
  "Tracing the boot in a reference emulator",
  "Translating MIPS to C",
  "Recompiling RSP microcode",
  "Compiling native code",
  "Linking and first run",
];

export type Device = "keyboard" | "xbox" | "ds4" | "dualsense" | "switchpro" | "n64usb" | "generic";

export interface Player {
  connected: boolean;
  type: Device;
  bindings: Record<string, string>;
  deadzone: number;
  range: number;
}

export interface Settings {
  useDefaults: boolean;
  players: Player[];
  aspect: "4:3" | "16:9" | "21:9" | "stretch";
  resolutionScale: number;
  vsync: boolean;
  fullscreen: boolean;
  /** Original console look: 4:3 at native resolution; overrides aspect and resolution. */
  n64Mode: boolean;
  experimental: Record<string, boolean>;
}

export const N64_INPUTS: [string, string][] = [
  ["a", "A"], ["b", "B"], ["z", "Z trigger"], ["start", "Start"],
  ["l", "L"], ["r", "R"],
  ["cUp", "C ▲"], ["cDown", "C ▼"], ["cLeft", "C ◀"], ["cRight", "C ▶"],
  ["dUp", "D-pad ▲"], ["dDown", "D-pad ▼"], ["dLeft", "D-pad ◀"], ["dRight", "D-pad ▶"],
  ["stickUp", "Stick ▲"], ["stickDown", "Stick ▼"], ["stickLeft", "Stick ◀"], ["stickRight", "Stick ▶"],
];

/** The runtime's built-in keyboard layout (runtime/rt64/plaid_rt64.cpp). */
const KEYBOARD: Record<string, string> = {
  a: "X", b: "C", z: "Z", start: "Enter", l: "Q", r: "E",
  cUp: "I", cDown: "K", cLeft: "J", cRight: "L",
  dUp: "W", dDown: "S", dLeft: "A", dRight: "D",
  stickUp: "↑", stickDown: "↓", stickLeft: "←", stickRight: "→",
};

/** Gamepad bindings use the browser's standard mapping: "Button N" / "Axis N+" / "Axis N-". */
const PAD: Record<string, string> = {
  a: "Button 0", b: "Button 2", z: "Button 6", start: "Button 9", l: "Button 4", r: "Button 5",
  cUp: "Axis 3-", cDown: "Axis 3+", cLeft: "Axis 2-", cRight: "Axis 2+",
  dUp: "Button 12", dDown: "Button 13", dLeft: "Button 14", dRight: "Button 15",
  stickUp: "Axis 1-", stickDown: "Axis 1+", stickLeft: "Axis 0-", stickRight: "Axis 0+",
};

export function defaultBindings(device: Device): Record<string, string> {
  return { ...(device === "keyboard" ? KEYBOARD : PAD) };
}

const FACE: Partial<Record<Device, string[]>> = {
  xbox: ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "View", "Menu", "LS", "RS"],
  ds4: ["✕", "○", "□", "△", "L1", "R1", "L2", "R2", "Share", "Options", "L3", "R3"],
  dualsense: ["✕", "○", "□", "△", "L1", "R1", "L2", "R2", "Create", "Options", "L3", "R3"],
  switchpro: ["B", "A", "Y", "X", "L", "R", "ZL", "ZR", "−", "+", "LS", "RS"],
};
const DPAD = ["D-pad ↑", "D-pad ↓", "D-pad ←", "D-pad →"];
const AXES = [["LS ←", "LS →"], ["LS ↑", "LS ↓"], ["RS ←", "RS →"], ["RS ↑", "RS ↓"]];

/** A binding as the player sees it on their controller. */
export function bindingLabel(type: Device, value: string): string {
  const b = /^Button (\d+)$/.exec(value);
  if (b) {
    const n = +b[1];
    if (n >= 12 && n <= 15 && type !== "generic" && type !== "n64usb") return DPAD[n - 12];
    return FACE[type]?.[n] ?? value;
  }
  const a = /^Axis (\d+)([+-])$/.exec(value);
  if (a && type !== "generic" && type !== "n64usb") return AXES[+a[1]]?.[a[2] === "+" ? 1 : 0] ?? value;
  return value;
}

export const newPlayer = (connected: boolean, type: Device): Player =>
  ({ connected, type, bindings: defaultBindings(type), deadzone: 12, range: 100 });

export const DEFAULT_SETTINGS: Settings = {
  useDefaults: true,
  players: [newPlayer(true, "keyboard"), newPlayer(false, "xbox"), newPlayer(false, "xbox"), newPlayer(false, "xbox")],
  aspect: "4:3",
  resolutionScale: 2,
  vsync: true,
  fullscreen: true,
  n64Mode: false,
  experimental: {},
};

export const api = {
  getConfig: () => invoke<Config>("get_config"),
  setConfig: (config: Config) => invoke<void>("set_config", { config }),
  scan: () => invoke<Game[]>("scan_library"),
  cover: (id: string) => invoke<string>("get_cover", { id }),
  info: (id: string) => invoke<{ title: string; description: string | null; extract: string; url: string }>("game_info", { id }),
  compile: (id: string) => invoke<void>("compile_game", { id }),
  cancel: () => invoke<void>("cancel_compile"),
  play: (id: string) => invoke<void>("play_game", { id }),
  saves: (id: string) => invoke<SaveFile[]>("list_saves", { id }),
  openFolder: (path: string) => invoke<void>("open_folder", { path }),
  checkUpdates: () => invoke<UpdateInfo>("check_updates"),
  /** True when the app installed with its own engine; there is no recompiler folder to choose. */
  engineBundled: () => invoke<boolean>("engine_bundled"),
  /** False until a release app has downloaded its engine. */
  engineReady: () => invoke<boolean>("engine_ready"),
  /** Downloads the engine; progress arrives as `engine` events ({ done, total } bytes). */
  installEngine: () => invoke<void>("install_engine"),
  updatePlaid: () => invoke<void>("update_plaid"),
  async settings(id: string): Promise<Settings> {
    const stored = await invoke<Partial<Settings> | null>("get_settings", { id });
    const s = { ...DEFAULT_SETTINGS, ...(stored ?? {}) };
    return Array.isArray(s.players) && s.players.length === 4 ? s : { ...s, players: DEFAULT_SETTINGS.players };
  },
  saveSettings: (id: string, settings: Settings) => invoke<void>("set_settings", { id, settings }),
};

/** The id global defaults are stored under. */
export const DEFAULTS_ID = "defaults";

const covers = new Map<string, Promise<string | null>>();
export function coverFor(id: string): Promise<string | null> {
  if (!covers.has(id)) {
    // a failure is not remembered, so the next view of the game tries again
    covers.set(id, api.cover(id).catch(() => { covers.delete(id); return null; }));
  }
  return covers.get(id)!;
}

export type Change = { sha: string; subject: string; when: string };
export type UpdateInfo = { current: string; behind: number; changes: Change[] };
