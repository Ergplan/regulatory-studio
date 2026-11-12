import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Deadline } from "@/components/ConsultationCard";
import { KIND_LABEL, commissionName, consultations, type Consultation } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { commission: string; slug: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] {
  return consultations.map((c) => { const [, , commission, slug] = c.path.split("/"); return { commission, slug }; });
}
const find = (p: Params): Consultation | undefined => consultations.find((c) => c.path === `/consultations/${p.commission}/${p.slug}`);

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const c = find(await params);
  if (!c) return {};
  return { title: `${c.title} (${c.commission.toUpperCase()})`, description: c.summary?.slice(0, 160),
    alternates: { canonical: c.path, types: { "text/markdown": c.path + ".md" } },
    robots: c.sample ? { index: false } : undefined };
}

export default async function ConsultationPage({ params }: { params: Promise<Params> }) {
  const c = find(await params);
  if (!c) notFound();
  return (
    <div className="two">
      <section>
        <p className="muted">{commissionName(c.commission)} · {KIND_LABEL[c.kind]}{c.issued && <> · issued {fmtDate(c.issued)}</>}</p>
        <h1>{c.title}</h1>
        <p className="lede"><Deadline c={c} />{c.hearing_date && <> · public hearing {fmtDate(c.hearing_date)}</>}</p>
        <h2>What is proposed</h2>
        <p>{c.summary}</p>
        {c.proposes.length > 0 && <ul>{c.proposes.map((p, i) => <li key={i}>{p}</li>)}</ul>}
        {c.amends && <p className="muted">Would amend: {c.amends}</p>}
      </section>
      <aside>
        <h2>Documents</h2>
        <ul><li><a href={c.source_url} rel="nofollow noopener">The draft (PDF)</a></li>
          {c.related.map((r) => <li key={r.url}><a href={r.url} rel="nofollow noopener">{r.label}</a></li>)}</ul>
        <p className="note">{c.draft
          ? <><b>Draft, not yet reviewed.</b> This summary was drafted by AI and is waiting for the legal team.</>
          : <>Reviewed by the Regulatory Studio legal team on {fmtDate(c.approved_at)}.</>} This is a proposal published for
          comment, not a notified regulation. Check the commission&apos;s public notice for how to send comments.</p>
      </aside>
    </div>
  );
}
