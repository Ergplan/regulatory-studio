import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ConsultationList, { CommissionChips } from "@/components/ConsultationList";
import { BUILD_DAY, commissionName, consultations } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { commission: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] {
  return [...new Set(consultations.map((c) => c.commission))].map((commission) => ({ commission }));
}
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { commission } = await params;
  return { title: `${commission.toUpperCase()} draft regulations and consultations`,
    alternates: { canonical: `/consultations/${commission}` } };
}

export default async function CommissionConsultations({ params }: { params: Promise<Params> }) {
  const { commission } = await params;
  const items = consultations.filter((c) => c.commission === commission);
  if (!items.length) notFound();
  return (<>
    <h1>{commissionName(commission)}: draft regulations and consultations</h1>
    <p className="lede muted">Status as of {fmtDate(BUILD_DAY)}.</p>
    <CommissionChips current={commission} />
    <ConsultationList items={items} />
  </>);
}
