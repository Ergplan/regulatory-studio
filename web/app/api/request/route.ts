// Studio: a reader asks the team for a full analysis of a draft. The request is emailed to the team's
// inbox (REQUEST_TO); nothing is stored on the site.
import { resend } from "@/lib/subscribe";

export const dynamic = "force-dynamic";
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const clip = (v: FormDataEntryValue | null, n: number) => String(v ?? "").replace(/[\u0000-\u0008\u000b-\u001f]/g, " ").trim().slice(0, n);
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export async function POST(req: Request) {
  const form = await req.formData();
  if (String(form.get("company") ?? "")) return Response.json({ message: "Thanks." }); // honeypot for bots
  const email = clip(form.get("email"), 200).toLowerCase();
  const name = clip(form.get("name"), 120), org = clip(form.get("org"), 160), message = clip(form.get("message"), 2000);
  const draft = clip(form.get("draft"), 300), group = clip(form.get("group"), 80), link = clip(form.get("link"), 300);
  const state = clip(form.get("state"), 60), ask = clip(form.get("ask"), 120);
  if (!EMAIL.test(email)) return Response.json({ message: "Please enter a valid email address." }, { status: 400 });
  if (!name) return Response.json({ message: "Please tell us your name." }, { status: 400 });
  if (!(process.env.RESEND_API_KEY && process.env.RESEND_FROM && process.env.REQUEST_TO)) {
    return Response.json({ message: "Requests are not open on this site yet. Please check back soon." }, { status: 503 });
  }
  const rows: [string, string][] = [["From", `${name} <${email}>`], ["Organisation", org || "-"], ["Business", group || "-"], ["State", state || "-"], ["Asked for", ask || "-"],
    ["Was reading", draft || "-"], ["Page", link || "-"], ["Message", message || "-"]];
  const res = await resend("/emails", {
    from: process.env.RESEND_FROM, to: [process.env.REQUEST_TO], reply_to: email,
    subject: `Project review request: ${ask || draft || "general"}`.slice(0, 180),
    text: rows.map(([k, v]) => `${k}: ${v}`).join("\n"),
    html: `<table>${rows.map(([k, v]) => `<tr><td style="padding:4px 12px 4px 0;color:#666;vertical-align:top">${k}</td><td style="padding:4px 0">${esc(v).replace(/\n/g, "<br>")}</td></tr>`).join("")}</table>`,
  });
  if (!res.ok) return Response.json({ message: "We could not send your request. Please try again later." }, { status: 502 });
  return Response.json({ message: "Request received. The team will reply by email." });
}
