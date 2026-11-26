// "Discuss my project": a reader's request is saved for the jouleWise team (they read it in the review site's Inbox).
// The studio Mac then mails it to sales@joulewise.com through Gmail (pipeline/regstudio/mailer.py, run by the sync job).
// If RESEND_API_KEY and RESEND_FROM are set here, it is emailed at once instead and the Mac skips it.
import { createHash } from "node:crypto";
import { resend } from "@/lib/subscribe";
import { q } from "@/lib/review/db";
import { SALES_EMAIL } from "@/lib/contact";

export const runtime = "nodejs";
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
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const ipHash = createHash("sha256").update("rs-lead|" + ip).digest("hex").slice(0, 24);

  let saved = false;
  try {
    const recent = Number((await q("SELECT count(*) AS n FROM rs_leads WHERE ip_hash = $1 AND at > now() - interval '1 hour'", [ipHash]))[0].n);
    if (recent >= 6) return Response.json({ message: `Too many requests from here. Please write to ${SALES_EMAIL}.` }, { status: 429 });
    await q(`INSERT INTO rs_leads(name, email, org, business, state, asked, reading, page, message, ip_hash) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
      [name, email, org, group, state, ask, draft, link, message, ipHash]);
    saved = true;
  } catch (e) { console.error("lead", e); }

  let emailed = false;
  if (process.env.RESEND_API_KEY && process.env.RESEND_FROM) {
    const rows: [string, string][] = [["From", `${name} <${email}>`], ["Organisation", org || "-"], ["Business", group || "-"], ["State", state || "-"], ["Asked for", ask || "-"],
      ["Was reading", draft || "-"], ["Page", link || "-"], ["Message", message || "-"]];
    const res = await resend("/emails", {
      from: process.env.RESEND_FROM, to: [process.env.REQUEST_TO || SALES_EMAIL], reply_to: email,
      subject: `Regulatory Studio: project review request${ask || draft ? `: ${ask || draft}` : ""}`.slice(0, 180),
      text: rows.map(([k, v]) => `${k}: ${v}`).join("\n"),
      html: `<table>${rows.map(([k, v]) => `<tr><td style="padding:4px 12px 4px 0;color:#666;vertical-align:top">${k}</td><td style="padding:4px 0">${esc(v).replace(/\n/g, "<br>")}</td></tr>`).join("")}</table>`,
    }).catch(() => null);
    emailed = Boolean(res?.ok);
    if (saved && emailed) await q("UPDATE rs_leads SET emailed = true WHERE ip_hash = $1 AND email = $2 AND at > now() - interval '1 minute'", [ipHash, email]).catch(() => {});
  }
  if (!saved && !emailed) return Response.json({ message: `We could not send your request. Please write to ${SALES_EMAIL}.`, fallback: true }, { status: 502 });
  return Response.json({ message: "Request received. The jouleWise team will reply by email." });
}
