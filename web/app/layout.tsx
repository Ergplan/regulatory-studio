import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { LAUNCHED, SITE_URL, site } from "@/lib/data";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Regulatory Studio · Indian power sector regulatory updates", template: "%s · Regulatory Studio" },
  description: "Weekly, legally reviewed summaries of CERC, APTEL and state electricity commission orders, traced to the regulations they rest on.",
  alternates: { types: { "application/rss+xml": "/feed.xml" } },
  openGraph: { siteName: "Regulatory Studio", type: "website", locale: "en_IN" },
  robots: LAUNCHED ? undefined : { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN">
      <body>
        {site.preview && (
          <div className="banner"><div className="wrap"><b>Preview only.</b> These summaries are AI drafts that the legal team has not reviewed yet. They are shown to check the site, not to rely on.</div></div>
        )}
        {site.contains_sample_data && (
          <div className="banner"><div className="wrap">This build contains SAMPLE data for testing. Sample items are not real orders.</div></div>
        )}
        <header className="site-header"><div className="wrap">
          <Link href="/" className="brand">Regulatory Studio<small>incubated by jouleWise</small></Link>
          <nav className="nav" aria-label="Main">
            <Link href="/orders">Orders</Link><Link href="/regulations">Regulations</Link>
            <Link href="/digest">Weekly digest</Link><Link href="/search">Search</Link><Link href="/about">About</Link>
          </nav>
        </div></header>
        <main><div className="wrap">{children}</div></main>
        <footer className="site-footer"><div className="wrap">
          <span>Regulatory Studio, incubated by jouleWise. Summaries are for information and are not legal advice; read the original order.</span>
          <span><Link href="/feed.xml">RSS</Link> · <Link href="/llms.txt">llms.txt</Link> · <Link href="/api/v1/orders.json">API</Link></span>
        </div></footer>
      </body>
    </html>
  );
}
