import type { Metadata } from "next";
import Link from "next/link";
import { site } from "@/lib/data";

export const metadata: Metadata = { title: "About", alternates: { canonical: "/about" } };
export default function About() {
  return (<article style={{ maxWidth: 760 }}>
    <h1>About Regulatory Studio</h1>
    <p>Regulatory Studio tracks orders of the Central Electricity Regulatory Commission, the Appellate Tribunal for Electricity
      and state electricity regulatory commissions, starting with open access and tariff matters. It is incubated by jouleWise.</p>
    <h2>How a summary is made</h2>
    <ol><li>New orders are collected from commission websites every week.</li>
      <li>Software reads each order, drafts a summary and proposes links to the regulations, Act sections and earlier decisions it relies on, each tied to the paragraph that supports it.</li>
      <li>Our legal team checks every summary and every link against the order. Nothing is published until they approve it, and the approval date is shown on each page.</li></ol>
    <h2>Coverage</h2><ul>{Object.entries(site.commissions).map(([k, v]) => <li key={k}><Link href={`/commissions/${k}`}>{v}</Link></li>)}</ul>
    <h2>For software and AI assistants</h2>
    <p>Every page has a Markdown version at the same address with <code>.md</code> added. See <Link href="/llms.txt">llms.txt</Link>,
      the <Link href="/api/v1/orders.json">JSON API</Link> and the <Link href="/feed.xml">RSS feed</Link>.</p>
    <h2>Not legal advice</h2><p>Summaries are for information. Always read the original order, linked from every page.</p>
  </article>);
}
