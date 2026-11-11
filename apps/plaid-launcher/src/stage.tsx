// Dev builds look different at a glance: "Plaid (Dev)", a Dev pill, and a woven tartan in the
// logo's colours behind the title bar. A dev build is any frontend not built in production mode
// (`npm run tauri:dev-build` builds with --mode dev).
import { useId } from "react";

export const DEV = import.meta.env.MODE !== "production";
export const APP_NAME = DEV ? "Plaid (Dev)" : "Plaid";

// one sett (repeat) of the tartan: [offset, width, colour, opacity], used for both warp and weft
const SETT = 96;
const BANDS: [number, number, string, number][] = [
  [0, 22, "#e5484d", 0.55],
  [30, 6, "#f5c542", 0.6],
  [44, 18, "#30a46c", 0.42],
  [70, 4, "#3e7bfa", 0.7],
  [80, 10, "#3e7bfa", 0.32],
];
const THREADS = [26, 40, 66, 93]; // fine light over-check lines

export function StageBackdrop() {
  return DEV ? <div className="stage-art" aria-hidden><TartanArt /></div> : null;
}

function TartanArt() {
  const id = useId().replace(/:/g, "");
  return (
    <svg className="stage-art-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMid slice">
      <defs>
        <pattern id={`${id}-sett`} width={SETT} height={SETT} patternUnits="userSpaceOnUse" patternTransform="translate(-14 -30)">
          <rect width={SETT} height={SETT} fill="#14121a" />
          {BANDS.map(([at, w, c, o]) => <rect key={`v${at}`} x={at} width={w} height={SETT} fill={c} opacity={o} />)}
          {BANDS.map(([at, w, c, o]) => <rect key={`h${at}`} y={at} height={w} width={SETT} fill={c} opacity={o * 0.85} />)}
          {THREADS.map((at) => <rect key={`tv${at}`} x={at} width={1} height={SETT} fill="#fff" opacity={0.22} />)}
          {THREADS.map((at) => <rect key={`th${at}`} y={at} height={1} width={SETT} fill="#fff" opacity={0.18} />)}
        </pattern>
        {/* the 2/2 twill: alternating diagonal threads give the cloth its woven texture */}
        <pattern id={`${id}-twill`} width={4} height={4} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width={2} height={4} fill="#000" opacity={0.3} />
        </pattern>
        <linearGradient id={`${id}-shade`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.08" />
          <stop offset="1" stopColor="#000" stopOpacity="0.35" />
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id}-sett)`} />
      <rect width="100%" height="100%" fill={`url(#${id}-twill)`} />
      <rect width="100%" height="100%" fill={`url(#${id}-shade)`} />
    </svg>
  );
}
