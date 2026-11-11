import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Subscription", robots: { index: false } };
const TEXT: Record<string, [string, string]> = {
  ok: ["You are subscribed", "The weekly digest will arrive after each week's orders have been reviewed. Every email has an unsubscribe link."],
  expired: ["That link has expired", "Confirmation links work for 7 days. Please sign up again from the home page."],
  error: ["Something went wrong", "We could not complete your subscription. Please try again later."],
};
export default async function Subscribed({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status = "ok" } = await searchParams;
  const [title, body] = TEXT[status] ?? TEXT.ok;
  return <div className="card" style={{ maxWidth: 620 }}><h1>{title}</h1><p>{body}</p><p><Link href="/">Back to Regulatory Studio</Link></p></div>;
}
