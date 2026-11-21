import type { Metadata } from "next";
import { SALES_EMAIL } from "@/lib/contact";

export const metadata: Metadata = { title: "Privacy", alternates: { canonical: "/privacy" } };

export default function Privacy() {
  return (<article className="prose">
    <p className="eyebrow">Privacy</p>
    <h1>What we keep, and why</h1>
    <p>Regulatory Studio is run by jouleWise and Urja Praxis. Reading the site needs no account and sets no advertising cookies.</p>
    <h2>The chat box</h2>
    <p>What you write in the chat, and any name, company, phone number or email you leave, is saved so the jouleWise team can read it and reply.
      Automatic replies come from the site's own answers to common questions; no AI model reads your messages. We also keep a one-way code made
      from your network address, only to limit abuse; it cannot be turned back into the address.</p>
    <h2>Project review requests</h2>
    <p>What you enter in "Discuss my project" is saved for the jouleWise team and may also be emailed to {SALES_EMAIL}. We use it to reply to you
      and to prepare the review you asked for.</p>
    <h2>The weekly digest</h2>
    <p>If you subscribe, we keep your email address to send the digest. Every email has a link to unsubscribe.</p>
    <h2>Your choices</h2>
    <p>To see, correct or delete what we hold about you, write to <a href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>. We do not sell or share it with
      anyone else.</p>
  </article>);
}
