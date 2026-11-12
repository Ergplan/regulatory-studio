import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ConsultationCard from "@/components/ConsultationCard";
import { GEO } from "@/components/IndiaMap";
import OrderCard from "@/components/OrderCard";
import ProjectCta from "@/components/ProjectCta";
import { byDeadline, consultations, orders, site } from "@/lib/data";

type Params = { c: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return Object.keys(site.commissions).map((c) => ({ c })); }
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { c } = await params;
  return { title: `${site.commissions[c]}: orders and drafts`, alternates: { canonical: `/commissions/${c}`, types: { "application/rss+xml": `/feeds/${c}.xml` } } };
}
export default async function Commission({ params }: { params: Promise<Params> }) {
  const { c } = await params;
  if (!site.commissions[c]) notFound();
  const list = orders.filter((o) => o.commission === c);
  const drafts = consultations.filter((x) => x.commission === c).sort(byDeadline);
  const place = GEO[c]?.national ? "India" : GEO[c]?.place ?? "this state";
  const empty = !list.length && !drafts.length;
  return (<>
    <p className="eyebrow">{GEO[c]?.place ?? "Commission"}</p>
    <h1>{site.commissions[c]}</h1>
    <p className="muted">{list.length} order{list.length === 1 ? "" : "s"} · {drafts.length} draft{drafts.length === 1 ? "" : "s"} analysed{site.preview ? " (awaiting legal review)" : ""} ·{" "}
      <a href={`/feeds/${c}.xml`}>RSS for this commission</a></p>
    {empty && <div className="glass empty-state"><p>We have not published analysis for this commission yet. Coverage is being added in order of what readers ask about.</p></div>}
    <ProjectCta ask={`Request an assessment for a project in ${place}`} about={`A project in ${place} (${c.toUpperCase()})`} path={`/commissions/${c}`} compact={!empty}
      lead={empty ? `Have a plant or project in ${place}? Ask for an assessment now. A review answers:` : `Have a plant or project in ${place}? Ask what these mean for it.`} />
    {drafts.length > 0 && <><h2>Draft regulations</h2><div className="grid">{drafts.map((x) => <ConsultationCard key={x.id} c={x} />)}</div></>}
    {list.length > 0 && <><h2>Orders</h2><div className="grid">{list.map((o) => <OrderCard key={o.id} o={o} />)}</div></>}
    <p className="small"><Link href="/consultations">All consultations</Link> · <Link href="/orders">All orders</Link></p>
  </>);
}
