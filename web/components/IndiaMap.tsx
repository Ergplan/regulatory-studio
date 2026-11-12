import dots from "@/lib/india-dots.json";

/** Where each commission sits: the state whose dots light up, and where its card floats around the map
 *  (in the map's own units; India spans 0..612 by 0..696). */
export const GEO: Record<string, { state: string; place: string; card: [number, number]; national?: boolean }> = {
  cerc: { state: "dl", place: "All India", card: [-112, 62], national: true },
  aptel: { state: "dl", place: "Appeals", card: [452, 48], national: true },
  uperc: { state: "up", place: "Uttar Pradesh", card: [522, 150] },
  rerc: { state: "rj", place: "Rajasthan", card: [-122, 196] },
  gerc: { state: "gj", place: "Gujarat", card: [-122, 330] },
  merc: { state: "mh", place: "Maharashtra", card: [-112, 464] },
  kerc: { state: "ka", place: "Karnataka", card: [-46, 598] },
  tnerc: { state: "tn", place: "Tamil Nadu", card: [420, 612] },
};
export const VB = { x: -215, y: 0, w: 860, h: 700 };
const STATES = dots.states as Record<string, { d: string; c: number[]; n: number }>;
export const centre = (code: string) => STATES[GEO[code].state].c as [number, number];

/** CSS that ties the commission in view to its state's dots, its marker, its card and its label. */
export function geoCss(): string {
  return Object.entries(GEO).map(([k, g]) => [
    `.cover:not(.in-story) .st-${g.state}{stroke:var(--dot-lit);stroke-width:3.1}`,
    `.cover.seen-${k} .st-${g.state}{stroke:var(--dot-seen);stroke-width:3.1}`,
    g.national ? `.cover[data-active="${k}"] .st{stroke:var(--dot-wash)}` : "",
    `.cover[data-active="${k}"] .st-${g.state}{stroke:var(--power);stroke-width:4.4}`,
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
        <g key={k} className={`mk mk-${k}`}><circle cx={x} cy={y} r="5" className="mk-dot" /><circle cx={x} cy={y} r="5" className="mk-ring" /></g>); })}
    </svg>
  );
}

export function LeaderLines() {
  return (
    <svg className="leaders" viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`} aria-hidden="true" focusable="false">
      {Object.entries(GEO).map(([k, g]) => { const [x, y] = centre(k); const [cx, cy] = g.card;
        const mx = (cx + x) / 2; return <path key={k} className={`ln ln-${k}`} d={`M${cx} ${cy}C${mx} ${cy} ${mx} ${y} ${x} ${y}`} />; })}
    </svg>
  );
}
