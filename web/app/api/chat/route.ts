// The chat box: a visitor's conversation is saved here for the jouleWise team, who read it on the review site.
// The browser sends the whole conversation each time, so a save that failed is made good by the next one.
import { createHash } from "node:crypto";
import { q, NoDatabase } from "@/lib/review/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const clip = (v: unknown, n: number) => String(v ?? "").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, " ").trim().slice(0, n);
const json = (b: unknown, status = 200) => Response.json(b, { status, headers: { "Cache-Control": "no-store" } });

export async function POST(req: Request) {
  let b: any;
  try {
    const raw = await req.text();
    if (raw.length > 60_000) return json({ ok: false, error: "too long" }, 413);
    b = JSON.parse(raw);
  } catch {
    return json({ ok: false, error: "bad request" }, 400);
  }
  if (!/^[0-9a-f]{32}$/.test(String(b.id ?? ""))) return json({ ok: false, error: "bad id" }, 400);
  if (clip(b.website, 200)) return json({ ok: true });                                     // honeypot: bots fill it
  const messages = (Array.isArray(b.messages) ? b.messages : []).slice(0, 60)
    .map((m: any) => ({ at: Number(m.at) || Date.now(), text: clip(m.text, 2000) })).filter((m: any) => m.text);
  const c = b.contact ?? {};
  const contact = { name: clip(c.name, 160), company: clip(c.company, 160), reach: clip(c.reach, 160) };
  if (!messages.length && !contact.reach) return json({ ok: false, error: "empty" }, 400);
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const ipHash = createHash("sha256").update("rs-chat|" + ip).digest("hex").slice(0, 24);
  try {
    const recent = Number((await q("SELECT count(*) AS n FROM rs_chats WHERE ip_hash = $1 AND started_at > now() - interval '1 hour' AND id <> $2", [ipHash, b.id]))[0].n);
    if (recent >= 12) return json({ ok: false, error: "Too many conversations from here. Please write to us by email." }, 429);
    const started = new Date(Math.min(Date.now(), Number(b.started) || Date.now())).toISOString();
    await q(`INSERT INTO rs_chats(id, started_at, page, ref, name, company, reach, messages, ip_hash)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
             ON CONFLICT (id) DO UPDATE SET updated_at = now(), messages = excluded.messages,
               name = coalesce(nullif(excluded.name, ''), rs_chats.name), company = coalesce(nullif(excluded.company, ''), rs_chats.company),
               reach = coalesce(nullif(excluded.reach, ''), rs_chats.reach)`,
      [b.id, started, clip(b.page, 200), clip(b.ref, 300), contact.name, contact.company, contact.reach, JSON.stringify(messages), ipHash]);
    return json({ ok: true });
  } catch (e) {
    if (e instanceof NoDatabase) return json({ ok: false, error: "not open yet" }, 503);
    console.error("chat", e);
    return json({ ok: false, error: "server error" }, 500);
  }
}
