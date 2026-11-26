// The studio's Mac calls this, and only this, to keep the review site in step. Each request is signed with the
// Mac's Ed25519 key; this site holds the public half in STUDIO_SYNC_PUBLIC_KEY. Nothing here is reachable
// without a valid signature made in the last five minutes.
import { createHash, createPublicKey, verify } from "node:crypto";
import { q, setMeta, NoDatabase } from "@/lib/review/db";
import { TEAMS } from "@/lib/review/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

function signedBy(body: string, stamp: string | null, sig: string | null): boolean {
  const raw = Buffer.from(process.env.STUDIO_SYNC_PUBLIC_KEY || "", "base64");
  if (raw.length !== 32 || !stamp || !sig || !/^\d{9,11}$/.test(stamp)) return false;
  if (Math.abs(Date.now() / 1000 - Number(stamp)) > 300) return false;
  try {
    const key = createPublicKey({ key: Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), raw]), format: "der", type: "spki" });
    const digest = createHash("sha256").update(body).digest("hex");
    return verify(null, Buffer.from(`${stamp}\n${digest}`), key, Buffer.from(sig, "base64"));
  } catch {
    return false;
  }
}

export async function POST(req: Request) {
  const body = await req.text();
  if (!signedBy(body, req.headers.get("x-studio-time"), req.headers.get("x-studio-sig"))) return json({ error: "bad signature" }, 401);
  let m: any;
  try {
    m = JSON.parse(body);
  } catch {
    return json({ error: "bad request" }, 400);
  }
  try {
    switch (m.op) {
      case "hello": {
        await setMeta("mac", { at: new Date().toISOString(), status: m.status ?? null });
        if (m.light) return json({ ok: true });
        const pages = Object.fromEntries((await q("SELECT path, hash FROM rs_pages")).map((r) => [r.path, r.hash]));
        const files = (await q("SELECT id FROM rs_files GROUP BY id, total HAVING count(*) >= greatest(total, 1)")).map((r) => r.id);
        const pending = Number((await q("SELECT count(*) AS n FROM rs_events WHERE applied_at IS NULL"))[0].n);
        return json({ ok: true, pages, files, pending });
      }
      case "pages": {
        for (const p of (m.pages ?? []) as { path: string; html: string; hash: string }[]) {
          if (typeof p.path !== "string" || !p.path.startsWith("/") || typeof p.html !== "string") continue;
          await q(`INSERT INTO rs_pages(path, html, hash) VALUES ($1, $2, $3)
                   ON CONFLICT (path) DO UPDATE SET html = excluded.html, hash = excluded.hash, updated_at = now()`, [p.path, p.html, String(p.hash)]);
        }
        if (Array.isArray(m.remove) && m.remove.length) await q("DELETE FROM rs_pages WHERE path = ANY($1::text[])", [m.remove]);
        return json({ ok: true });
      }
      case "file": {
        if (!/^[0-9a-f]{64}$/.test(m.id ?? "")) return json({ error: "bad id" }, 400);
        const data = m.total ? Buffer.from(String(m.data ?? ""), "base64") : null;
        if (Number(m.n) === 0) await q("DELETE FROM rs_files WHERE id = $1", [m.id]);
        await q(`INSERT INTO rs_files(id, n, total, size, data) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id, n) DO UPDATE SET data = excluded.data, total = excluded.total, size = excluded.size`,
          [m.id, Number(m.n) || 0, Number(m.total) || 0, Number(m.size) || 0, data]);
        return json({ ok: true });
      }
      case "events": {
        const events = await q(`SELECT id, path, body, user_name, user_email, team, created_at FROM rs_events WHERE applied_at IS NULL ORDER BY id LIMIT 50`);
        return json({ events: events.map((e) => ({ ...e, id: Number(e.id) })) });
      }
      case "ack": {
        for (const r of (m.results ?? []) as { id: number; status: string; note?: string }[]) {
          await q("UPDATE rs_events SET applied_at = now(), status = $2, note = $3 WHERE id = $1 AND applied_at IS NULL",
            [Number(r.id), String(r.status).slice(0, 20), String(r.note ?? "").slice(0, 300)]);
        }
        return json({ ok: true });
      }
      case "invite": {
        const email = String(m.email ?? "").trim().toLowerCase();
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !TEAMS.includes(m.team) || !/^[0-9a-f]{64}$/.test(m.token_hash ?? "") || !String(m.name ?? "").trim())
          return json({ error: "bad invitation" }, 400);
        const days = Math.min(30, Math.max(1, Number(m.days) || 7));
        await q(`INSERT INTO rs_invites(token_hash, email, name, team, expires_at, created_by) VALUES ($1, $2, $3, $4, now() + ($5 || ' days')::interval, 'the studio Mac')
                 ON CONFLICT (token_hash) DO NOTHING`, [m.token_hash, email, String(m.name).trim().slice(0, 80), m.team, String(days)]);
        return json({ ok: true });
      }
      case "leads": {
        // New project requests, and chats where the visitor left contact details, for the Mac to mail to sales.
        const leads = await q(`SELECT id, at, name, email, org, business, state, asked, reading, page, message
                               FROM rs_leads WHERE NOT emailed ORDER BY id LIMIT 20`);
        const chats = await q(`SELECT id, started_at, updated_at, page, name, company, reach, messages FROM rs_chats
                               WHERE mailed_at IS NULL AND coalesce(reach, '') <> '' ORDER BY updated_at LIMIT 20`);
        return json({ leads: leads.map((l) => ({ ...l, id: Number(l.id) })), chats });
      }
      case "leads_mailed": {
        const leads = ((m.leads ?? []) as unknown[]).map(Number).filter((n) => Number.isInteger(n) && n > 0);
        const chats = ((m.chats ?? []) as unknown[]).map(String).filter((c) => /^[0-9a-f]{32}$/.test(c));
        if (leads.length) await q("UPDATE rs_leads SET emailed = true WHERE id = ANY($1::bigint[])", [leads]);
        if (chats.length) await q("UPDATE rs_chats SET mailed_at = now() WHERE id = ANY($1::text[])", [chats]);
        return json({ ok: true });
      }
      case "invite_requests": {
        const requests = await q(`SELECT id, name, email, team FROM rs_invite_requests WHERE done_at IS NULL AND at > now() - interval '7 days' ORDER BY id LIMIT 20`);
        return json({ requests: requests.map((r) => ({ ...r, id: Number(r.id) })) });
      }
      case "invite_requests_done": {
        for (const r of (m.results ?? []) as { id: number; status: string; note?: string }[])
          await q("UPDATE rs_invite_requests SET done_at = now(), status = $2, note = $3 WHERE id = $1 AND done_at IS NULL",
            [Number(r.id), String(r.status).slice(0, 20), String(r.note ?? "").slice(0, 300)]);
        return json({ ok: true });
      }
      default:
        return json({ error: "unknown op" }, 400);
    }
  } catch (e) {
    if (e instanceof NoDatabase) return json({ error: "no database" }, 503);
    console.error("sync", e);
    return json({ error: "server error" }, 500);
  }
}
