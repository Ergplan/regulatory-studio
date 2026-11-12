import type { Metadata } from "next";
import Link from "next/link";
import AnalysisBlock, { HighBadge, type Block } from "@/components/AnalysisBlock";
import GroupIcon from "@/components/GroupIcon";
import { GEO } from "@/components/IndiaMap";
import Stage from "@/components/Stage";
import { BUILD_DAY, GROUPS, byDeadline, commentable, commissionName, consultations, isOpen, site, type Consultation } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Draft regulations and public consultations",
  description: "Draft regulations, amendments and consultation papers from CERC and state electricity commissions, by commission, with comment deadlines, the groups each one affects, and the ones our team rates as high impact.",
  alternates: { canonical: "/consultations" },
};

const high = (c: Consultation) => Number(c.rating === "high");
const block = (c: Consultation): Block => ({
  id: c.id, href: c.path, kind: "Draft", title: c.title, summary: c.summary, date: c.issued ?? "", impact: c.impact, rating: c.rating,
  draftable: commentable(c), unreviewed: !!c.draft, closed: !isOpen(c),
  tab: !isOpen(c) ? `Listed deadline ${fmtDate(c.comment_deadline ?? c.hearing_date)} passed` : c.comment_deadline ? `Comments by ${fmtDate(c.comment_deadline)}` : "Open · deadline in the public notice",
});

export default function Consultations() {
  const codes = Object.keys(GEO).filter((k) => site.commissions[k]);
  const chapters = codes.map((code) => {
    const mine = consultations.filter((c) => c.commission === code);
    const open = mine.filter(isOpen).sort((a, b) => high(b) - high(a) || byDeadline(a, b));
    const closed = mine.filter((c) => !isOpen(c)).sort((a, b) => high(b) - high(a) || (b.issued ?? "").localeCompare(a.issued ?? ""));
    return { code, open, closed, n: mine.length };
  });
  const live = chapters.filter((c) => c.n);
  const nOpen = consultations.filter(isOpen).length;
  const top = consultations.filter((c) => c.rating === "high").sort(byDeadline);
  const areas = GROUPS.map(([g, short, long]) => ({ g, short, long, n: consultations.filter((c) => isOpen(c) && c.impact?.stakeholders[g]).length }));

  return (
    <div className="cover">
      <Stage items={chapters.map((c) => ({ code: c.code, href: c.n ? `#c-${c.code}` : `/commissions/${c.code}`, idle: !c.n,
        note: c.n ? [c.open.length ? `${c.open.length} open` : "", c.closed.length ? `${c.closed.length} closed` : ""].filter(Boolean).join(" · ") : "none listed" }))} />
      <div className="flow">
        <section className="cover-hero short">
          <p className="eyebrow">Consultations · status as of {fmtDate(BUILD_DAY)}</p>
          <h1 className="hero">Open for comment.</h1>
          <p className="lede">{nOpen} draft regulation{nOpen === 1 ? "" : "s"} open across {live.filter((c) => c.open.length).length} commission{live.filter((c) => c.open.length).length === 1 ? "" : "s"}:
            what each would change, the last date for comments, and whom it touches. These are proposals, not law.</p>
          <p className="cta"><Link href="/studio" className="btn">Cues for your comments</Link><Link href="/impact" className="btn ghost">Impact map</Link></p>
        </section>

        <section className="glass areas-box">
          <h2 className="label">Impact areas</h2>
          <ul className="areas">{areas.map((a) => (
            <li key={a.g} className={a.n ? "" : "zero"}><Link href={`/impact/${a.g}`} title={a.long}><GroupIcon g={a.g} size={24} /><span>{a.short}</span><b>{a.n}</b></Link></li>))}</ul>
          <p className="muted small">Open drafts assessed so far that affect each group. <HighBadge /> is our team&apos;s overall rating, given during legal review; it is not generated.</p>
        </section>

        {top.length > 0 && (
          <section className="glass updates-box tight">
            <h2 className="label">Rated high impact</h2>
            <ol className="updates">{top.map((c) => (
              <li key={c.id}><a href={`#u-${c.id.slice(0, 10)}`}><span className="u-code">{c.commission.toUpperCase()}</span>
                <span className="u-title">{c.title}</span>
                <span className="u-meta">{isOpen(c) ? (c.comment_deadline ? `comments by ${fmtDate(c.comment_deadline)}` : "open") : "closed"}</span></a></li>))}</ol>
          </section>)}

        {live.length === 0 && <div className="glass empty">No draft regulations are listed yet.</div>}
        {live.map((c) => (
          <section key={c.code} className="chapter" id={`c-${c.code}`} data-chapter={c.code}>
            <header className="chapter-head rise">
              <p className="eyebrow">{[GEO[c.code].place, c.open.length ? `${c.open.length} open` : "", c.closed.length ? `${c.closed.length} closed` : ""].filter(Boolean).join(" · ")}</p>
              <h2><Link href={`/consultations/${c.code}`}>{commissionName(c.code)}</Link></h2>
            </header>
            {c.open.map((x) => <AnalysisBlock key={x.id} {...block(x)} showAreasEmpty />)}
            {c.closed.length > 0 && <p className="sub-label rise">Closed, final regulations awaited</p>}
            {c.closed.map((x) => <AnalysisBlock key={x.id} {...block(x)} showAreasEmpty />)}
          </section>))}
      </div>
    </div>
  );
}
