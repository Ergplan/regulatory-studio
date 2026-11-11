// RSS per commission and per topic: /feeds/cerc.xml, /feeds/topic-banking.xml
import { SITE_URL, commissionName, orderLabel, orders, site, topicName, type Order } from "@/lib/data";
import { escapeXml } from "@/lib/format";

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return [...Object.keys(site.commissions).map((c) => ({ file: `${c}.xml` })),
          ...Object.keys(site.topics).map((t) => ({ file: `topic-${t}.xml` }))];
}

function rss(title: string, self: string, list: Order[]): string {
  const items = list.filter((o) => !o.sample).slice(0, 100).map((o) => `
    <item>
      <title>${escapeXml(`${o.commission.toUpperCase()}: ${o.title ?? orderLabel(o)}`)}</title>
      <link>${SITE_URL}${o.path}</link>
      <guid isPermaLink="true">${SITE_URL}${o.path}</guid>
      <pubDate>${new Date(o.approved_at.replace(" ", "T") + "Z").toUTCString()}</pubDate>
      <description>${escapeXml(o.summary)}</description>
    </item>`).join("");
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
  <title>${escapeXml(title)}</title><link>${SITE_URL}</link>
  <atom:link href="${SITE_URL}${self}" rel="self" type="application/rss+xml"/>
  <description>${escapeXml(title)}</description><language>en-in</language>${items}
</channel></rss>`;
}

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  const key = file.replace(/\.xml$/, "");
  const xml = key.startsWith("topic-")
    ? rss(`Regulatory Studio: ${topicName(key.slice(6))}`, `/feeds/${file}`, orders.filter((o) => o.topics.includes(key.slice(6))))
    : rss(`Regulatory Studio: ${commissionName(key)}`, `/feeds/${file}`, orders.filter((o) => o.commission === key));
  return new Response(xml, { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
}
