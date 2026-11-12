import type { Metadata } from "next";
import { notFound } from "next/navigation";
import OrderCard from "@/components/OrderCard";
import Subscribe from "@/components/Subscribe";
import { digests, orderById } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { week: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return digests.map((d) => ({ week: d.id.toLowerCase() })); }
const find = (w: string) => digests.find((d) => d.id.toLowerCase() === w);
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const d = find((await params).week);
  return d ? { title: `Weekly digest, ${fmtDate(d.from)} to ${fmtDate(d.to)}`, description: d.intro.slice(0, 160), alternates: { canonical: d.path } } : {};
}
export default async function Week({ params }: { params: Promise<Params> }) {
  const d = find((await params).week);
  if (!d) notFound();
  return (<><h1>Weekly digest: {fmtDate(d.from)} to {fmtDate(d.to)}</h1><p className="lede">{d.intro}</p>
    <div className="grid">{d.items.map((id) => orderById.get(id)).filter(Boolean).map((o) => <OrderCard key={o!.id} o={o!} />)}</div>
    {d.draft ? <p className="note"><b>Analysis awaiting legal review.</b> This digest was prepared with AI and has not been checked by the legal team yet.</p>
      : <p className="note">Reviewed and approved by the Regulatory Studio legal team on {fmtDate(d.approved_at)}.</p>}
    <div className="glass digest-signup"><Subscribe /></div></>);
}
