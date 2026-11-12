import Trail from "@/components/Trail";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HighBadge } from "@/components/AnalysisBlock";
import Brief from "@/components/Brief";
import Charts, { consultationTimeline } from "@/components/Charts";
import Impact from "@/components/Impact";
import ProjectCta, { askFor } from "@/components/ProjectCta";
import { Deadline } from "@/components/ConsultationCard";
import { KIND_LABEL, commissionName, consultationStatus, consultations, isOpen, type Consultation } from "@/lib/data";
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
  const own = c.figures ?? []; const auto = own.some((f) => f.type === "timeline") ? null : consultationTimeline(c);
  const figs = auto ? [...own, auto] : own;
  const ask = askFor({ consultation: true, closed: !isOpen(c), impact: c.impact, text: `${c.title} ${c.summary}` });
  return (<>
    <div className="head-block">
        <p className="muted">{commissionName(c.commission)} · {KIND_LABEL[c.kind]}{c.issued && <> · issued {fmtDate(c.issued)}</>}</p>
        {c.rating === "high" && <p><HighBadge /></p>}
        {c.impact?.headline ? <><h1>{c.impact.headline}</h1><p className="formal">{c.title}</p></> : <h1>{c.title}</h1>}
        <p className="lede"><Deadline c={c} />{c.hearing_date && <> · public hearing {fmtDate(c.hearing_date)}</>}</p>
        {c.impact && <Brief impact={c.impact} status={`Proposal, not law · ${consultationStatus(c)}`}
          analysis={c.draft ? "prepared with AI, awaiting legal review" : `reviewed ${fmtDate(c.approved_at)}${c.reviewed_by ? ` by ${c.reviewed_by}` : ""}`}
          ask={ask} about={c.title} path={c.path} />}
        <Trail checked={c.checked} draft={c.draft} approvedAt={c.approved_at} reviewer={c.reviewed_by} />
    </div>
    <div className="two">
      <section>
        <h2>What is proposed</h2>
        <p>{c.summary}</p>
        {c.proposes.length > 0 && <ul>{c.proposes.map((p, i) => <li key={i}>{p}</li>)}</ul>}
        {c.amends && <p className="muted">Would amend: {c.amends}</p>}
        <Charts figures={figs} pdf={c.source_url} pending={c.draft} />
        {c.impact && <Impact impact={c.impact} pdf={c.source_url} draft={c.draft} />}
        {!c.impact && <ProjectCta ask={ask} about={c.title} path={c.path} />}
      </section>
      <aside>
        <div className="glass studio-cta">
          <p className="eyebrow">Studio</p>
          <p>{Object.keys(c.comments ?? {}).length
            ? `Cues for comments are ready for ${Object.keys(c.comments!).length} stakeholder group${Object.keys(c.comments!).length === 1 ? "" : "s"}. For a full analysis, leave a request.`
            : "See the points worth commenting on, or leave a request for a full analysis."}</p>
          <Link href={`/studio?draft=${c.id.slice(0, 10)}`} className="btn">Cues for your comments</Link>
        </div>
        <h2>Documents</h2>
        <ul><li><a href={c.source_url} rel="nofollow noopener">The draft (PDF)</a></li>
          {c.related.map((r) => <li key={r.url}><a href={r.url} rel="nofollow noopener">{r.label}</a></li>)}</ul>
        <p className="note">{c.draft
          ? <><b>Analysis awaiting legal review.</b> This summary was prepared with AI and has not been checked by the legal team yet.</>
          : <>Reviewed by the Regulatory Studio legal team on {fmtDate(c.approved_at)}.</>} This is a proposal published for
          comment, not a notified regulation. Check the commission&apos;s public notice for how to send comments.</p>
      </aside>
    </div>
  </>);
}
