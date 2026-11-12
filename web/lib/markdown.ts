// Markdown twins of site pages, for language models and other readers that prefer plain text.
import {
  SITE_URL, actById, citingOrders, clauses, clausesOf, commissionName, digests, linkTypeLabel, orderById, orderLabel,
  orders, regulations, regulationById, targetInfo, topicName, type Order,
} from "./data";

const abs = (p: string) => (/^https?:\/\//.test(p) ? p : SITE_URL + p);

export function orderMd(o: Order): string {
  const lines = [
    `# ${o.title ?? orderLabel(o)}`, "",
    `- Commission: ${commissionName(o.commission)}`,
    o.case_number ? `- Case: ${o.case_number}` : "", o.date ? `- Order date: ${o.date}` : "",
    `- Topics: ${o.topics.map(topicName).join(", ")}`,
    `- Original order: ${abs(o.pdf)} (commission page: ${o.source_url})`,
    o.draft ? "- Status: DRAFT drafted by AI, not yet reviewed by the legal team"
      : `- Reviewed by the Regulatory Studio legal team: ${o.approved_at}${o.revised_at ? `, revised ${o.revised_at}` : ""}`,
    o.sample ? "- NOTE: SAMPLE DATA, NOT A REAL ORDER" : "", "",
    "## Summary", "", o.summary, "", "## Issue", "", o.issue, "", "## Outcome", "", o.outcome, "",
    "## Provisions and decisions linked", "",
    ...o.links.map((l) => {
      const t = targetInfo(l.kind, l.target);
      return `- ${linkTypeLabel(l.type)}: [${t?.label ?? l.target}](${abs((t?.href ?? "") + ".md")}) (cited as "${l.cited_as}", paragraph ${l.pid})\n  > ${l.excerpt}`;
    }),
    "", "Summaries are for information and are not legal advice. Canonical page: " + abs(o.path),
  ];
  return lines.filter((l, i, a) => l !== "" || a[i - 1] !== "").join("\n") + "\n";
}

export function pageMd(path: string): string | null {
  const o = orders.find((x) => x.path === path);
  if (o) return orderMd(o);
  const reg = regulations.find((r) => r.path === path);
  if (reg) return [`# ${reg.title}`, "", `Commission: ${commissionName(reg.commission)}`, "", "## Clauses", "",
    ...clausesOf(reg.id).map((c) => `- [Regulation ${c.number}${c.heading ? ": " + c.heading : ""}](${abs(c.path + ".md")}) — cited by ${citingOrders("clause", c.id).length} reviewed orders`)].join("\n") + "\n";
  const c = clauses.find((x) => x.path === path);
  if (c) {
    const r = regulationById.get(c.regulation_id)!;
    return [`# Regulation ${c.number}${c.heading ? ": " + c.heading : ""}`, "", `Part of: [${r.title}](${abs(r.path + ".md")})`, "",
      "## Text", "", c.text, "", c.in_force_to ? `Omitted: in force until ${c.in_force_to}.` : `In force${c.in_force_from ? " from " + c.in_force_from : ""}.`, "",
      ...(c.versions?.length ? ["## Earlier wording", "", ...c.versions.map((v) => `- In force ${v.in_force_from ? "from " + v.in_force_from + " " : ""}to ${v.in_force_to}: ${v.text}`), ""] : []),
      "## Reviewed orders citing this clause", "",
      ...citingOrders("clause", c.id).map(({ order, links }) => `- [${order.title ?? orderLabel(order)}](${abs(order.path + ".md")}) (${order.commission.toUpperCase()}, ${order.date ?? ""}): ${[...new Set(links.map((l) => linkTypeLabel(l.type)))].join(", ")}`)].join("\n") + "\n";
  }
  if (path.startsWith("/act/")) {
    const a = actById.get(path.slice(5));
    if (a) return [`# Section ${a.number}, ${a.act}: ${a.title}`, "", "## Reviewed orders relying on this section", "",
      ...citingOrders("act_section", a.id).map(({ order }) => `- [${order.title ?? orderLabel(order)}](${abs(order.path + ".md")})`)].join("\n") + "\n";
  }
  const d = digests.find((x) => x.path === path);
  if (d) return [`# Weekly digest ${d.from} to ${d.to}`, "", d.intro, "",
    ...d.items.map((id) => orderById.get(id)).filter(Boolean).map((x) => `- [${x!.title ?? orderLabel(x!)}](${abs(x!.path + ".md")}): ${x!.issue}`)].join("\n") + "\n";
  return null;
}

export function allMdPaths(): string[] {
  return [...orders.map((o) => o.path), ...regulations.map((r) => r.path), ...clauses.map((c) => c.path),
    ...[...actById.keys()].map((id) => `/act/${id}`), ...digests.map((d) => d.path)];
}
