import Link from "next/link";
import { KIND_LABEL, daysLeft, type Consultation } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export function Deadline({ c }: { c: Consultation }) {
  const left = daysLeft(c.comment_deadline);
  if (!c.comment_deadline) return <span className="muted">Comment deadline: see the public notice</span>;
  return (<span>Comments by <b>{fmtDate(c.comment_deadline)}</b>
    {left !== null && left >= 0 && <span className="tag">{left === 0 ? "last day" : `${left} day${left === 1 ? "" : "s"} left`}</span>}
    {left !== null && left < 0 && <span className="tag">closed</span>}</span>);
}

export default function ConsultationCard({ c }: { c: Consultation }) {
  return (
    <article className="card order-card">
      <div className="meta"><span className="tag">{c.commission.toUpperCase()}</span> {KIND_LABEL[c.kind]}
        {c.issued && <> · issued {fmtDate(c.issued)}</>}
        {c.sample && <span className="tag bad">Sample</span>}{c.draft && <span className="tag bad">Draft, not reviewed</span>}</div>
      <h3><Link href={c.path}>{c.title}</Link></h3>
      <p className="small"><Deadline c={c} />{c.hearing_date && <> · hearing {fmtDate(c.hearing_date)}</>}</p>
    </article>
  );
}
