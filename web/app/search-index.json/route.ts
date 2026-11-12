// Small static index for the search page: orders, draft regulations, regulations and clauses.
import { clauses, consultationStatus, consultations, orderLabel, orders, regName, regulationById, regulations } from "@/lib/data";

export const dynamic = "force-static";

// Readers use several names for the same thing; add the others so any of them finds the item.
const ALIASES: [RegExp, string][] = [
  [/\bbess\b|batter|energy storage|storage system|pumped/i, "BESS battery energy storage ESS pumped hydro storage"],
  [/open access|\bgeoa\b|wheeling|banking/i, "open access OA GEOA wheeling banking"],
  [/captive/i, "captive CPP contract demand"],
  [/deviation|\bdsm\b|scheduling|forecast/i, "DSM deviation settlement scheduling forecasting"],
  [/renewable purchase|\brpo\b|\brco\b/i, "RPO RCO renewable purchase obligation"],
  [/transmission charge|\bists\b|\bgna\b/i, "ISTS GNA transmission charges waiver"],
];
const widen = (t: string) => t + " " + ALIASES.filter(([re]) => re.test(t)).map(([, add]) => add).join(" ");
const brief = (t: string | undefined | null) => (t ?? "").replace(/\s+/g, " ").trim().slice(0, 170);

export function GET() {
  const docs = [
    ...consultations.map((c) => ({ t: "Draft", title: c.impact?.headline || c.title, sub: [c.commission.toUpperCase(), consultationStatus(c), c.impact?.headline ? c.title : null].filter(Boolean).join(" · "),
      why: brief(c.impact?.market_note || c.summary), href: c.path, text: widen([c.title, c.summary, ...c.proposes, c.amends, c.impact?.headline, c.impact?.market_note].join(" ")) })),
    ...orders.map((o) => ({ t: "Order", title: o.impact?.headline || o.title || orderLabel(o), sub: [o.commission.toUpperCase(), o.impact?.headline ? o.title : null, o.case_number, o.date].filter(Boolean).join(" · "),
      why: brief(o.impact?.market_note || o.issue), href: o.path,
      text: widen([o.title, o.case_number, o.issue, o.outcome, o.summary, o.impact?.headline, ...o.parties.map((p) => p.name), ...o.topics].join(" ")) })),
    ...regulations.map((r) => ({ t: "Regulation", title: r.impact?.headline || regName(r), sub: [r.commission.toUpperCase(), r.impact?.headline ? r.title : null].filter(Boolean).join(" · "),
      why: brief(r.impact?.market_note), href: r.path, text: widen([r.title, r.impact?.headline, r.impact?.market_note].join(" ")) })),
    ...clauses.map((c) => {
      const r = regulationById.get(c.regulation_id);
      return { t: "Clause", title: `Regulation ${c.number}${c.heading ? ": " + c.heading : ""}`, sub: r ? regName(r) : "", why: brief(c.text), href: c.path,
        text: `${c.number} ${c.heading ?? ""} ${c.text}` };
    }),
  ];
  return Response.json(docs);
}
