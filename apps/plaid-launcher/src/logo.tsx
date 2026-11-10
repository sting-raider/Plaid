/**
 * The Plaid mark: a flat-shaded low-poly "P". Red stem, and a bowl lit yellow on top,
 * blue on the side and green underneath, so all four controller colours appear.
 */
interface Facet { points: string; fill: string; from: [number, number, number] }

// `from`: where the facet flies in from during the intro (dx, dy in viewBox units, rotation in degrees)
export const FACETS: Facet[] = [
  { points: "13,12 20,8 20,56 13,52", fill: "#9b2b30", from: [-70, 6, -90] },
  { points: "20,8 31,8 31,30 20,34", fill: "#e5484d", from: [-26, -74, 50] },
  { points: "20,34 31,30 31,56 20,56", fill: "#cc3a40", from: [-36, 72, -60] },
  { points: "20,8 31,8 25.5,13", fill: "#ff8a8e", from: [4, -86, 180] },
  { points: "31,8 41,8 52,17 42,20 31,19", fill: "#f5c542", from: [66, -62, 120] },
  { points: "52,17 52,29 42,27 42,20", fill: "#3e7bfa", from: [86, 4, -120] },
  { points: "52,29 42,38 31,38 31,28 42,27", fill: "#2f9e66", from: [56, 66, 90] },
];

export const Logo = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
    {FACETS.map((f) => <polygon key={f.points} points={f.points} fill={f.fill} />)}
  </svg>
);

/** The intro version: facets fly in as wireframes, lock, shade in, then a glint sweeps across. */
export function AnimatedLogo({ delay = 0.55 }: { delay?: number }) {
  return (
    <svg className="logo-anim" viewBox="0 0 64 64" aria-hidden>
      <defs>
        <clipPath id="logo-clip">{FACETS.map((f) => <polygon key={f.points} points={f.points} />)}</clipPath>
        <linearGradient id="logo-glint" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0.75" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {FACETS.map((f, i) => (
        <polygon
          key={f.points}
          className="facet"
          points={f.points}
          style={{
            "--c": f.fill,
            "--dx": `${f.from[0]}px`,
            "--dy": `${f.from[1]}px`,
            "--r": `${f.from[2]}deg`,
            "--d": `${delay + i * 0.09}s`,
            "--s": `${delay + 0.95 + i * 0.07}s`,
          } as React.CSSProperties}
        />
      ))}
      <g clipPath="url(#logo-clip)">
        <rect className="glint" x="-30" y="-10" width="22" height="84" fill="url(#logo-glint)" transform="skewX(-20)"
          style={{ animationDelay: `${delay + 1.75}s` }} />
      </g>
    </svg>
  );
}
