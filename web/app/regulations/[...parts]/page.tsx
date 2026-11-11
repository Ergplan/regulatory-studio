import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import SpiderMap, { type MapNode } from "@/components/SpiderMap";
import { citingOrders, clauses, clausesOf, commissionName, linkTypeLabel, orderLabel, regulationById, regulations, site } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { parts: string[] };
export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  return [
    ...regulations.map((r) => ({ parts: r.path.split("/").slice(2) })),
    ...clauses.map((c) => ({ parts: c.path.split("/").slice(2) })),
  ];
}

function resolve(parts: string[]) {
  const path = "/regulations/" + parts.map(decodeURIComponent).join("/");
  const reg = regulations.find((r) => r.path === path);
  if (reg) return { reg, clause: undefined };
  const clause = clauses.find((c) => c.path === path);
  if (clause) return { reg: regulationById.get(clause.regulation_id)!, clause };
  return null;
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const r = resolve((await params).parts);
  if (!r) return {};
  const title = r.clause ? `Regulation ${r.clause.number}${r.clause.heading ? ", " + r.clause.heading : ""} · ${r.reg.short_title ?? r.reg.title}` : r.reg.title;
  const path = r.clause?.path ?? r.reg.path;
  return { title, description: r.clause?.text.slice(0, 160) ?? `Clauses of the ${r.reg.title} and the orders that cite them.`,
    alternates: { canonical: path, types: { "text/markdown": path + ".md" } }, robots: r.reg.sample ? { index: false } : undefined };
}

export default async function RegulationPage({ params }: { params: Promise<Params> }) {
  const r = resolve((await params).parts);
  if (!r) notFound();
  const { reg, clause } = r;

  if (clause) {
    const citing = citingOrders("clause", clause.id);
    const nodes: MapNode[] = citing.map(({ order, links }) => ({
      key: order.id, label: orderLabel(order), sub: `${order.commission.toUpperCase()} · ${order.date ?? ""}`, href: order.path,
      kind: "document", side: "right", types: [...new Set(links.map((l) => l.type))] }));
    nodes.unshift({ key: reg.id, label: reg.short_title ?? reg.title, sub: "Parent regulation", href: reg.path, kind: "regulation", side: "left", types: ["made_under"] });
    const jsonLd = { "@context": "https://schema.org", "@type": "Legislation", name: `Regulation ${clause.number}, ${reg.title}`,
      legislationJurisdiction: "IN", isPartOf: { "@type": "Legislation", name: reg.title }, text: clause.text,
      legislationPassedBy: { "@type": "GovernmentOrganization", name: commissionName(reg.commission) } };
    return (
      <article>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <div className="meta"><span className="tag">{reg.commission.toUpperCase()}</span><Link href={reg.path}>{reg.title}</Link></div>
        <h1>Regulation {clause.number}{clause.heading ? `: ${clause.heading}` : ""}</h1>
        <blockquote className="card summary">{clause.text || <span className="muted">Heading only; see sub-clauses.</span>}</blockquote>
        <p className="muted small">In force {clause.in_force_from ? "from " + fmtDate(clause.in_force_from) : ""}{clause.in_force_to ? " to " + fmtDate(clause.in_force_to) : ""}.</p>
        <h2>How orders have used this clause</h2>
        {citing.length ? <>
          <SpiderMap center={{ label: `Reg. ${clause.number}`, sub: reg.short_title ?? reg.title }} nodes={nodes} typeLabels={site.link_types}
            title={`Orders citing regulation ${clause.number}`} />
          <ul className="links-list">{citing.map(({ order, links }) => (
            <li key={order.id}><Link href={order.path}>{order.title ?? orderLabel(order)}</Link> <span className="muted">{order.commission.toUpperCase()} · {fmtDate(order.date)}</span>
              {links.map((l, i) => <blockquote key={i}><strong>{linkTypeLabel(l.type)}</strong>: {l.excerpt}</blockquote>)}</li>
          ))}</ul></> : <p className="muted">No reviewed order cites this clause yet.</p>}
      </article>
    );
  }

  const cl = clausesOf(reg.id);
  return (
    <article>
      <div className="meta"><span className="tag">{reg.commission.toUpperCase()}</span>{reg.notified_date && <span>Notified {fmtDate(reg.notified_date)}</span>}</div>
      <h1>{reg.title}</h1>
      {reg.source_url && <p><a href={reg.source_url} rel="nofollow noopener">Official text on the commission&apos;s website</a></p>}
      <table className="list"><thead><tr><th>Clause</th><th>Heading</th><th>Orders citing it</th></tr></thead>
        <tbody>{cl.map((c) => <tr key={c.id}><td><Link href={c.path}>{c.number}</Link></td><td>{c.heading}</td><td>{citingOrders("clause", c.id).length}</td></tr>)}</tbody></table>
    </article>
  );
}
