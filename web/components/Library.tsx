import Link from "next/link";
import { HighBadge } from "@/components/AnalysisBlock";
import GroupIcon from "@/components/GroupIcon";
import { GEO } from "@/components/IndiaMap";
import {
  GROUPS, byDeadline, citingOrders, clausesOf, commentable, commissionName, consultationStatus, consultations, isOpen, orderLabel, orders, regulations, site,
  type Consultation, type Impact, type Order,
} from "@/lib/data";
import { fmtDate } from "@/lib/format";

export type LibraryKind = "drafts" | "regulations" | "orders";
interface Row { key: string; href: string; code: string; title: string; formal?: string; meta: string; live?: boolean; impact?: Impact | null; high: boolean; pending: boolean; cues?: string; note?: string }

const KINDS: Record<LibraryKind, { href: string; label: string; title: string; lede: string }> = {
  drafts: { href: "/consultations", label: "Drafts", title: "Draft regulations", lede: "Proposals the commissions have published for comment: what each would change and the last date for comments. These are proposals, not law." },
  regulations: { href: "/regulations", label: "Regulations", title: "Regulations in force", lede: "Notified regulations, split into clauses, with every order that applied, interpreted or relaxed each one." },
  orders: { href: "/orders", label: "Orders", title: "Orders", lede: "Decisions of the commissions, newest first, each traced to the provisions it rests on. An order binds the parties to the case." },
};

export const draftRow = (c: Consultation): Row => ({
  key: c.id, href: c.path, code: c.commission, title: c.impact?.headline || c.title, formal: c.impact?.headline ? c.title : undefined, meta: consultationStatus(c), live: isOpen(c),
  impact: c.impact, high: c.rating === "high", pending: !!c.draft, cues: commentable(c) ? `/studio?draft=${c.id.slice(0, 10)}` : undefined,
  note: c.impact?.headline ? undefined : c.summary });
export const orderRow = (o: Order): Row => ({ key: o.id, href: o.path, code: o.commission, title: o.impact?.headline || o.title || orderLabel(o),
  formal: o.impact?.headline ? (o.title ?? orderLabel(o)) : undefined, meta: [fmtDate(o.date), o.title ? o.case_number : ""].filter(Boolean).join(" · "),
  impact: o.impact, high: o.rating === "high", pending: !!o.draft, note: o.impact?.headline ? undefined : o.issue });

function rows(kind: LibraryKind): Row[] {
  if (kind === "drafts") return [...consultations].sort((a, b) => Number(isOpen(b)) - Number(isOpen(a)) || Number(b.rating === "high") - Number(a.rating === "high") || byDeadline(a, b)).map(draftRow);
  if (kind === "regulations") return regulations.map((r) => {
    const cl = clausesOf(r.id); const n = new Set(cl.flatMap((x) => citingOrders("clause", x.id).map((y) => y.order.id))).size;
    return { key: r.id, href: r.path, code: r.commission, title: r.impact?.headline || r.title, formal: r.impact?.headline ? r.title : undefined,
      meta: [r.notified_date ? `notified ${fmtDate(r.notified_date)}` : "", `${cl.length} clauses`, n ? `cited by ${n} order${n === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · "),
      impact: r.impact, high: r.rating === "high", pending: !!site.preview };
  });
  return orders.map(orderRow);
}

/** One row design for every list on the site. */
export function LibraryRow({ r, showCode = true, as: Tag = "li" }: { r: Row; showCode?: boolean; as?: "li" | "article" }) {
  const hit = r.impact ? GROUPS.filter(([g]) => r.impact!.stakeholders[g]) : [];
  return (
    <Tag className={`lib-row${r.high ? " is-high" : ""}`}>
      <div className="lib-main">
        <p className="lib-meta">{showCode && <span className="lib-code">{r.code.toUpperCase()}</span>}
          <span className={r.live === undefined ? "" : r.live ? "live" : "shut"}>{r.meta}</span>{r.pending && <span className="pend">analysis awaiting review</span>}</p>
        <h3>{r.high && <HighBadge />}<Link href={r.href}>{r.title}</Link></h3>
        {r.formal && <p className="formal">{r.formal}</p>}
        {r.note && <p className="lib-note">{r.note}</p>}
        {r.cues && <p className="lib-links"><Link href={r.cues}>Cues for your comments →</Link></p>}
      </div>
      {hit.length > 0 && (
        <ul className="lib-icons" aria-label="Who it affects">{hit.map(([g, short]) => (
          <li key={g} className={`ic e-${r.impact!.stakeholders[g]!.effect}`} title={`${short}: ${r.impact!.stakeholders[g]!.comment}`}><GroupIcon g={g} size={16} /><span>{short}</span></li>))}</ul>)}
    </Tag>
  );
}

/** Drafts, regulations and orders share one page design, with one switch between them. */
export default function Library({ kind }: { kind: LibraryKind }) {
  const all = rows(kind);
  const count: Record<LibraryKind, number> = { drafts: consultations.length, regulations: regulations.length, orders: orders.length };
  const codes = [...Object.keys(GEO), ...new Set(all.map((r) => r.code))].filter((c, i, a) => a.indexOf(c) === i && all.some((r) => r.code === c));
  const k = KINDS[kind];
  return (<>
    <p className="eyebrow">Updates{site.preview ? " · preview edition" : ""}</p>
    <h1 className="hero page-title">{k.title}</h1>
    <p className="lede">{k.lede}</p>
    <nav className="seg" aria-label="Type of update">{(Object.keys(KINDS) as LibraryKind[]).map((x) => (
      <Link key={x} href={KINDS[x].href} className={x === kind ? "on" : ""} aria-current={x === kind ? "page" : undefined}>{KINDS[x].label}<b>{count[x]}</b></Link>))}</nav>
    {codes.length > 1 && <nav className="jump" aria-label="Jump to a commission">{codes.map((c) => <a key={c} href={`#c-${c}`}>{c.toUpperCase()}<b>{all.filter((r) => r.code === c).length}</b></a>)}</nav>}
    {all.length === 0 && <div className="glass empty-state"><p>Nothing published here yet.</p></div>}
    {codes.map((c) => (
      <section key={c} id={`c-${c}`} className="lib-sec">
        <h2><span>{c.toUpperCase()}</span>{commissionName(c)}</h2>
        <ul className="lib">{all.filter((r) => r.code === c).map((r) => <LibraryRow key={r.key} r={r} showCode={false} />)}</ul>
      </section>))}
  </>);
}
