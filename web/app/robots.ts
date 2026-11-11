import type { MetadataRoute } from "next";
import { LAUNCHED, SITE_URL } from "@/lib/data";

// Search engines and AI crawlers are welcome: the point is to be found and cited.
export default function robots(): MetadataRoute.Robots {
  if (!LAUNCHED) return { rules: [{ userAgent: "*", disallow: "/" }] };
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/api/subscribe"] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
