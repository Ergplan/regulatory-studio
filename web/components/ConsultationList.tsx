import Link from "next/link";
import ConsultationCard from "@/components/ConsultationCard";
import { byDeadline, commissionName, consultations, isOpen, type Consultation } from "@/lib/data";

export function CommissionChips({ current }: { current?: string }) {
  const counts = new Map<string, number>();
  for (const c of consultations) counts.set(c.commission, (counts.get(c.commission) ?? 0) + 1);
  return (
    <nav className="topics" aria-label="Filter by commission">
      <Link className={`chip${current ? "" : " active"}`} href="/consultations">All ({consultations.length})</Link>
      {[...counts.entries()].sort().map(([k, n]) => (
        <Link key={k} className={`chip${current === k ? " active" : ""}`} href={`/consultations/${k}`} title={commissionName(k)}>
          {k.toUpperCase()} ({n})</Link>))}
    </nav>
  );
}

export default function ConsultationList({ items }: { items: Consultation[] }) {
  const open = items.filter(isOpen).sort(byDeadline);
  const closed = items.filter((c) => !isOpen(c)).sort(byDeadline).reverse();
  return (<>
    <h2>Open for comment ({open.length})</h2>
    {open.length ? <div className="grid">{open.map((c) => <ConsultationCard key={c.id} c={c} />)}</div>
      : <div className="card empty">No open consultations right now.</div>}
    {closed.length > 0 && (<><h2>Closed, final regulations awaited ({closed.length})</h2>
      <div className="grid">{closed.map((c) => <ConsultationCard key={c.id} c={c} />)}</div></>)}
  </>);
}
