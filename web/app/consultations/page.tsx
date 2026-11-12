import type { Metadata } from "next";
import ConsultationList, { CommissionChips } from "@/components/ConsultationList";
import { BUILD_DAY, consultations } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Draft regulations and public consultations",
  description: "Draft regulations, amendments and consultation papers from CERC and state electricity commissions, with comment deadlines and hearing dates.",
  alternates: { canonical: "/consultations" },
};

export default function Consultations() {
  return (<>
    <h1>Draft regulations and public consultations</h1>
    <p className="lede muted">Proposals the commissions have published for comment: what they would change, the last date
      for comments and any public hearing. These are proposals, not law. Status as of {fmtDate(BUILD_DAY)}.</p>
    <CommissionChips />
    <ConsultationList items={consultations} />
  </>);
}
