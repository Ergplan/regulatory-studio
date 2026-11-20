import type { NextConfig } from "next";

const config: NextConfig = {
  serverExternalPackages: ["pg"],
  async rewrites() {
    return {
      // review.joulewise.tech is the review site: every path there is served by app/r (see that route).
      beforeFiles: [
        { source: "/", has: [{ type: "host", value: "review\\..*" }], destination: "/r" },
        { source: "/:path((?!r/|r$|review-api/|_next/).*)", has: [{ type: "host", value: "review\\..*" }], destination: "/r/:path" },
      ],
      afterFiles: [{ source: "/:path*.md", destination: "/md/:path*" }],
      fallback: [],
    };
  },
};

export default config;
