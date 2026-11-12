import Link from "next/link";
import type { Order } from "@/lib/data";
import { orderLabel, topicName } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export default function OrderCard({ o, showSummary = true }: { o: Order; showSummary?: boolean }) {
  return (
    <article className="card order-card">
      <div className="meta"><span className="tag">{o.commission.toUpperCase()}</span> {fmtDate(o.date)}
        {o.sample && <span className="tag bad">Sample</span>}
        {o.draft && <span className="tag bad">Analysis awaiting review</span>}</div>
      <h3><Link href={o.path}>{o.title ?? orderLabel(o)}</Link></h3>
      {o.case_number && o.title && <div className="muted small">{o.case_number}</div>}
      {showSummary && <p>{o.issue}</p>}
      <div className="topics">{o.topics.map((t) => <Link key={t} href={`/topics/${t}`} className="chip">{topicName(t)}</Link>)}</div>
    </article>
  );
}
