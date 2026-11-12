import type { Metadata } from "next";
import Link from "next/link";
import { HeatCell, HeatLegend } from "@/components/Impact";
import { GROUPS, consultations, isOpen, orderLabel, orders } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Market impact heat map",
  description: "Who each recent electricity regulatory order and draft regulation affects: discoms, C&I and open access consumers, captive users, RE developers, storage, generators, the grid and traders.",
  alternates: { canonical: "/impact" },
};

type Row = { key: string; href: string; label: string; sub: string; kind: string; stakeholders: Record<string, never> | Record<string, import("@/lib/data").ImpactCell>; note: string; draft?: boolean };

export default function ImpactMap() {
  const rows: Row[] = [
    ...consultations.filter((c) => c.impact && isOpen(c)).map((c) => ({ key: c.id, href: c.path, label: c.title, kind: "Open draft",
      sub: `${c.commission.toUpperCase()} · comments by ${c.comment_deadline ? fmtDate(c.comment_deadline) : "see notice"}`,
      stakeholders: c.impact!.stakeholders, note: c.impact!.market_note, draft: c.draft })),
    ...orders.filter((o) => o.impact).map((o) => ({ key: o.id, href: o.path, label: o.title ?? orderLabel(o), kind: "Order",
      sub: `${o.commission.toUpperCase()} · ${o.date ? fmtDate(o.date) : ""}`, stakeholders: o.impact!.stakeholders, note: o.impact!.market_note, draft: o.draft })),
    ...consultations.filter((c) => c.impact && !isOpen(c)).map((c) => ({ key: c.id, href: c.path, label: c.title, kind: "Closed draft",
      sub: `${c.commission.toUpperCase()}`, stakeholders: c.impact!.stakeholders, note: c.impact!.market_note, draft: c.draft })),
  ];
  const totals = GROUPS.map(([g]) => rows.reduce((n, r) => n + ((r.stakeholders[g]?.level ?? 0) > 0 ? 1 : 0), 0));
  return (<>
    <p className="eyebrow">Market impact</p>
    <h1 className="hero">Who is affected, and how much</h1>
    <p className="lede">Each row is an order or a draft regulation; each column a group in the power market. Green is an
      opportunity, orange a cost or new obligation, blue mixed. Hover or tap a cell for the reason; open a row for key points
      and procurement requirements.</p>
    <HeatLegend />
    {rows.length === 0 ? <div className="card empty">No impact assessments published yet.</div> : (
      <div className="heat-scroll"><table className="heatmap">
        <thead><tr><th className="row-h">Order or draft</th>{GROUPS.map(([g, short, long]) => <th key={g} title={long}>{short}</th>)}</tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.key}><th className="row-h" scope="row"><span className="meta">{r.kind} · {r.sub}{r.draft ? " · draft" : ""}</span>
            <Link href={r.href}>{r.label}</Link>{r.note && <span className="row-note">{r.note}</span>}</th>
            {GROUPS.map(([g, short]) => <HeatCell key={g} cell={r.stakeholders[g]} label={short} />)}</tr>))}
        </tbody>
        <tfoot><tr><th className="row-h">Items affecting each group</th>{totals.map((n, i) => <td key={i} className="total">{n}</td>)}</tr></tfoot>
      </table></div>)}
  </>);
}
