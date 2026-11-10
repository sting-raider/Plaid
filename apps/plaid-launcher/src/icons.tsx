const s = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;
type P = { size?: number };

/** The plaid mark: two vertical and two horizontal bars in the four controller colours. */
export const Logo = ({ size = 18 }: P) => (
  <svg width={size} height={size} viewBox="0 0 22 22" aria-hidden>
    <rect x="5" y="0" width="4" height="22" rx="1" fill="#e5484d" />
    <rect x="13" y="0" width="4" height="22" rx="1" fill="#3e7bfa" />
    <rect x="0" y="5" width="22" height="4" rx="1" fill="#30a46c" opacity="0.92" />
    <rect x="0" y="13" width="22" height="4" rx="1" fill="#f5c542" opacity="0.92" />
  </svg>
);

export const Minimize = () => (<svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 5h10" stroke="currentColor" /></svg>);
export const Maximize = () => (<svg width="10" height="10" viewBox="0 0 10 10"><rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" /></svg>);
export const Close = () => (<svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 0l10 10M10 0L0 10" stroke="currentColor" /></svg>);

export const Play = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24"><path d="M7 4.5v15l12.5-7.5z" fill="currentColor" /></svg>);
export const Hammer = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><path d="M14 4l6 6-3 3-6-6zM11 7L3 15l3 3 8-8" /></svg>);
export const Gear = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>);
export const Search = ({ size = 16 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>);
export const Folder = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>);
export const Refresh = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><path d="M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4" /></svg>);
export const Back = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><path d="M15 18l-6-6 6-6" /></svg>);
export const Check = ({ size = 12 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s} strokeWidth={3}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>);
export const Grid = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><rect x="4" y="4" width="7" height="7" rx="1.5" /><rect x="13" y="4" width="7" height="7" rx="1.5" /><rect x="4" y="13" width="7" height="7" rx="1.5" /><rect x="13" y="13" width="7" height="7" rx="1.5" /></svg>);
export const Bolt = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><path d="M13 3L5 13h6l-1 8 8-10h-6z" /></svg>);
export const Pad = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><path d="M7 8h10a4 4 0 0 1 4 4.5l-.6 3.6a2.5 2.5 0 0 1-4.3 1.3L14 15h-4l-2.1 2.4a2.5 2.5 0 0 1-4.3-1.3L3 12.5A4 4 0 0 1 7 8z" /><path d="M8 11v3M6.5 12.5h3" /><circle cx="16" cy="11.5" r=".6" fill="currentColor" /><circle cx="17.5" cy="13.5" r=".6" fill="currentColor" /></svg>);
export const Info = ({ size = 18 }: P) => (<svg width={size} height={size} viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>);
