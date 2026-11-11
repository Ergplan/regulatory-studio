// Free weekly digest sign-up: sends a confirmation link; nothing is stored until it is clicked.
import { SITE_URL } from "@/lib/data";
import { configured, makeToken, resend } from "@/lib/subscribe";

export const dynamic = "force-dynamic";
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export async function POST(req: Request) {
  const form = await req.formData();
  if (String(form.get("company") ?? "")) return Response.json({ message: "Thanks." }); // honeypot for bots
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 200) {
    return Response.json({ message: "Please enter a valid email address." }, { status: 400 });
  }
  if (!configured()) {
    return Response.json({ message: "Sign-ups open with the first weekly digest. Please check back soon." }, { status: 503 });
  }
  const link = `${SITE_URL}/api/confirm?t=${encodeURIComponent(makeToken(email))}`;
  const res = await resend("/emails", {
    from: process.env.RESEND_FROM, to: [email],
    subject: "Confirm your Regulatory Studio weekly digest",
    html: `<p>Please confirm you would like the free Regulatory Studio weekly digest of Indian electricity regulatory orders.</p>
<p><a href="${link}">Confirm my subscription</a></p>
<p style="color:#666;font-size:13px">If you did not ask for this, ignore this email and nothing will happen. The link works for 7 days.</p>`,
    text: `Confirm your Regulatory Studio weekly digest: ${link}\n\nIf you did not ask for this, ignore this email.`,
  });
  if (!res.ok) return Response.json({ message: "We could not send the confirmation email. Please try again later." }, { status: 502 });
  return Response.json({ message: "Check your inbox and click the link to confirm." });
}
