import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HighBadge } from "@/components/AnalysisBlock";
import GroupIcon from "@/components/GroupIcon";
import { Cites, Direction, MethodNote } from "@/components/Impact";
import ProjectCta from "@/components/ProjectCta";
import { GROUPS, type GroupKey } from "@/lib/data";
import { impactSections } from "@/lib/impact";

type Params = { group: string };
export const dynamicParams = false;
export const generateStaticParams = (): Params[] => GROUPS.map(([g]) => ({ group: g }));
const ROLE: Record<string, string> = { ci_consumers: "Industrial or commercial energy buyer", captive: "Captive power user", re_developers: "Renewable developer",
  storage: "Storage developer", discoms: "Distribution licensee" };
const find = (g: string) => GROUPS.find(([k]) => k === g);

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const grp = find((await params).group);
  if (!grp) return {};
  return { title: `Market impact on ${grp[2].toLowerCase()}`, alternates: { canonical: `/impact/${grp[0]}` },
    description: `What recent electricity draft regulations, regulations and orders change for ${grp[2].toLowerCase()}, with paragraph citations.` };
}

export default async function GroupPage({ params }: { params: Promise<Params> }) {
  const grp = find((await params).group);
  if (!grp) notFound();
  const [g, , long] = grp as [GroupKey, string, string];
  const sections = impactSections();
  const total = sections.reduce((n, s) => n + s.rows.length, 0);
  const hits = sections.map((s) => ({ ...s, rows: s.rows.filter((r) => r.impact.stakeholders[g]) })).filter((s) => s.rows.length);
  const mine = hits.flatMap((s) => s.rows.map((r) => r.impact.stakeholders[g]!.effect));
  const n = mine.length;
  const count = (e: string) => mine.filter((x) => x === e).length;
  return (<>
    <p className="eyebrow"><Link href="/impact">Market impact</Link></p>
    <h1 className="hero page-title group-hero"><GroupIcon g={g} size={40} /> {long}</h1>
    <p className="lede">{n ? `${n} of ${total} assessed documents affect this group directly.` : `None of the ${total} assessed documents affects this group directly yet.`}</p>
    {n > 0 && <p className="g-tally">{count("opportunity") > 0 && <span className="d-opportunity">▲ {count("opportunity")} gain</span>}{count("cost") > 0 && <span className="d-cost">▼ {count("cost")} bear cost</span>}{count("mixed") > 0 && <span className="d-mixed">◆ {count("mixed")} mixed</span>}</p>}
    <nav className="g-switch" aria-label="Choose a group">{GROUPS.map(([k, short]) => (
      <Link key={k} href={`/impact/${k}`} className={k === g ? "on" : ""} aria-current={k === g ? "page" : undefined}><GroupIcon g={k} size={18} /><span>{short}</span></Link>))}</nav>

    {hits.map((s) => (
      <section key={s.id} className={`kind kind-${s.id} g-kind`}>
        <h2 className="kind-head"><span>{s.label}</span><em>{s.note}</em></h2>
        {s.rows.map((r) => {
          const c = r.impact.stakeholders[g]!;
          return (
            <article key={r.key} className={`g-item e-${c.effect}`}>
              <p className="lib-meta"><span className="lib-code">{r.commission.toUpperCase()}</span><span>{r.sub}</span>{r.draft && <span className="pend">analysis awaiting review</span>}</p>
              <h3>{r.high && <HighBadge />}<Link href={r.href}>{r.impact.headline || r.title}</Link></h3>
              {r.impact.headline && <p className="formal">{r.title}</p>}
              <div className="g-effect"><Direction effect={c.effect} /><p>{c.comment} <Cites basis={c.basis} pdf={r.pdf} /></p></div>
              {r.impact.checks && r.impact.checks.length > 0 && (
                <details className="g-checks"><summary>What decides whether it applies to you</summary><ul className="checks">{r.impact.checks.map((q) => <li key={q}>{q}</li>)}</ul></details>)}
              <p className="lib-links"><Link href={r.href}>Open the full analysis →</Link></p>
            </article>);
        })}
      </section>))}
    <ProjectCta ask="Discuss my project" about={`Impact on ${long}`} path={`/impact/${g}`} as={ROLE[g]} />
    <MethodNote />
  </>);
}
