import { consultations, orders, orderLabel, regulations, site, type Impact } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export interface ImpactRow { key: string; href: string; title: string; kind: string; sub: string; impact: Impact; pdf: string | null; draft: boolean; high: boolean }
export interface ImpactSection { id: string; label: string; note: string; rows: ImpactRow[] }

/** Documents with a published impact assessment, grouped as draft regulations, notified regulations, orders. */
export function impactSections(): ImpactSection[] {
  const drafts = consultations.filter((c) => c.impact).map((c) => ({
    key: c.id, href: c.path, title: c.title, kind: "Draft regulation", impact: c.impact!, pdf: c.source_url, draft: !!c.draft, high: c.rating === "high",
    sub: `${c.commission.toUpperCase()}${c.comment_deadline ? ` · comments by ${fmtDate(c.comment_deadline)}` : c.issued ? ` · issued ${fmtDate(c.issued)}` : ""}` }));
  const regs = regulations.filter((r) => r.impact).map((r) => ({
    key: r.id, href: r.path, title: r.title, kind: "Notified regulation", impact: r.impact!, pdf: r.source_url, draft: !!site.preview, high: r.rating === "high",
    sub: `${r.commission.toUpperCase()}${r.notified_date ? ` · notified ${fmtDate(r.notified_date)}` : ""}` }));
  const ords = orders.filter((o) => o.impact).map((o) => ({
    key: o.id, href: o.path, title: o.title ?? orderLabel(o), kind: "Order", impact: o.impact!, pdf: o.pdf, draft: !!o.draft, high: o.rating === "high",
    sub: `${o.commission.toUpperCase()}${o.case_number ? ` · ${o.case_number}` : ""}${o.date ? ` · ${fmtDate(o.date)}` : ""}` }));
  return [
    { id: "drafts", label: "Draft regulations", note: "Effects apply only if adopted", rows: drafts },
    { id: "regulations", label: "Notified regulations", note: "In force", rows: regs },
    { id: "orders", label: "Orders", note: "Bind the parties; the reasoning guides similar cases", rows: ords },
  ].filter((s) => s.rows.length);
}
