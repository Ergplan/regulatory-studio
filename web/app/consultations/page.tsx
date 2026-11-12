import type { Metadata } from "next";
import ConsultationCard from "@/components/ConsultationCard";
import { BUILD_DAY, consultations, isOpen } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Draft regulations and public consultations",
  description: "Draft regulations, amendments and consultation papers from CERC and state electricity commissions, with comment deadlines and hearing dates.",
  alternates: { canonical: "/consultations" },
};

export default function Consultations() {
  const open = consultations.filter(isOpen).sort((a, b) => (a.comment_deadline ?? a.hearing_date ?? "9").localeCompare(b.comment_deadline ?? b.hearing_date ?? "9"));
  const closed = consultations.filter((c) => !isOpen(c));
  return (
    <>
      <h1>Draft regulations and public consultations</h1>
      <p className="lede muted">Proposals the commissions have published for comment: what they would change, the last date
        for comments and any public hearing. These are proposals, not law. Status as of {fmtDate(BUILD_DAY)}.</p>
      <h2>Open for comment ({open.length})</h2>
      {open.length ? <div className="grid">{open.map((c) => <ConsultationCard key={c.id} c={c} />)}</div>
        : <div className="card empty">No open consultations right now.</div>}
      {closed.length > 0 && (<><h2>Closed, final regulations awaited ({closed.length})</h2>
        <div className="grid">{closed.map((c) => <ConsultationCard key={c.id} c={c} />)}</div></>)}
    </>
  );
}
