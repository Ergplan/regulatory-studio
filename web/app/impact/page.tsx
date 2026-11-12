import type { Metadata } from "next";
import Link from "next/link";
import { HighBadge } from "@/components/AnalysisBlock";
import GroupIcon from "@/components/GroupIcon";
import { Cites, Direction, MethodNote } from "@/components/Impact";
import { GEO } from "@/components/IndiaMap";
import Stage from "@/components/Stage";
import { GROUPS, commissionName, site } from "@/lib/data";
import { impactByState, impactSections, tally } from "@/lib/impact";

export const metadata: Metadata = {
  title: "Market impact map",
  description: "State by state: which groups in the power market each draft regulation, notified regulation and order affects, and how. Every statement cites the paragraph it rests on.",
  alternates: { canonical: "/impact" },
};

export default function ImpactMap() {
  const codes = Object.keys(GEO).filter((k) => site.commissions[k]);
  const states = impactByState(codes);
  const all = impactSections();
  const overall = tally(all.flatMap((s) => s.rows));
  const count = (id: string) => all.find((s) => s.id === id)?.rows.length ?? 0;

  return (<>
        <section className="glass areas-box across">
      <h2 className="label">Across all commissions · {count("drafts")} drafts · {count("regulations")} regulations · {count("orders")} orders</h2>
      {overall.length ? (
        <ul className="tally">{overall.map((t) => (
          <li key={t.g}><Link href={`/impact/${t.g}`} title={`Everything that affects ${t.long.toLowerCase()}`}>
            <GroupIcon g={t.g} size={22} /><span>{t.short}</span>
            <em>{t.gains > 0 && <i className="d-opportunity">▲{t.gains}</i>}{t.costs > 0 && <i className="d-cost">▼{t.costs}</i>}{t.mixed > 0 && <i className="d-mixed">◆{t.mixed}</i>}</em>
          </Link></li>))}</ul>
      ) : <p className="muted">No impact assessments published yet.</p>}
      <p className="muted small">Pick a group to see only what affects it. Counts are documents, by direction.</p>
    </section>
    <div className="cover">
      <Stage items={codes.map((code) => { const s = states.find((x) => x.code === code);
        return { code, href: s ? `#c-${code}` : `/commissions/${code}`, idle: !s, note: s ? `${s.n} assessed` : "not assessed" }; })} />
      <div className="flow">
        <section className="cover-hero short">
          <p className="eyebrow">Market impact</p>
          <h1 className="hero">Who is affected, and how.</h1>
          <p className="lede">One block per commission. Inside it, drafts, regulations and orders are kept apart, and each shows only
            the groups it touches. Open any item for the reason and the paragraphs it rests on.</p>
          <p className="legend small"><Direction effect="opportunity" /> <Direction effect="cost" /> <Direction effect="mixed" />
            <span className="muted">Direction only, no scores.</span></p>
        </section>

        {states.map((s) => (
          <section key={s.code} className="chapter state" id={`c-${s.code}`} data-chapter={s.code}>
            <header className="chapter-head rise">
              <p className="eyebrow">{GEO[s.code].place} · {s.n} assessed</p>
              <h2><Link href={`/commissions/${s.code}`}>{commissionName(s.code)}</Link></h2>
              <ul className="tally mini" aria-label="Groups affected here">{s.tally.map((t) => (
                <li key={t.g} title={t.long}><span><GroupIcon g={t.g} size={18} /><span>{t.short}</span>
                  <em>{t.gains > 0 && <i className="d-opportunity">▲{t.gains}</i>}{t.costs > 0 && <i className="d-cost">▼{t.costs}</i>}{t.mixed > 0 && <i className="d-mixed">◆{t.mixed}</i>}</em></span></li>))}</ul>
              {s.lead && <p className="state-lead">{s.lead}</p>}
            </header>
            {s.sections.map((sec) => (
              <div key={sec.id} className={`kind kind-${sec.id} rise`}>
                <h3 className="kind-head"><span>{sec.label}</span><em>{sec.note}</em></h3>
                {sec.rows.map((r) => {
                  const hit = GROUPS.filter(([g]) => r.impact.stakeholders[g]);
                  return (
                    <details key={r.key} className="doc">
                      <summary>
                        <span className="doc-title">{r.high && <HighBadge />}{r.title}</span>
                        <span className="doc-sub">{r.sub}{r.draft ? " · AI draft" : ""}</span>
                        <span className="doc-icons">{hit.map(([g, short]) => (
                          <span key={g} className={`ic e-${r.impact.stakeholders[g]!.effect}`} title={`${short}: ${r.impact.stakeholders[g]!.comment}`}>
                            <GroupIcon g={g} size={17} /><span>{short}</span></span>))}</span>
                      </summary>
                      <p className="doc-note">{r.impact.market_note}</p>
                      <ul className="who">{hit.map(([g, , long]) => { const c = r.impact.stakeholders[g]!; return (
                        <li key={g} className={`e-${c.effect}`}><div className="who-head"><GroupIcon g={g} /><span>{long}</span><Direction effect={c.effect} /></div>
                          <p>{c.comment} <Cites basis={c.basis} pdf={r.pdf} /></p></li>); })}</ul>
                      <p className="folder-links"><Link href={`${r.href}#impact`}>Key points and procurement requirements →</Link></p>
                    </details>);
                })}
              </div>))}
          </section>))}

        <section id="method" className="glass method-box rise">
          <h2 className="label">How these are prepared</h2>
          <ol>
            <li>Only documents the legal team picks are assessed, from the operative text (the decision, the proviso, the table, the deadline), not the recitals. A party&apos;s argument is labelled as a claim, never as a finding.</li>
            <li>Each statement names the mechanism that changes and the figure the text gives. Nothing is computed that the text does not state.</li>
            <li>Every statement cites paragraph ids from the extracted text; statements whose citations are not in the document are dropped automatically.</li>
            <li>There are no scores. Direction says who is on which side, not how much. &quot;High impact&quot; is the team&apos;s own rating, given in review.</li>
            <li>An AI drafts the assessment; a named reviewer edits and approves it. Until then it is shown only on the preview, marked as a draft.</li>
          </ol>
          <MethodNote />
        </section>
      </div>
    </div>
  </>);
}
