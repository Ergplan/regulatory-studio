import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { actById, actSections, citingOrders, linkTypeLabel, orderLabel } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { parts: string[] };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return actSections.map((a) => ({ parts: a.id.split("/") })); }

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const a = actById.get((await params).parts.join("/"));
  return a ? { title: `Section ${a.number}, ${a.act}: ${a.title}`, alternates: { canonical: `/act/${a.id}` } } : {};
}

export default async function ActPage({ params }: { params: Promise<Params> }) {
  const a = actById.get((await params).parts.join("/"));
  if (!a) notFound();
  const citing = citingOrders("act_section", a.id);
  return (
    <article>
      <div className="meta"><span className="tag">{a.act}</span></div>
      <h1>Section {a.number}: {a.title}</h1>
      <h2>Reviewed orders relying on this section</h2>
      {citing.length ? <ul className="links-list">{citing.map(({ order, links }) => (
        <li key={order.id}><Link href={order.path}>{order.title ?? orderLabel(order)}</Link> <span className="muted">{order.commission.toUpperCase()} · {fmtDate(order.date)}</span>
          {links.map((l, i) => <blockquote key={i}><strong>{linkTypeLabel(l.type)}</strong>: {l.excerpt}</blockquote>)}</li>))}</ul>
        : <p className="muted">No reviewed order cites this section yet.</p>}
    </article>
  );
}
