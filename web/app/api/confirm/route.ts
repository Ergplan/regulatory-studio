import { SITE_URL } from "@/lib/data";
import { configured, readToken, resend } from "@/lib/subscribe";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("t") ?? "";
  const email = configured() ? readToken(token) : null;
  if (!email) return Response.redirect(`${SITE_URL}/subscribed?status=expired`, 303);
  const res = await resend("/contacts", { email, unsubscribed: false, segments: [{ id: process.env.RESEND_SEGMENT_ID }] });
  // 409/422 typically means the contact already exists; treat as confirmed.
  if (!res.ok && res.status !== 409 && res.status !== 422) return Response.redirect(`${SITE_URL}/subscribed?status=error`, 303);
  return Response.redirect(`${SITE_URL}/subscribed?status=ok`, 303);
}
