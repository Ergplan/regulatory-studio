// Double opt-in without a database: the confirmation link carries the email and time,
// signed with SUBSCRIBE_SECRET. The contact is created in Resend only after the click.
import { createHmac, timingSafeEqual } from "node:crypto";

const MAX_AGE_MS = 7 * 24 * 3600 * 1000;

export function configured(): boolean {
  return Boolean(process.env.RESEND_API_KEY && process.env.RESEND_SEGMENT_ID && process.env.RESEND_FROM && process.env.SUBSCRIBE_SECRET);
}

function sign(payload: string): string {
  return createHmac("sha256", process.env.SUBSCRIBE_SECRET!).update(payload).digest("base64url");
}

export function makeToken(email: string): string {
  const payload = Buffer.from(JSON.stringify({ e: email, t: Date.now() })).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

export function readToken(token: string): string | null {
  const [payload, mac] = token.split(".");
  if (!payload || !mac) return null;
  const good = Buffer.from(sign(payload)), given = Buffer.from(mac);
  if (good.length !== given.length || !timingSafeEqual(good, given)) return null;
  try {
    const { e, t } = JSON.parse(Buffer.from(payload, "base64url").toString());
    return typeof e === "string" && Date.now() - t < MAX_AGE_MS ? e : null;
  } catch { return null; }
}

export async function resend(path: string, body: unknown): Promise<Response> {
  return fetch(`https://api.resend.com${path}`, {
    method: "POST",
    headers: { authorization: `Bearer ${process.env.RESEND_API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}
