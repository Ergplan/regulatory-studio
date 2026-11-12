import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { LAUNCHED, SITE_URL, site } from "@/lib/data";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Regulatory Studio · Indian power sector regulatory updates", template: "%s · Regulatory Studio" },
  description: "A jouleWise and Urja Praxis joint venture. Weekly, legally reviewed summaries of CERC, APTEL and state electricity commission orders, traced to the regulations they rest on.",
  alternates: { types: { "application/rss+xml": "/feed.xml" } },
  openGraph: { siteName: "Regulatory Studio", type: "website", locale: "en_IN" },
  robots: LAUNCHED ? undefined : { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Urbanist:wght@300;400;500;600;700&display=swap" />
      </head>
      <body>
        {site.preview && (
          <div className="banner"><div className="wrap"><b>Preview edition.</b> The analysis on this site was prepared with AI and is awaiting legal review. It is shown to check the site, not to rely on.</div></div>
        )}
        {site.contains_sample_data && (
          <div className="banner"><div className="wrap">This build contains SAMPLE data for testing. Sample items are not real orders.</div></div>
        )}
        <header className="site-header"><div className="wrap">
          <Link href="/" className="brand">Regulatory Studio<small><span className="j">joule</span><span className="w">Wise</span> × <span className="w">Urja Praxis</span></small></Link>
          <nav className="nav" aria-label="Main">
            <Link href="/orders">Orders</Link><Link href="/regulations">Regulations</Link>
            <Link href="/consultations">Consultations</Link><Link href="/impact">Impact</Link><Link href="/studio">Consultation support</Link><Link href="/digest">Digest</Link><Link href="/search">Search</Link><Link href="/about">About</Link>
            <Link href="/discuss" className="nav-cta">Discuss my project</Link>
          </nav>
        </div></header>
        <main><div className="wrap">{children}</div></main>
        <footer className="site-footer"><div className="wrap">
          <span><b className="brand-foot">Regulatory Studio</b> · a joint venture of <a href="https://www.joulewise.tech" className="jw"><span className="j">joule</span><span className="w">Wise</span></a> and <span className="jw"><span className="w">Urja Praxis</span></span><br />
            Summaries are for information and are not legal advice; read the original order.</span>
          <span className="small">Map: state outlines from @svg-maps/india, CC BY 4.0.</span>
          <span><Link href="/feed.xml">RSS</Link> · <Link href="/llms.txt">llms.txt</Link> · <Link href="/api/v1/orders.json">API</Link></span>
        </div></footer>
      </body>
    </html>
  );
}
