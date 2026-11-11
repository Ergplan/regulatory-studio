import type { Metadata } from "next";
import { notFound } from "next/navigation";
import OrderCard from "@/components/OrderCard";
import { orders, site } from "@/lib/data";

type Params = { c: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return Object.keys(site.commissions).map((c) => ({ c })); }
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { c } = await params;
  return { title: `${site.commissions[c]} orders`, alternates: { canonical: `/commissions/${c}`, types: { "application/rss+xml": `/feeds/${c}.xml` } } };
}
export default async function Commission({ params }: { params: Promise<Params> }) {
  const { c } = await params;
  if (!site.commissions[c]) notFound();
  const list = orders.filter((o) => o.commission === c);
  return (<><h1>{site.commissions[c]}</h1><p className="muted">{list.length} reviewed orders · <a href={`/feeds/${c}.xml`}>RSS for this commission</a></p>
    {list.length ? <div className="grid">{list.map((o) => <OrderCard key={o.id} o={o} />)}</div> : <div className="card empty">No reviewed orders yet.</div>}</>);
}
