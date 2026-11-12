import Link from "next/link";
import GroupIcon from "@/components/GroupIcon";
import { EFFECT_LABEL, GROUPS, pidPage, type Effect, type Impact as ImpactT } from "@/lib/data";

/** Paragraph citations, linked to the page of the source PDF. */
export function Cites({ basis, pdf }: { basis: string[]; pdf?: string | null }) {
  if (!basis.length) return null;
  return (
    <span className="cites">
      {basis.map((b) => {
        const page = pidPage(b);
        const label = `p.${page} ¶${b.split(".")[1]}`;
        return pdf && page ? <a key={b} href={`${pdf}#page=${page}`} rel="nofollow noopener" title={`Paragraph ${b} of the source`}>{label}</a>
          : <span key={b}>{label}</span>;
      })}
    </span>
  );
}

export function Direction({ effect }: { effect: Effect }) {
  const mark = effect === "opportunity" ? "▲" : effect === "cost" ? "▼" : "◆";
  return <span className={`dir d-${effect}`}><span aria-hidden="true">{mark}</span> {EFFECT_LABEL[effect]}</span>;
}

export function MethodNote() {
  return (
    <p className="small muted method">No scores. Each statement cites the paragraphs it rests on (p.page ¶paragraph, linked to the
      source PDF); statements the text does not support are left out. Direction shows who gains or bears the cost, not how much.
      For drafts, effects apply only if the draft is adopted. <Link href="/impact#method">How these are prepared</Link></p>
  );
}

/** Market impact on an order, draft or regulation page. Readable without JavaScript. */
export default function Impact({ impact, pdf, draft = false }: { impact: ImpactT; pdf?: string | null; draft?: boolean }) {
  const hit = GROUPS.filter(([g]) => impact.stakeholders[g]);
  return (
    <section className="impact card" id="impact">
      <p className="eyebrow">Market impact{draft ? " · analysis awaiting legal review" : ""}</p>
      {impact.market_note && <p className="impact-note">{impact.market_note}</p>}
      {hit.length > 0 && (<>
        <h3>Who is affected</h3>
        <ul className="who">{hit.map(([g, , long]) => {
          const c = impact.stakeholders[g]!;
          return (
            <li key={g} className={`e-${c.effect}`}>
              <div className="who-head"><GroupIcon g={g} /><Link href={`/impact/${g}`}>{long}</Link><Direction effect={c.effect} /></div>
              <p>{c.comment} <Cites basis={c.basis} pdf={pdf} /></p>
            </li>);
        })}</ul></>)}
      {impact.key_points.length > 0 && (<><h3>Key points</h3>
        <ul>{impact.key_points.map((k, i) => <li key={i}>{k.text} <Cites basis={k.basis} pdf={pdf} /></li>)}</ul></>)}
      {impact.procurement.length > 0 && (<><h3>Procurement requirements</h3>
        <ul>{impact.procurement.map((k, i) => <li key={i}>{k.text} <Cites basis={k.basis} pdf={pdf} /></li>)}</ul></>)}
      {impact.open_questions.length > 0 && (<><h3>Open questions</h3>
        <ul>{impact.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul></>)}
      <MethodNote />
    </section>
  );
}
