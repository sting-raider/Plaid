import { useEffect, useState } from "react";
import { AnimatedLogo } from "./logo";

/**
 * Start-up sequence: CRT power-on, the low-poly P assembles from wireframe facets and
 * shades in, the wordmark drops in, then the update check fills a cartridge-style
 * loading bar. `work` resolves with the status line to show when it finishes.
 */
export function Boot({ work, onDone }: { work: (status: (s: string) => void) => Promise<string>; onDone: () => void }) {
  const [status, setStatus] = useState("Powering on");
  const [blocks, setBlocks] = useState(0);
  const [finished, setFinished] = useState(false);
  const [off, setOff] = useState(false);

  useEffect(() => {
    let live = true;
    const minimum = new Promise((r) => setTimeout(r, 3300));
    // the bar creeps while the work runs; it never claims more than 13 of 16 blocks early
    const creep = setInterval(() => setBlocks((b) => (b < 13 ? b + 1 : b)), 220);
    const start = setTimeout(() => setStatus("Checking for updates"), 2500);
    Promise.all([work((s) => live && setStatus(s)), minimum]).then(([final]) => {
      if (!live) return;
      clearInterval(creep);
      setBlocks(16);
      setStatus(final);
      setFinished(true);
      setTimeout(() => live && setOff(true), 650);
      setTimeout(() => live && onDone(), 1100);
    });
    return () => { live = false; clearInterval(creep); clearTimeout(start); };
  }, []);

  useEffect(() => {
    const skip = () => { if (finished) { setOff(true); setTimeout(onDone, 450); } };
    window.addEventListener("keydown", skip);
    window.addEventListener("mousedown", skip);
    return () => { window.removeEventListener("keydown", skip); window.removeEventListener("mousedown", skip); };
  }, [finished]);

  return (
    <div className={`boot ${off ? "off" : ""}`} data-tauri-drag-region>
      <div className="boot-screen">
        <div className="mark3d"><AnimatedLogo /></div>
        <div className="wordmark">
          {"PLAID".split("").map((c, i) => <span key={i} style={{ animationDelay: `${2.3 + i * 0.07}s` }}>{c}</span>)}
        </div>
        <div className="boot-status">
          <div className="boot-blocks">{Array.from({ length: 16 }, (_, i) => <i key={i} className={i < blocks ? "on" : ""} />)}</div>
          <div className={`pixel ${finished ? "" : "cursor"}`}>{status}</div>
        </div>
      </div>
    </div>
  );
}
