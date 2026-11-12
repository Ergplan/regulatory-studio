import Link from "next/link";
import CoverScroll from "@/components/CoverScroll";
import GroupIcon from "@/components/GroupIcon";
import IndiaMap, { GEO, LeaderLines, VB, geoCss } from "@/components/IndiaMap";
import { Direction } from "@/components/Impact";
import Subscribe from "@/components/Subscribe";
import { GROUPS, byDeadline, commentable, commissionName, consultations, isOpen, orderLabel, orders, regulations, site, type Impact } from "@/lib/data";
import { fmtDate } from "@/lib/format";

interface Block { id: string; href: string; kind: "Draft" | "Order"; tab: string; title: string; summary: string; date: string; impact?: Impact | null; draftable: boolean; unreviewed: boolean }
const PER_CHAPTER = 4;

function blocksFor(code: string): { blocks: Block[]; total: number; drafts: number; orders: number } {
  const drafts = consultations.filter((c) => c.commission === code);
  const open = drafts.filter(isOpen).sort(byDeadline);
  const ords = orders.filter((o) => o.commission === code);
  const closed = drafts.filter((c) => !isOpen(c)).sort((a, b) => (b.issued ?? "").localeCompare(a.issued ?? ""));
  const all: Block[] = [
    ...[...open, ...closed].map((c) => ({ id: c.id, href: c.path, kind: "Draft" as const, title: c.title, summary: c.summary, date: c.issued ?? "",
      tab: !isOpen(c) ? `Draft · listed deadline ${fmtDate(c.comment_deadline ?? c.hearing_date)} passed` : c.comment_deadline ? `Draft · comments by ${fmtDate(c.comment_deadline)}` : "Draft · open for comment",
      impact: c.impact, draftable: commentable(c), unreviewed: !!c.draft })),
    ...ords.map((o) => ({ id: o.id, href: o.path, kind: "Order" as const, title: o.title ?? orderLabel(o), summary: o.summary, date: o.date ?? "",
      tab: `Order · ${fmtDate(o.date)}`, impact: o.impact, draftable: false, unreviewed: !!o.draft })),
  ];
  // items with an impact assessment lead; then drafts by deadline and orders by date, as built above
  all.sort((a, b) => Number(!!b.impact) - Number(!!a.impact));
  return { blocks: all.slice(0, PER_CHAPTER), total: all.length, drafts: drafts.length, orders: ords.length };
}

export default function Home() {
  const codes = Object.keys(GEO).filter((k) => site.commissions[k]);
  const chapters = codes.map((code) => ({ code, ...blocksFor(code) }));
  const live = chapters.filter((c) => c.blocks.length);
  const updates = live.flatMap((c) => c.blocks.map((b) => ({ ...b, code: c.code }))).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);
  const pct = (x: number, y: number) => ({ left: `${((x - VB.x) / VB.w) * 100}%`, top: `${((y - VB.y) / VB.h) * 100}%` });

  return (
    <div className="cover">
      <style dangerouslySetInnerHTML={{ __html: geoCss() }} />
      <CoverScroll />
      <div className="stage" aria-label="Commissions covered">
        <div className="orbit">
          <LeaderLines />
          <div className="india-box"><IndiaMap /></div>
          <div className="ccards">
            {chapters.map((c) => (
              <a key={c.code} href={c.blocks.length ? `#c-${c.code}` : `/commissions/${c.code}`} className={`ccard cc-${c.code}${c.blocks.length ? "" : " idle"}`} style={pct(...GEO[c.code].card)}>
                <b>{c.code.toUpperCase()}</b>
                <span>{GEO[c.code].place}</span>
                <em>{c.blocks.length ? [c.drafts ? `${c.drafts} draft${c.drafts === 1 ? "" : "s"}` : "", c.orders ? `${c.orders} order${c.orders === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ") : "coming soon"}</em>
              </a>))}
          </div>
        </div>
        <p className="now" aria-hidden="true">{codes.map((k) => <span key={k} className={`now-${k}`}><i />{commissionName(k)}</span>)}</p>
      </div>

      <div className="flow">
        <section className="cover-hero">
          <p className="eyebrow">Regulatory Studio · a <span className="j">joule</span>Wise × Urja Praxis joint venture</p>
          <h1 className="hero">India&apos;s power regulation, read and mapped.</h1>
          <p className="lede">Orders and draft regulations from CERC, APTEL and six state commissions: what each one changes, who it
            affects, and the paragraph it rests on. Then draft your comments in the Studio.{" "}
            {site.preview ? "This preview shows AI drafts awaiting legal review." : "Every summary is checked by our legal team before it is published."}</p>
          <p className="cta"><Link href="/studio" className="btn">Open the Studio</Link><Link href="/impact" className="btn ghost">Impact map</Link><Link href="/digest" className="btn ghost">Weekly digest</Link></p>
        </section>

        <section className="updates-box glass">
          <h2 className="label">Key updates</h2>
          {updates.length ? (
            <ol className="updates">{updates.map((u) => (
              <li key={u.id}><a href={`#u-${u.id.slice(0, 10)}`}>
                <span className="u-code">{u.code.toUpperCase()}</span>
                <span className="u-title">{u.title}</span>
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
            {c.blocks.map((b) => {
              const hit = b.impact ? GROUPS.filter(([g]) => b.impact!.stakeholders[g]) : [];
              return (
                <article key={b.id} className={`folder rise${b.kind === "Draft" ? " is-draft" : ""}`} id={`u-${b.id.slice(0, 10)}`}>
                  <span className="tab">{b.tab}{b.unreviewed ? " · AI draft" : ""}</span>
                  <h3><Link href={b.href}>{b.title}</Link></h3>
                  <p className="folder-sum">{b.impact?.market_note || b.summary}</p>
                  {hit.length > 0 && (
                    <ul className="who-chips" aria-label="Who is affected">{hit.map(([g, short]) => (
                      <li key={g} className={`e-${b.impact!.stakeholders[g]!.effect}`} title={b.impact!.stakeholders[g]!.comment}>
                        <GroupIcon g={g} size={16} /> {short} <Direction effect={b.impact!.stakeholders[g]!.effect} /></li>))}</ul>)}
                  <p className="folder-links"><Link href={b.impact ? `${b.href}#impact` : b.href}>{b.impact ? "Read the analysis" : "Read the summary"} →</Link>
                    {b.draftable && <Link href={`/studio?draft=${b.id.slice(0, 10)}`}>Draft your comments →</Link>}</p>
                </article>);
            })}
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
  );
}
