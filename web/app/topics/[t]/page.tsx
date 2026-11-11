import type { Metadata } from "next";
import { notFound } from "next/navigation";
import OrderCard from "@/components/OrderCard";
import { orders, site } from "@/lib/data";

type Params = { t: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return Object.keys(site.topics).map((t) => ({ t })); }
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { t } = await params;
  return { title: `${site.topics[t]}: regulatory orders`, alternates: { canonical: `/topics/${t}` } };
}
export default async function Topic({ params }: { params: Promise<Params> }) {
  const { t } = await params;
  if (!site.topics[t]) notFound();
  const list = orders.filter((o) => o.topics.includes(t));
  return (<><h1>{site.topics[t]}</h1><p className="muted">{list.length} reviewed orders across all commissions · <a href={`/feeds/topic-${t}.xml`}>RSS for this topic</a></p>
    {list.length ? <div className="grid">{list.map((o) => <OrderCard key={o.id} o={o} />)}</div> : <div className="card empty">No reviewed orders on this topic yet.</div>}</>);
}
