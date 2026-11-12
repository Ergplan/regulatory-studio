import type { Metadata } from "next";
import Link from "next/link";
import { HighBadge } from "@/components/AnalysisBlock";
import GroupIcon from "@/components/GroupIcon";
import { Cites, Direction, MethodNote } from "@/components/Impact";
import { GROUPS } from "@/lib/data";
import { impactSections } from "@/lib/impact";

export const metadata: Metadata = {
  title: "Market impact map",
  description: "Who recent electricity draft regulations, notified regulations and orders affect, and how: discoms, C&I and open access consumers, captive users, RE developers, storage, generators, grid operators and traders. Every statement cites the paragraph it rests on.",
  alternates: { canonical: "/impact" },
};

export default function ImpactMap() {
  const sections = impactSections();
  return (<>
    <p className="eyebrow">Market impact</p>
    <h1 className="hero">Who is affected, and how</h1>
    <p className="lede">Each row is a draft regulation, a notified regulation or an order; each column a group in the power market.
      A cell says what changes for that group and cites the paragraphs it rests on. An empty cell means the text does not affect that group directly.</p>
    <p className="legend small"><Direction effect="opportunity" /> <Direction effect="cost" /> <Direction effect="mixed" />
      <span className="muted">Direction only, no scores. Click a group to see everything that affects it.</span></p>
    {sections.length === 0 ? <div className="card empty">No impact assessments published yet.</div> : (<>
      <div className="matrix-scroll" role="region" aria-label="Impact matrix" tabIndex={0}>
        <table className="matrix">
          <thead><tr>
            <th className="doc-col" scope="col">Document</th>
            {GROUPS.map(([g, short, long]) => (
              <th key={g} scope="col"><Link href={`/impact/${g}`} title={long}><GroupIcon g={g} /><span>{short}</span></Link></th>))}
          </tr></thead>
          {sections.map((s) => (
            <tbody key={s.id}>
              <tr className="sec"><th colSpan={GROUPS.length + 1} scope="colgroup"><span>{s.label}</span> <em>{s.note}</em></th></tr>
              {s.rows.map((r) => (
                <tr key={r.key}>
                  <th className="doc-col" scope="row">
                    <span className="meta">{r.sub}{r.draft ? " · AI draft" : ""}</span>
                    {r.high && <HighBadge />}<Link href={`${r.href}#impact`}>{r.title}</Link>
                    <span className="row-note">{r.impact.market_note}</span>
                  </th>
                  {GROUPS.map(([g, short]) => {
                    const c = r.impact.stakeholders[g];
                    return c
                      ? <td key={g} className={`cell e-${c.effect}`}><Direction effect={c.effect} /><p>{c.comment}</p><Cites basis={c.basis} pdf={r.pdf} /></td>
                      : <td key={g} className="cell none"><span aria-hidden="true">—</span><span className="sr">{short}: not directly affected</span></td>;
                  })}
                </tr>))}
            </tbody>))}
        </table>
      </div>
      <div className="matrix-cards">
        {sections.map((s) => (
          <section key={s.id}><h2>{s.label} <em className="muted small">{s.note}</em></h2>
            {s.rows.map((r) => (
              <article key={r.key} className="card">
                <p className="meta">{r.sub}{r.draft ? " · AI draft" : ""}</p>
                <h3><Link href={`${r.href}#impact`}>{r.title}</Link></h3>
                <ul className="who">{GROUPS.filter(([g]) => r.impact.stakeholders[g]).map(([g, , long]) => {
                  const c = r.impact.stakeholders[g]!;
                  return <li key={g} className={`e-${c.effect}`}><div className="who-head"><GroupIcon g={g} /><span>{long}</span><Direction effect={c.effect} /></div>
                    <p>{c.comment} <Cites basis={c.basis} pdf={r.pdf} /></p></li>;
                })}</ul>
              </article>))}
          </section>))}
      </div>
    </>)}
    <section id="method" className="card method-box">
      <h2>How these are prepared</h2>
      <ol>
        <li>Only documents the legal team picks are assessed, from the operative text (the decision, the proviso, the table, the deadline), not the recitals. A party&apos;s argument is labelled as a claim, never as a finding.</li>
        <li>Each statement names the mechanism that changes (a charge, a limit, an obligation, an eligibility rule) and the figure the text gives. Nothing is computed that the text does not state.</li>
        <li>Every key point, procurement requirement and stakeholder comment cites paragraph ids from the extracted text. Statements whose citations are not in the document are dropped automatically.</li>
        <li>There are no scores. Direction (gains, bears cost, mixed) says who is on which side, not how much.</li>
        <li>An AI drafts the assessment; a named reviewer edits and approves it with the summary. Until then it is shown only on the preview, marked as a draft.</li>
      </ol>
      <MethodNote />
    </section>
  </>);
}
