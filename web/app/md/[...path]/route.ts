import { allMdPaths, pageMd } from "@/lib/markdown";

export const dynamic = "force-static";
export const dynamicParams = false;
export function generateStaticParams() { return allMdPaths().map((p) => ({ path: p.slice(1).split("/") })); }

export async function GET(_req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const md = pageMd("/" + path.map(decodeURIComponent).join("/"));
  if (!md) return new Response("Not found\n", { status: 404 });
  return new Response(md, { headers: { "content-type": "text/markdown; charset=utf-8" } });
}
