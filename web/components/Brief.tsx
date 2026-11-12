import Link from "next/link";
import GroupIcon from "@/components/GroupIcon";
import { Direction } from "@/components/Impact";
import { discussHref } from "@/components/ProjectCta";
import { GROUPS, type Impact } from "@/lib/data";

/** The first screen of an analysis: what happened, who should pay attention, what decides whether it applies, and the next step. */
export default function Brief({ impact, status, analysis, ask, about, path }: { impact: Impact; status: string; analysis: string; ask: string; about: string; path: string }) {
  const hit = GROUPS.filter(([g]) => impact.stakeholders[g]);
  return (
    <section className="brief glass" aria-label="In brief">
      <div className="brief-status"><span><b>Document</b> {status}</span><span><b>Analysis</b> {analysis}</span></div>
      <div className="brief-grid">
        <div><h2>What happened</h2><p>{impact.market_note}</p></div>
        <div><h2>Who should pay attention</h2>
          <ul className="who-chips">{hit.map(([g, short]) => <li key={g}><GroupIcon g={g} size={16} /> <Link href={`/impact/${g}`}>{short}</Link> <Direction effect={impact.stakeholders[g]!.effect} /></li>)}</ul></div>
        {impact.checks && impact.checks.length > 0 && (
          <div><h2>What decides whether it applies to you</h2><ul className="checks">{impact.checks.map((c) => <li key={c}>{c}</li>)}</ul></div>)}
        <div className="brief-next"><h2>Next step</h2>
          <p>A plant or project impact review tells you whether this applies, which assumptions to check and what to look at next.</p>
          <p><Link href={discussHref(ask, about, path)} className="btn">{ask}</Link> <a href="#impact" className="btn ghost">See the evidence</a></p></div>
      </div>
    </section>
  );
}
