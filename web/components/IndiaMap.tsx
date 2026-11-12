import dots from "@/lib/india-dots.json";

/** Where each commission sits: the state whose dots light up, and where its card floats around the map
 *  (in the map's own units; India spans 0..612 by 0..696). */
export const GEO: Record<string, { state: string; place: string; card: [number, number]; side: "left" | "right"; national?: boolean }> = {
  // two tidy columns of labels, four a side, each at the same height as its opposite number
  cerc: { state: "dl", place: "All India", card: [-70, 110], side: "left", national: true },
  rerc: { state: "rj", place: "Rajasthan", card: [-70, 280], side: "left" },
  gerc: { state: "gj", place: "Gujarat", card: [-70, 450], side: "left" },
  merc: { state: "mh", place: "Maharashtra", card: [-70, 620], side: "left" },
  aptel: { state: "dl", place: "Appeals", card: [682, 110], side: "right", national: true },
  uperc: { state: "up", place: "Uttar Pradesh", card: [682, 280], side: "right" },
  kerc: { state: "ka", place: "Karnataka", card: [682, 450], side: "right" },
  tnerc: { state: "tn", place: "Tamil Nadu", card: [682, 620], side: "right" },
};
export const VB = { x: -470, y: -20, w: 1552, h: 736 };
const STATES = dots.states as Record<string, { d: string; c: number[]; n: number }>;
export const centre = (code: string) => STATES[GEO[code].state].c as [number, number];

/** CSS that ties the commission in view to its state's dots, its marker, its card and its label. */
export function geoCss(): string {
  return Object.entries(GEO).map(([k, g]) => [
    `.cover:not(.in-story) .st-${g.state}{stroke:var(--dot-lit);stroke-width:4}`,
    `.cover.seen-${k} .st-${g.state}{stroke:var(--dot-seen);stroke-width:4}`,
    g.national ? `.cover[data-active="${k}"] .st{stroke:var(--dot-wash)}` : "",
    `.cover[data-active="${k}"] .st-${g.state}{stroke:var(--power);stroke-width:5.4}`,
    `.cover[data-active="${k}"] .mk-${k}{opacity:1}`,
    `.cover[data-active="${k}"] .ln-${k}{stroke:var(--power);opacity:.9}`,
    `.cover[data-active="${k}"] .cc-${k}{opacity:1;background:var(--green-glass);border-color:var(--power);color:#fff}`,
    `.cover[data-active="${k}"] .now-${k}{display:inline-flex}`,
  ].join("")).join("");
}

/** India drawn as small dots, one path per state so a state can light up. Decorative: every commission is also a text link. */
export default function IndiaMap() {
  return (
    <svg className="india" viewBox={dots.viewBox} role="img" aria-label="Dotted map of India showing the states whose electricity commissions are covered">
      {Object.entries(STATES).map(([id, s]) => <path key={id} className={`st st-${id}`} d={s.d} />)}
      {Object.keys(GEO).map((k) => { const [x, y] = centre(k); return (
        <g key={k} className={`mk mk-${k}`}><circle cx={x} cy={y} r="8" className="mk-dot" /><circle cx={x} cy={y} r="8" className="mk-ring" /></g>); })}
    </svg>
  );
}

export function LeaderLines() {
  return (
    <svg className="leaders" viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`} aria-hidden="true" focusable="false">
      {Object.entries(GEO).map(([k, g]) => { const [x, y] = centre(k); const [cx, cy] = g.card;
        const bend = g.side === "left" ? cx + 70 : cx - 70;
        return <path key={k} className={`ln ln-${k}`} d={`M${cx} ${cy}H${bend}L${x} ${y}`} />; })}
    </svg>
  );
}
