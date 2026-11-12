import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Brief from "@/components/Brief";
import Impact from "@/components/Impact";
import ProjectCta, { askFor } from "@/components/ProjectCta";
import SpiderMap, { type MapNode } from "@/components/SpiderMap";
import { citingOrders, clauses, clausesOf, commissionName, linkTypeLabel, orderLabel, regName, regulationById, regulations, site } from "@/lib/data";
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
      key: order.id, label: orderLabel(order), sub: `${order.commission.toUpperCase()} · ${fmtDate(order.date)}`, href: order.path,
      kind: "document", side: "right", types: [...new Set(links.map((l) => l.type))] }));
    nodes.unshift({ key: reg.id, label: regName(reg), sub: `${reg.commission.toUpperCase()} · parent regulation`, href: reg.path, kind: "regulation", side: "left", types: ["part_of"] });
    const jsonLd = { "@context": "https://schema.org", "@type": "Legislation", name: `Regulation ${clause.number}, ${reg.title}`,
      legislationJurisdiction: "IN", isPartOf: { "@type": "Legislation", name: reg.title }, text: clause.text,
      legislationPassedBy: { "@type": "GovernmentOrganization", name: commissionName(reg.commission) } };
    return (
      <article>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <div className="meta"><span className="tag">{reg.commission.toUpperCase()}</span><Link href={reg.path}>{reg.title}</Link></div>
        <h1>Regulation {clause.number}{clause.heading ? `: ${clause.heading}` : ""}</h1>
        <blockquote className="card summary">{clause.text || <span className="muted">Heading only; see sub-clauses.</span>}</blockquote>
        {clause.in_force_to
          ? <p className="bad small">No longer in force: omitted with effect from the day after {fmtDate(clause.in_force_to)}.</p>
          : <p className="muted small">In force{clause.in_force_from ? " from " + fmtDate(clause.in_force_from) : ""}.</p>}
        {clause.versions && clause.versions.length > 0 && (
          <details className="card"><summary>Earlier wording ({clause.versions.length})</summary>
            {clause.versions.map((v, i) => (
              <div key={i} style={{ marginTop: 12 }}>
                <div className="small muted">In force {v.in_force_from ? "from " + fmtDate(v.in_force_from) + " " : ""}to {fmtDate(v.in_force_to)}</div>
                <blockquote className="summary" style={{ margin: "4px 0 0" }}>{v.text}</blockquote>
              </div>))}
            <p className="small muted">Orders passed while earlier wording was in force applied that wording.</p>
          </details>)}
        <h2>How orders have used this clause</h2>
        {citing.length ? <>
          <SpiderMap center={{ label: `Regulation ${clause.number}`, sub: `${reg.commission.toUpperCase()} · ${regName(reg)}` }} nodes={nodes} typeLabels={site.link_types}
            title={`Orders citing regulation ${clause.number}`} />
          <ul className="links-list" id="all-links">{citing.map(({ order, links }) => (
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
      {reg.impact?.headline ? <><h1>{reg.impact.headline}</h1><p className="formal">{reg.title}</p></> : <h1>{reg.title}</h1>}
      <p>{reg.pdf && <><a href={reg.pdf}>Read the regulations (PDF)</a> · </>}
        {reg.source_url && <a href={reg.source_url} rel="nofollow noopener">{reg.source_listing ? "The commission's regulations listing" : "On the commission's website"}</a>}</p>
      {reg.impact && <Brief impact={reg.impact} status={`Notified regulation${reg.notified_date ? `, ${fmtDate(reg.notified_date)}` : ""}: in force`}
        analysis={site.preview ? "prepared with AI, awaiting legal review" : "reviewed by the legal team"}
        ask={askFor({ impact: reg.impact, text: reg.title })} about={reg.title} path={reg.path} />}
      {reg.impact && <Impact impact={reg.impact} pdf={reg.pdf} draft={site.preview} />}
      {!reg.impact && <ProjectCta ask={askFor({ text: reg.title })} about={reg.title} path={reg.path} compact />}
      <h2>Clauses</h2>
      <table className="list"><thead><tr><th>Clause</th><th>Heading</th><th>Orders citing it</th></tr></thead>
        <tbody>{cl.map((c) => <tr key={c.id}><td><Link href={c.path}>{c.number}</Link></td><td>{c.heading}{c.in_force_to && <span className="tag bad"> omitted</span>}{c.versions && c.versions.length > 0 && <span className="tag"> amended</span>}</td><td>{citingOrders("clause", c.id).length}</td></tr>)}</tbody></table>
    </article>
  );
}
