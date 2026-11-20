import type { Metadata } from "next";
import Link from "next/link";
import { weeks } from "@/lib/archive";
import { orderHeadline } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = { title: "Weekly archive", description: "Every order and draft regulation on Regulatory Studio, week by week.", alternates: { canonical: "/archive" } };

export default function Archive() {
  return (<>
    <p className="eyebrow">Archive</p>
    <h1>Week by week</h1>
    <p className="lede">Every order and draft regulation we have published, grouped by the week it was issued (Monday to Sunday).</p>
    {weeks.length ? <ul className="archive">{weeks.map((w) => {
      const n = w.orders.length + w.drafts.length;
      return (<li key={w.id}>
        <Link className="arch-week" href={w.path}>{fmtDate(w.from)} to {fmtDate(w.to)}</Link>
        <span className="arch-meta">{w.orders.length} order{w.orders.length === 1 ? "" : "s"}{w.drafts.length ? ` · ${w.drafts.length} draft regulation${w.drafts.length === 1 ? "" : "s"}` : ""}
          {w.pending ? ` · ${w.pending === n ? "all" : w.pending} awaiting legal review` : ""}{w.digest && <> · <Link href={w.digest}>weekly digest</Link></>}</span>
        <ul className="arch-heads">{w.orders.slice(0, 3).map((o) => <li key={o.id}><span className="lib-code">{o.commission.toUpperCase()}</span> <Link href={o.path}>{orderHeadline(o) || o.title}</Link></li>)}
          {w.orders.length === 0 && w.drafts.slice(0, 3).map((c) => <li key={c.id}><span className="lib-code">{c.commission.toUpperCase()}</span> <Link href={c.path}>{c.title}</Link></li>)}</ul>
      </li>);
    })}</ul> : <div className="card empty">The first week is being prepared.</div>}
  </>);
}
