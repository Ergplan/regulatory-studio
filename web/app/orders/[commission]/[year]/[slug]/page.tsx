import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Brief from "@/components/Brief";
import Impact from "@/components/Impact";
import ProjectCta, { askFor } from "@/components/ProjectCta";
import SpiderMap, { type MapNode } from "@/components/SpiderMap";
import { SITE_URL, commissionName, linkTypeLabel, orderLabel, orders, site, targetInfo, topicName, type Order } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { commission: string; year: string; slug: string };

export const dynamicParams = false;
export function generateStaticParams(): Params[] {
  return orders.map((o) => { const [, , commission, year, slug] = o.path.split("/"); return { commission, year, slug }; });
}

function find(p: Params): Order | undefined {
  return orders.find((o) => o.path === `/orders/${p.commission}/${p.year}/${p.slug}`);
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const o = find(await params);
  if (!o) return {};
  const title = `${o.title ?? orderLabel(o)} (${o.commission.toUpperCase()}${o.date ? ", " + o.date.slice(0, 4) : ""})`;
  return {
    title, description: o.issue?.slice(0, 160),
    alternates: { canonical: o.path, types: { "text/markdown": o.path + ".md" } },
    openGraph: { title, description: o.issue?.slice(0, 200), type: "article" },
    robots: o.sample ? { index: false } : undefined,
  };
}

export default async function OrderPage({ params }: { params: Promise<Params> }) {
  const o = find(await params);
  if (!o) notFound();

  // Group links by target so each provision appears once on the map.
  const byTarget = new Map<string, { kind: string; target: string; types: Set<string> }>();
  for (const l of o.links) {
    const k = l.kind + ":" + l.target;
    if (!byTarget.has(k)) byTarget.set(k, { kind: l.kind, target: l.target, types: new Set() });
    byTarget.get(k)!.types.add(l.type);
  }
  const nodes: MapNode[] = [];
  for (const [k, v] of byTarget) {
    const info = targetInfo(v.kind as never, v.target);
    if (!info) continue;
    nodes.push({ key: k, label: info.label, sub: info.sub, href: info.href, kind: v.kind, types: [...v.types],
      side: v.kind === "document" ? "right" : "left" });
  }
  // Later decisions that cite this order (appeals, follow-ons) also sit on the right.
  for (const other of orders) {
    if (other.id === o.id) continue;
    const ls = other.links.filter((l) => l.kind === "document" && l.target === o.id);
    if (ls.length) nodes.push({ key: "in:" + other.id, label: orderLabel(other), sub: `${other.commission.toUpperCase()} · ${other.date ?? ""}`,
      href: other.path, kind: "document", types: [...new Set(ls.map((l) => l.type))], side: "right" });
  }

  const jsonLd = {
    "@context": "https://schema.org", "@type": "Article", headline: o.title ?? orderLabel(o),
    about: o.issue, abstract: o.summary, datePublished: o.approved_at ?? o.date, dateModified: o.revised_at ?? o.approved_at ?? o.date,
    author: { "@type": "Organization", name: "Regulatory Studio" },
    publisher: { "@type": "Organization", name: "Regulatory Studio", parentOrganization: { "@type": "Organization", name: "jouleWise" } },
    isBasedOn: { "@type": "Legislation", name: o.case_number ?? o.title, legislationDate: o.date,
      legislationJurisdiction: "IN", legislationPassedBy: { "@type": "GovernmentOrganization", name: commissionName(o.commission) }, url: o.source_url },
    url: SITE_URL + o.path, keywords: o.topics.map(topicName).join(", "),
  };

  const about = o.title ?? orderLabel(o);
  const ask = askFor({ impact: o.impact, text: [o.title, o.issue, ...o.topics].join(" ") });
  const analysis = o.draft ? "prepared with AI, awaiting legal review" : `reviewed ${fmtDate(o.approved_at)}${o.reviewed_by ? ` by ${o.reviewed_by}` : ""}`;

  return (
    <article>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="meta"><Link href={`/commissions/${o.commission}`} className="tag">{o.commission.toUpperCase()}</Link>
        {o.date && <span>Order dated {fmtDate(o.date)}</span>}{o.sample && <span className="tag bad">Sample, not a real order</span>}</div>
      {o.impact?.headline
        ? <><h1>{o.impact.headline}</h1><p className="formal">{o.title ?? orderLabel(o)}{o.case_number && o.title ? ` · ${o.case_number}` : ""} · {commissionName(o.commission)}</p></>
        : <><h1>{o.title ?? orderLabel(o)}</h1>{o.case_number && <p className="muted">{o.case_number} · {commissionName(o.commission)}</p>}</>}
      {o.impact && <Brief impact={o.impact} status={`Order of ${fmtDate(o.date)}: binds the parties`} analysis={analysis}
        ask={ask} about={about} path={o.path} />}

      <div className="two">
        <section>
          <h2>Summary</h2>
          <p className="summary">{o.summary}</p>
          <dl className="facts">
            <dt>Issue</dt><dd>{o.issue}</dd>
            <dt>Outcome</dt><dd>{o.outcome}</dd>
            {o.parties.length > 0 && <><dt>Parties</dt><dd>{o.parties.map((p) => `${p.name} (${p.role})`).join("; ")}</dd></>}
            <dt>Topics</dt><dd>{o.topics.map((t) => <Link key={t} href={`/topics/${t}`} className="chip">{topicName(t)}</Link>)}</dd>
          </dl>
          {o.impact && <Impact impact={o.impact} pdf={o.pdf} draft={o.draft} />}
          {!o.impact && <ProjectCta ask={ask} about={about} path={o.path} />}
        </section>
        <aside>
          <h2>Original order</h2>
          <p>{o.pdf && <><a href={o.pdf}>Read the order (PDF)</a><br /></>}
            <a href={o.source_url} rel="nofollow noopener">{o.source_listing ? `The commission's orders listing${o.case_number ? ` (look for ${o.case_number})` : ""}` : "On the commission's website"}</a></p>
          {o.draft
            ? <p className="note"><b>Analysis awaiting legal review.</b> This summary and its links were prepared with AI and have not been checked by the legal team yet. Read the original order.</p>
            : <p className="note">Reviewed by the Regulatory Studio legal team on {fmtDate(o.approved_at)}{o.revised_at && <>, revised {fmtDate(o.revised_at)}</>}.
            This summary is for information only and is not legal advice.</p>}
        </aside>
      </div>

      <h2>Order trace</h2>
      {nodes.length ? <SpiderMap center={{ label: orderLabel(o), sub: `${o.commission.toUpperCase()} · ${fmtDate(o.date)}` }} nodes={nodes}
        typeLabels={site.link_types} title={`Provisions and decisions linked to ${orderLabel(o)}`} />
        : <p className="muted">No reviewed links for this order yet.</p>}

      <h2>Every link, with the passage it rests on</h2>
      <ul className="links-list" id="all-links">{o.links.map((l, i) => {
        const info = targetInfo(l.kind, l.target);
        return (
          <li key={i}><strong>{linkTypeLabel(l.type)}</strong> {info ? <Link href={info.href}>{info.label}</Link> : l.target}
            {info?.sub && <span className="muted"> · {info.sub}</span>}
            <div className="small muted">Cited as “{l.cited_as}”, paragraph {l.pid}{l.page ? (o.pdf ? <>, <a href={`${o.pdf}#page=${l.page}`}>page {l.page}</a></> : <>, page {l.page}</>) : null}</div>
            <blockquote>{l.excerpt}</blockquote></li>
        );
      })}</ul>
    </article>
  );
}
