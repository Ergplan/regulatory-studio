import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import ThemeToggle from "@/components/ThemeToggle";
import { LAUNCHED, SITE_URL, site } from "@/lib/data";

const THEME_SCRIPT = `try{if(localStorage.getItem("rs-theme")==="light")document.documentElement.dataset.theme="light"}catch(e){}`;

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
    <html lang="en-IN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter+Tight:wght@400;600;700;800&display=swap" />
      </head>
      <body>
        {site.preview && (
          <div className="banner"><div className="wrap"><b>Preview only.</b> These summaries are AI drafts that the legal team has not reviewed yet. They are shown to check the site, not to rely on.</div></div>
        )}
        {site.contains_sample_data && (
          <div className="banner"><div className="wrap">This build contains SAMPLE data for testing. Sample items are not real orders.</div></div>
        )}
        <header className="site-header"><div className="wrap">
          <Link href="/" className="brand">Regulatory Studio<small>incubated by <span className="j">joule</span><span className="w">Wise</span></small></Link>
          <nav className="nav" aria-label="Main">
            <Link href="/orders">Orders</Link><Link href="/regulations">Regulations</Link>
            <Link href="/consultations">Consultations</Link><Link href="/digest">Weekly digest</Link><Link href="/search">Search</Link><Link href="/about">About</Link>
            <ThemeToggle />
          </nav>
        </div></header>
        <main><div className="wrap">{children}</div></main>
        <footer className="site-footer"><div className="wrap">
          <span><b className="brand-foot">Regulatory Studio</b> · incubated by <a href="https://www.joulewise.tech" className="jw"><span className="j">joule</span><span className="w">Wise</span></a><br />
            Summaries are for information and are not legal advice; read the original order.</span>
          <span><Link href="/feed.xml">RSS</Link> · <Link href="/llms.txt">llms.txt</Link> · <Link href="/api/v1/orders.json">API</Link></span>
        </div></footer>
      </body>
    </html>
  );
}
