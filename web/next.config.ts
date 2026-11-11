import type { NextConfig } from "next";

const config: NextConfig = {
  // Markdown twin of every page: /orders/x.md is served by /md/orders/x
  async rewrites() {
    return [{ source: "/:path*.md", destination: "/md/:path*" }];
  },
};

export default config;
