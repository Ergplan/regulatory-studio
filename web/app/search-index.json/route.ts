// Small static index for the search page: orders, regulations and clauses.
import { clauses, orderLabel, orders, regName, regulationById, regulations } from "@/lib/data";

export const dynamic = "force-static";

export function GET() {
  const docs = [
    ...orders.map((o) => ({ t: "Order", title: o.title ?? orderLabel(o), sub: [o.commission.toUpperCase(), o.title ? o.case_number : null, o.date].filter(Boolean).join(" · "),
      href: o.path, text: [o.title, o.case_number, o.issue, o.outcome, o.summary, ...o.parties.map((p) => p.name), ...o.topics].join(" ") })),
    ...regulations.map((r) => ({ t: "Regulation", title: regName(r), sub: r.commission.toUpperCase(), href: r.path, text: r.title })),
    ...clauses.map((c) => {
      const r = regulationById.get(c.regulation_id);
      return { t: "Clause", title: `Regulation ${c.number}${c.heading ? ": " + c.heading : ""}`, sub: r ? regName(r) : "", href: c.path,
        text: `${c.number} ${c.heading ?? ""} ${c.text}` };
    }),
  ];
  return Response.json(docs);
}
