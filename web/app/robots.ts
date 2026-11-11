import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/data";

// Search engines and AI crawlers are welcome: the point is to be found and cited.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/api/subscribe"] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
