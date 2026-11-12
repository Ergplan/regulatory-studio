import type { Metadata } from "next";
import Link from "next/link";
import { Pipeline } from "@/components/Trail";
import { site } from "@/lib/data";

export const metadata: Metadata = { title: "About", alternates: { canonical: "/about" } };
export default function About() {
  return (<article style={{ maxWidth: 900 }}>
    <h1>About Regulatory Studio</h1>
    <p>Regulatory Studio tracks orders of the Central Electricity Regulatory Commission, the Appellate Tribunal for Electricity
      and state electricity regulatory commissions, starting with open access and tariff matters. It is a joint venture of jouleWise and Urja Praxis.</p>
    <h2>How a summary is made</h2>
    <Pipeline />
    <p>The AI reviewers cannot change or approve anything. What they find is shown to the legal reviewer beside the summary and is not published.
      Nothing is published as reviewed until a named reviewer approves it, and the approval date is shown on each page.</p>
    <h2>Two kinds of status</h2>
    <p>Every page shows two things separately. <b>Document status</b> says what the underlying text is: a proposal open for comment, a
      proposal whose comment period has closed, a notified regulation in force, or an order that binds the parties to a case.{" "}
      <b>Analysis status</b> says where our own work stands: prepared with AI and awaiting legal review, or reviewed, with the date.</p>
    <h2>Preview edition and reviewed edition</h2>
    <p>{site.preview ? "You are reading the preview edition. " : ""}The reviewed edition publishes only what the legal team has approved. A preview edition, used to check the
      site before launch, also shows analysis that is still awaiting review; it carries a banner on every page and each item is marked.
      Do not rely on analysis marked as awaiting review.</p>
    <h2>Evidence</h2>
    <p>Statements in an analysis cite the page and paragraph of the document they rest on, and the link opens that page. Where a commission
      publishes a document only through a listing page, we link the listing and say so, and serve our own copy of the document for page references.
      Found an error? <Link href="/discuss?ask=Report%20a%20correction">Report a correction</Link>.</p>
    <h2>Coverage</h2><ul>{Object.entries(site.commissions).map(([k, v]) => <li key={k}><Link href={`/commissions/${k}`}>{v}</Link></li>)}</ul>
    <h2>For software and AI assistants</h2>
    <p>Every page has a Markdown version at the same address with <code>.md</code> added. See <Link href="/llms.txt">llms.txt</Link>,
      the <Link href="/api/v1/orders.json">JSON API</Link> and the <Link href="/feed.xml">RSS feed</Link>.</p>
    <h2>Not legal advice</h2><p>Summaries are for information. Always read the original order, linked from every page.</p>
  </article>);
}
