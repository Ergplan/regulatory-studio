import Link from "next/link";
import GroupIcon from "@/components/GroupIcon";
import AnalysisBlock, { HighBadge, type Block } from "@/components/AnalysisBlock";
import { GEO } from "@/components/IndiaMap";
import Stage from "@/components/Stage";
import Subscribe from "@/components/Subscribe";
import { byDeadline, commentable, commissionName, consultations, isOpen, orderLabel, orders, regulations, site, type GroupKey } from "@/lib/data";
import { fmtDate } from "@/lib/format";

const PER_CHAPTER = 3;
const CHOICES: [GroupKey | null, string, string, string][] = [
  ["ci_consumers", "Industrial or commercial energy buyer", "Open access, tariffs, renewable obligations", "/impact/ci_consumers"],
  ["captive", "Captive power user", "Capacity limits, contract demand, banking", "/impact/captive"],
  ["re_developers", "Renewable developer", "Transmission charges, deviation, tenders", "/impact/re_developers"],
  ["storage", "Storage developer", "BESS and pumped storage rules", "/impact/storage"],
  ["discoms", "Distribution licensee", "Procurement, obligations, deviation", "/impact/discoms"],
  [null, "Regulatory or legal team", "Open consultations and cues for comments", "/consultations"],
];

function blocksFor(code: string): { blocks: Block[]; total: number; drafts: number; orders: number } {
  const drafts = consultations.filter((c) => c.commission === code);
  const open = drafts.filter(isOpen).sort(byDeadline);
  const ords = orders.filter((o) => o.commission === code);
  const closed = drafts.filter((c) => !isOpen(c)).sort((a, b) => (b.issued ?? "").localeCompare(a.issued ?? ""));
  const all: Block[] = [
    ...[...open, ...closed].map((c) => ({ id: c.id, href: c.path, kind: "Draft" as const, title: c.title, summary: c.summary, date: c.issued ?? "",
      tab: !isOpen(c) ? `Draft · listed deadline ${fmtDate(c.comment_deadline ?? c.hearing_date)} passed` : c.comment_deadline ? `Draft · comments by ${fmtDate(c.comment_deadline)}` : "Draft · open for comment",
      impact: c.impact, draftable: commentable(c), unreviewed: !!c.draft, rating: c.rating })),
    ...ords.map((o) => ({ id: o.id, href: o.path, kind: "Order" as const, title: o.title ?? orderLabel(o), summary: o.summary, date: o.date ?? "",
      tab: `Order · ${fmtDate(o.date)}`, impact: o.impact, draftable: false, unreviewed: !!o.draft, rating: o.rating })),
  ];
  // rated high by the team first, then items with an impact assessment; otherwise drafts by deadline and orders by date
  all.sort((a, b) => Number(b.rating === "high") - Number(a.rating === "high") || Number(!!b.impact) - Number(!!a.impact));
  return { blocks: all.slice(0, PER_CHAPTER), total: all.length, drafts: drafts.length, orders: ords.length };
}

export default function Home() {
  const codes = Object.keys(GEO).filter((k) => site.commissions[k]);
  const chapters = codes.map((code) => ({ code, ...blocksFor(code) }));
  const live = chapters.filter((c) => c.blocks.length);
  const updates = live.flatMap((c) => c.blocks.map((b) => ({ ...b, code: c.code }))).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);

  return (<>
    <section className="cover-hero wide">
      <p className="eyebrow">Regulatory Studio · by <span className="j">joule</span>Wise × Urja Praxis</p>
      <h1 className="hero">See how changing power rules affect your cost and renewable plans.</h1>
      <div className="hero-foot">
        <p className="lede">Explore updates on open access, captive power, tariffs and storage. Understand what may affect your plant
          or project, then ask for an assessment of what it means commercially.{" "}
          {site.preview ? "This is a preview edition: the analysis is awaiting legal review." : "Every analysis is checked by our legal team before it is published."}</p>
        <p className="cta"><a href="#who" className="btn">See what affects my business</a><a href="#updates" className="btn ghost">Browse regulatory updates</a></p>
      </div>
      <nav className="chooser" id="who" aria-label="Choose your business">
        <h2 className="label">I am a</h2>
        <ul>{CHOICES.map(([g, label, hint, href]) => (
          <li key={label}><Link href={href}>{g ? <GroupIcon g={g} size={24} />
            : <svg className="gicon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M7 3h8l4 4v14H7zM15 3v4h4M10 12h6M10 16h6" /></svg>}<b>{label}</b><span>{hint}</span></Link></li>))}</ul>
      </nav>
    </section>
    <div className="cover">
      <Stage items={chapters.map((c) => ({ code: c.code, href: c.blocks.length ? `#c-${c.code}` : `/commissions/${c.code}`, idle: !c.blocks.length,
        note: c.blocks.length ? [c.drafts ? `${c.drafts} draft${c.drafts === 1 ? "" : "s"}` : "", c.orders ? `${c.orders} order${c.orders === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ") : "coming soon" }))} />

      <div className="flow">
        <section className="updates-box glass" id="updates">
          <h2 className="label">Key updates</h2>
          {updates.length ? (
            <ol className="updates">{updates.map((u) => (
              <li key={u.id}><a href={`#u-${u.id.slice(0, 10)}`}>
                <span className="u-code">{u.code.toUpperCase()}</span>
                <span className="u-title">{u.rating === "high" && <HighBadge />}{u.impact?.headline || u.title}</span>
                <span className="u-meta">{u.kind}{u.date ? ` · ${fmtDate(u.date)}` : ""}</span>
              </a></li>))}</ol>
          ) : <p className="muted">The first reviewed updates are being prepared. Coverage: {codes.map((k) => k.toUpperCase()).join(", ")}.</p>}
        </section>

        {live.map((c) => (
          <section key={c.code} className="chapter" id={`c-${c.code}`} data-chapter={c.code}>
            <header className="chapter-head rise">
              <p className="eyebrow">{GEO[c.code].place}</p>
              <h2><Link href={`/commissions/${c.code}`}>{commissionName(c.code)}</Link></h2>
            </header>
            {c.blocks.map((b) => <AnalysisBlock key={b.id} {...b} />)}
            {c.total > c.blocks.length && <p className="more rise"><Link href={`/commissions/${c.code}`}>All {c.total} items from {c.code.toUpperCase()} →</Link></p>}
          </section>))}

        <section className="glass rise tail">
          <h2 className="label">Get the weekly digest</h2>
          <Subscribe />
          <p className="muted small">{orders.length} {site.preview ? "draft" : "reviewed"} orders · {consultations.filter(isOpen).length} open drafts · {regulations.length} regulations in the registry ·{" "}
            <Link href="/consultations">all consultations</Link></p>
        </section>
      </div>
    </div>
  </>);
}
