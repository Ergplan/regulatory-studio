import { EFFECT_LABEL, GROUPS, type Impact as ImpactT, type ImpactCell } from "@/lib/data";

export function HeatCell({ cell, label, compact = false }: { cell?: ImpactCell; label: string; compact?: boolean }) {
  const c = cell ?? { level: 0, effect: "neutral", why: "" };
  const text = c.level ? `${label}: ${EFFECT_LABEL[c.effect]}, level ${c.level} of 3${c.why ? ` (${c.why})` : ""}` : `${label}: no effect`;
  return (
    <td className={`heat e-${c.effect} l-${c.level}`} title={text}>
      <span className="sr">{text}</span>
      {!compact && c.level > 0 && <span aria-hidden="true">{c.effect === "cost" ? "−" : c.effect === "opportunity" ? "+" : "±"}{c.level}</span>}
    </td>
  );
}

export function HeatLegend() {
  return (
    <p className="heat-legend small">
      <span><i className="heat e-opportunity l-3" /> Opportunity</span>
      <span><i className="heat e-cost l-3" /> Cost or obligation</span>
      <span><i className="heat e-mixed l-3" /> Mixed</span>
      <span className="muted">Darker = more direct and material (level 1 to 3). Proposals affect people only if adopted.</span>
    </p>
  );
}

/** Market impact box for an order or draft page. Readable without JavaScript. */
export default function Impact({ impact, draft = false }: { impact: ImpactT; draft?: boolean }) {
  const hit = GROUPS.filter(([g]) => (impact.stakeholders[g]?.level ?? 0) > 0);
  return (
    <section className="impact card">
      <p className="eyebrow">Market impact{draft ? " · draft, not reviewed" : ""}</p>
      {impact.market_note && <p className="impact-note">{impact.market_note}</p>}
      {impact.key_points.length > 0 && (<><h3>Key points</h3><ul>{impact.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul></>)}
      {impact.procurement.length > 0 && (<><h3>Procurement requirements</h3><ul>{impact.procurement.map((k, i) => <li key={i}>{k}</li>)}</ul></>)}
      <h3>Who it affects</h3>
      <table className="heatmap one"><thead><tr>{GROUPS.map(([g, short, long]) => <th key={g} title={long}>{short}</th>)}</tr></thead>
        <tbody><tr>{GROUPS.map(([g, short]) => <HeatCell key={g} cell={impact.stakeholders[g]} label={short} />)}</tr></tbody></table>
      {hit.length > 0 && <ul className="impact-why small">{hit.map(([g, , long]) => {
        const c = impact.stakeholders[g];
        return <li key={g}><b>{long}</b> · {EFFECT_LABEL[c.effect]}{c.why ? `: ${c.why}` : ""}</li>;
      })}</ul>}
      <HeatLegend />
    </section>
  );
}
