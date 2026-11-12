import { LibraryRow, draftRow } from "@/components/Library";
import { daysLeft, type Consultation } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export function Deadline({ c }: { c: Consultation }) {
  const left = daysLeft(c.comment_deadline);
  if (!c.comment_deadline) return <span>Deadline not stated by the commission: <b>check the public notice</b></span>;
  return (<span>Comments by <b>{fmtDate(c.comment_deadline)}</b>
    {left !== null && left >= 0 && <span className="tag">{left === 0 ? "last day" : `${left} day${left === 1 ? "" : "s"} left`}</span>}
    {left !== null && left < 0 && <span className="tag">closed</span>}</span>);
}

export default function ConsultationCard({ c }: { c: Consultation }) {
  return <LibraryRow r={draftRow(c)} as="article" />;
}
