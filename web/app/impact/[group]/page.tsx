import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import GroupIcon from "@/components/GroupIcon";
import { Cites, Direction, MethodNote } from "@/components/Impact";
import { GROUPS, type GroupKey } from "@/lib/data";
import { impactSections } from "@/lib/impact";

type Params = { group: string };
export const dynamicParams = false;
export const generateStaticParams = (): Params[] => GROUPS.map(([g]) => ({ group: g }));
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
  const n = hits.reduce((k, s) => k + s.rows.length, 0);
  return (<>
    <p className="eyebrow"><Link href="/impact">Market impact</Link></p>
    <h1 className="hero group-hero"><GroupIcon g={g} size={34} /> {long}</h1>
    <p className="lede">{n} of {total} assessed documents affect {long.toLowerCase()} directly.</p>
    <nav className="group-nav small">{GROUPS.map(([k, short]) => k === g ? <strong key={k}>{short}</strong> : <Link key={k} href={`/impact/${k}`}>{short}</Link>)}</nav>
    {hits.map((s) => (
      <section key={s.id}><h2>{s.label} <em className="muted small">{s.note}</em></h2>
        <ul className="who big">{s.rows.map((r) => {
          const c = r.impact.stakeholders[g]!;
          return <li key={r.key} className={`e-${c.effect}`}>
            <div className="who-head"><Link href={`${r.href}#impact`}>{r.title}</Link><Direction effect={c.effect} /></div>
            <p className="meta">{r.sub}{r.draft ? " · AI draft" : ""}</p>
            <p>{c.comment} <Cites basis={c.basis} pdf={r.pdf} /></p></li>;
        })}</ul>
      </section>))}
    <MethodNote />
  </>);
}
