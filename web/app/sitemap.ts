import type { MetadataRoute } from "next";
import { SITE_URL, actSections, clauses, digests, orders, regulations, site } from "@/lib/data";

export default function sitemap(): MetadataRoute.Sitemap {
  const at = (p: string, lastModified?: string | null): MetadataRoute.Sitemap[number] =>
    ({ url: SITE_URL + p, lastModified: lastModified ? lastModified.replace(" ", "T") + (lastModified.length <= 19 ? "Z" : "") : undefined });
  return [
    at("/"), at("/orders"), at("/regulations"), at("/digest"), at("/search"), at("/about"),
    ...Object.keys(site.commissions).map((c) => at(`/commissions/${c}`)),
    ...Object.keys(site.topics).map((t) => at(`/topics/${t}`)),
    ...orders.filter((o) => !o.sample).map((o) => at(o.path, o.revised_at ?? o.approved_at)),
    ...regulations.filter((r) => !r.sample).map((r) => at(r.path)),
    ...clauses.filter((c) => !regulations.find((r) => r.id === c.regulation_id)?.sample).map((c) => at(c.path)),
    ...actSections.map((a) => at(`/act/${a.id}`)),
    ...digests.map((d) => at(d.path, d.approved_at)),
  ];
}
