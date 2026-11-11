import { SITE_URL, clauses, digests, orders, regulations } from "@/lib/data";

export const dynamic = "force-static";
export const dynamicParams = false;
const NAMES = ["orders.json", "clauses.json", "regulations.json", "links.json", "digests.json"];
export function generateStaticParams() { return NAMES.map((name) => ({ name })); }

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const real = orders.filter((o) => !o.sample);
  const data: Record<string, unknown> = {
    "orders.json": real.map(({ links, ...o }) => ({ ...o, url: SITE_URL + o.path, link_count: links.length })),
    "clauses.json": clauses.map((c) => ({ ...c, url: SITE_URL + c.path })),
    "regulations.json": regulations.filter((r) => !r.sample).map((r) => ({ ...r, url: SITE_URL + r.path })),
    "links.json": real.flatMap((o) => o.links.map((l) => ({ from: o.id, from_url: SITE_URL + o.path, ...l }))),
    "digests.json": digests.map((d) => ({ ...d, url: SITE_URL + d.path })),
  };
  if (!(name in data)) return Response.json({ error: "not found" }, { status: 404 });
  return Response.json({ generated_by: "Regulatory Studio", license_note: "Summaries are for information, not legal advice.", data: data[name] },
    { headers: { "access-control-allow-origin": "*" } });
}
