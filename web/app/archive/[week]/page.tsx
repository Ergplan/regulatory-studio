import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { draftRow, LibraryRow, orderRow } from "@/components/Library";
import { weeks } from "@/lib/archive";
import { site } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { week: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return weeks.map((w) => ({ week: w.id })); }
const find = (id: string) => weeks.find((w) => w.id === id.toLowerCase());
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const w = find((await params).week);
  return w ? { title: `Week of ${fmtDate(w.from)}`, description: `Orders and draft regulations issued from ${fmtDate(w.from)} to ${fmtDate(w.to)}.`, alternates: { canonical: w.path } } : {};
}

export default async function WeekPage({ params }: { params: Promise<Params> }) {
  const w = find((await params).week);
  if (!w) notFound();
  const i = weeks.indexOf(w), newer = weeks[i - 1], older = weeks[i + 1];
  const commissions = [...new Set(w.orders.map((o) => o.commission))].sort();
  return (<>
    <p className="eyebrow"><Link href="/archive">Archive</Link> · week {w.id.slice(6)} of {w.id.slice(0, 4)}</p>
    <h1>{fmtDate(w.from)} to {fmtDate(w.to)}</h1>
    <p className="lede">{w.orders.length} order{w.orders.length === 1 ? "" : "s"}{w.drafts.length ? ` and ${w.drafts.length} draft regulation${w.drafts.length === 1 ? "" : "s"}` : ""} issued this week.
      {w.digest && <> Read the <Link href={w.digest}>weekly digest</Link> for the key points.</>}</p>
    {w.pending > 0 && <p className="note"><b>{w.pending === w.orders.length + w.drafts.length ? "These analyses are" : `${w.pending} of these analyses are`} awaiting legal review.</b> They were prepared with AI and are marked on each item. Read the original order before relying on them.</p>}
    {w.drafts.length > 0 && <section className="lib-sec"><h2>Draft regulations and notices</h2>
      <ul className="lib">{w.drafts.map((c) => <LibraryRow key={c.id} r={draftRow(c)} />)}</ul></section>}
    {commissions.map((c) => (<section key={c} className="lib-sec"><h2>{site.commissions[c] ?? c.toUpperCase()}</h2>
      <ul className="lib">{w.orders.filter((o) => o.commission === c).map((o) => <LibraryRow key={o.id} r={orderRow(o)} showCode={false} />)}</ul></section>))}
    <nav className="arch-nav" aria-label="Other weeks">
      {older ? <Link href={older.path}>← Week of {fmtDate(older.from)}</Link> : <span />}
      {newer ? <Link href={newer.path}>Week of {fmtDate(newer.from)} →</Link> : <span />}
    </nav>
  </>);
}
