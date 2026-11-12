import { KIND_LABEL, SITE_URL, consultations, digests, isOpen, orderLabel, orders, regulations, site } from "@/lib/data";

export const dynamic = "force-static";

export function GET() {
  const body = [
    "# Regulatory Studio",
    "",
    "> Legally reviewed summaries of Indian electricity regulatory orders (CERC, APTEL and state commissions), each traced to the regulation clauses, Electricity Act sections and earlier decisions it relies on. Incubated by jouleWise. Not legal advice.",
    "",
    "Every page has a Markdown version: add `.md` to its address. Every link between an order and a provision cites the paragraph of the order it rests on, and was approved by a named legal reviewer.",
    "",
    "## Data",
    `- [All orders as JSON](${SITE_URL}/api/v1/orders.json)`,
    `- [Regulation clauses as JSON](${SITE_URL}/api/v1/clauses.json)`,
    `- [Every order-to-provision link as JSON](${SITE_URL}/api/v1/links.json)`,
    `- [Draft regulations and consultations as JSON](${SITE_URL}/api/v1/consultations.json)`,
    `- [RSS feed, all orders](${SITE_URL}/feed.xml); per commission at /feeds/<commission>.xml, per topic at /feeds/topic-<topic>.xml`,
    "",
    "## Coverage",
    ...Object.entries(site.commissions).map(([k, v]) => `- [${v}](${SITE_URL}/commissions/${k})`),
    "",
    "## Latest digests",
    ...digests.slice(0, 8).map((d) => `- [${d.from} to ${d.to}](${SITE_URL}${d.path}.md)`),
    "",
    "## Open for comment",
    ...consultations.filter((c) => !c.sample && isOpen(c)).map((c) => `- [${c.title}](${SITE_URL}${c.path}.md): ${KIND_LABEL[c.kind]}, comments by ${c.comment_deadline ?? "see public notice"}`),
    "",
    "## Recent orders",
    ...orders.filter((o) => !o.sample).slice(0, 50).map((o) => `- [${o.title ?? orderLabel(o)}](${SITE_URL}${o.path}.md): ${o.issue}`),
    "",
    "## Regulations",
    ...regulations.filter((r) => !r.sample).map((r) => `- [${r.title}](${SITE_URL}${r.path}.md)`),
    "",
  ].join("\n");
  return new Response(body, { headers: { "content-type": "text/plain; charset=utf-8" } });
}
