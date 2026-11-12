import { SITE_URL, commissionName, orderLabel, orders } from "@/lib/data";
import { escapeXml } from "@/lib/format";

export const dynamic = "force-static";

export function GET() {
  const items = orders.filter((o) => !o.sample).slice(0, 100).map((o) => `
    <item>
      <title>${escapeXml(`${o.commission.toUpperCase()}: ${o.title ?? orderLabel(o)}`)}</title>
      <link>${SITE_URL}${o.path}</link>
      <guid isPermaLink="true">${SITE_URL}${o.path}</guid>
      <pubDate>${new Date((o.approved_at ?? `${o.date} 00:00:00`).replace(" ", "T") + "Z").toUTCString()}</pubDate>
      <category>${escapeXml(commissionName(o.commission))}</category>
      ${o.topics.map((t) => `<category>${escapeXml(t)}</category>`).join("")}
      <description>${escapeXml(o.summary)}</description>
    </item>`).join("");
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
  <title>Regulatory Studio</title><link>${SITE_URL}</link>
  <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>Legally reviewed summaries of Indian electricity regulatory orders</description><language>en-in</language>${items}
</channel></rss>`;
  return new Response(xml, { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
}
