import { GROUPS, consultationStatus, consultations, orders, orderLabel, regulations, site, type GroupKey, type Impact } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export interface ImpactRow { key: string; href: string; title: string; kind: string; sub: string; impact: Impact; pdf: string | null; draft: boolean; high: boolean; commission: string }
export interface ImpactSection { id: string; label: string; note: string; rows: ImpactRow[] }

/** Documents with a published impact assessment, grouped as draft regulations, notified regulations, orders. */
export function impactSections(): ImpactSection[] {
  const drafts = consultations.filter((c) => c.impact).map((c) => ({
    key: c.id, href: c.path, title: c.title, kind: "Draft regulation", impact: c.impact!, pdf: c.source_url, draft: !!c.draft, high: c.rating === "high", commission: c.commission,
    sub: consultationStatus(c) }));
  const regs = regulations.filter((r) => r.impact).map((r) => ({
    key: r.id, href: r.path, title: r.title, kind: "Notified regulation", impact: r.impact!, pdf: r.pdf ?? null, draft: !!site.preview, high: r.rating === "high", commission: r.commission,
    sub: r.notified_date ? `notified ${fmtDate(r.notified_date)}` : "" }));
  const ords = orders.filter((o) => o.impact).map((o) => ({
    key: o.id, href: o.path, title: o.impact?.headline || o.headline || o.title || orderLabel(o), kind: "Order", impact: o.impact!, pdf: o.pdf, draft: !!o.draft, high: o.rating === "high", commission: o.commission,
    sub: [o.case_number, o.date ? fmtDate(o.date) : ""].filter(Boolean).join(" · ") }));
  return [
    { id: "drafts", label: "Drafts", note: "Proposals: effects apply only if adopted", rows: drafts },
    { id: "regulations", label: "Regulations", note: "Notified and in force", rows: regs },
    { id: "orders", label: "Orders", note: "Bind the parties; the reasoning guides similar cases", rows: ords },
  ].filter((s) => s.rows.length);
}

export interface GroupTally { g: GroupKey; short: string; long: string; gains: number; costs: number; mixed: number; n: number }
export interface StateImpact { code: string; sections: ImpactSection[]; n: number; tally: GroupTally[]; lead: string }

/** Who the assessed documents affect, counted by direction. Only groups that are affected appear. */
export function tally(rows: ImpactRow[]): GroupTally[] {
  return GROUPS.map(([g, short, long]) => {
    const cells = rows.map((r) => r.impact.stakeholders[g]).filter(Boolean);
    return { g, short, long, n: cells.length, gains: cells.filter((c) => c!.effect === "opportunity").length,
      costs: cells.filter((c) => c!.effect === "cost").length, mixed: cells.filter((c) => c!.effect === "mixed").length };
  }).filter((t) => t.n).sort((a, b) => b.n - a.n);
}

/** The same documents, one block per commission, each split into drafts, regulations and orders. */
export function impactByState(order: string[]): StateImpact[] {
  const all = impactSections();
  return order.map((code) => {
    const sections = all.map((s) => ({ ...s, rows: s.rows.filter((r) => r.commission === code) })).filter((s) => s.rows.length);
    const rows = sections.flatMap((s) => s.rows);
    const t = tally(rows);
    const bearers = t.filter((x) => x.costs > x.gains).map((x) => x.long);
    const gainers = t.filter((x) => x.gains > x.costs).map((x) => x.long);
    const list = (a: string[]) => a.length > 1 ? `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}` : a[0];
    const lead = [gainers.length ? `Mostly gain: ${list(gainers)}.` : "", bearers.length ? `Mostly bear cost: ${list(bearers)}.` : ""].filter(Boolean).join(" ");
    return { code, sections, n: rows.length, tally: t, lead };
  }).filter((s) => s.n);
}
