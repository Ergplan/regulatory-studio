import type { NextConfig } from "next";

// The legal team's review screen runs on the Mac mini behind Cloudflare Access. Set REVIEW_URL to that address
// (for example https://review.example.com) and the site forwards /review, and the whole review.* host, to it.
const review = (process.env.REVIEW_URL || "").replace(/\/+$/, "");

const config: NextConfig = {
  async redirects() {
    if (!/^https:\/\/[a-z0-9.-]+$/i.test(review)) return [];
    return [
      { source: "/:path*", has: [{ type: "host", value: "review(?:er)?\\.joulewise\\.tech" }], destination: `${review}/:path*`, permanent: false },
      { source: "/review", destination: `${review}/`, permanent: false },
    ];
  },
  // Markdown twin of every page: /orders/x.md is served by /md/orders/x
  async rewrites() {
    return [{ source: "/:path*.md", destination: "/md/:path*" }];
  },
};

export default config;
