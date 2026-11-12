import type { Metadata } from "next";
import Link from "next/link";
import GroupIcon from "@/components/GroupIcon";
import StudioDesk, { type DeskDraft } from "@/components/StudioDesk";
import { GROUPS, byDeadline, commentable, commissionName, consultations, isOpen } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Studio: draft your comments",
  description: "Pick who you are and a draft electricity regulation that is open for comment, and get comments prepared from the draft's own text, ready to edit and file.",
  alternates: { canonical: "/studio" },
};

export default function Studio() {
  const open = consultations.filter(commentable).sort(byDeadline)
    .sort((a, b) => Object.keys(b.comments ?? {}).length - Object.keys(a.comments ?? {}).length);
  const drafts: DeskDraft[] = open.map((c) => ({
    id: c.id, title: c.title, commission: c.commission, commissionName: commissionName(c.commission), path: c.path, deadline: c.comment_deadline,
    deadlineLabel: !isOpen(c) ? `listed deadline ${fmtDate(c.comment_deadline ?? c.hearing_date)} has passed: confirm with the commission`
      : c.comment_deadline ? `comments by ${fmtDate(c.comment_deadline)}` : "deadline in the public notice",
    summary: c.summary, proposes: c.proposes,
    effect: Object.fromEntries(GROUPS.filter(([g]) => c.impact?.stakeholders[g]).map(([g]) => [g, c.impact!.stakeholders[g]!.comment])),
    comments: c.comments ?? {} }));
  const prepared = open.filter((c) => Object.keys(c.comments ?? {}).length);
  return (<>
    <p className="eyebrow">Studio</p>
    <h1 className="hero">Draft your comments.</h1>
    <p className="lede">Say who you are, pick a draft regulation that is open for comment, and start from comments prepared from the
      draft&apos;s own text. Each point names the provision and the paragraph it rests on. Edit, then save the file.</p>
    <StudioDesk drafts={drafts} groups={GROUPS} />
    {prepared.length > 0 && (
      <section className="prepared">
        <h2>Prepared comments</h2>
        <p className="muted small">Everything the desk above draws on, as plain text.</p>
        {prepared.map((c) => (
          <div key={c.id} className="glass">
            <p className="meta">{c.commission.toUpperCase()} · {!isOpen(c) ? `listed deadline ${fmtDate(c.comment_deadline ?? c.hearing_date)} has passed` : c.comment_deadline ? `comments by ${fmtDate(c.comment_deadline)}` : "deadline in the public notice"}</p>
            <h3><Link href={c.path}>{c.title}</Link></h3>
            {GROUPS.filter(([g]) => c.comments?.[g]).map(([g, , long]) => { const k = c.comments![g]; return (
              <details key={g}><summary><GroupIcon g={g} size={18} /> {long}{k.draft ? " · AI draft, not reviewed" : ""}</summary>
                <p>{k.position}</p>
                <ol>{k.points.map((p, i) => <li key={i}><b>{p.clause}.</b> {p.comment}{p.suggestion && <> <i>Requested change:</i> {p.suggestion}</>}</li>)}</ol>
              </details>); })}
          </div>))}
      </section>)}
  </>);
}
