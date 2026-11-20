// Sign-in for the review site. Reviewers are invited by a one-time link and choose their own password.
// Passwords are stored only as scrypt hashes; sessions and invitations only as SHA-256 hashes of random tokens.
import { createHash, randomBytes, scrypt as scryptCb, timingSafeEqual } from "node:crypto";
import { q, type Row } from "./db";

export const COOKIE = "rs_sid";
export const SESSION_DAYS = 7;
export const TEAMS = ["urja", "joulewise", "admin"] as const;
export type Team = (typeof TEAMS)[number];
export type User = { id: number; email: string; name: string; team: Team };

export const sha = (s: string) => createHash("sha256").update(s).digest("hex");
export const token = () => randomBytes(32).toString("base64url");

const scrypt = (pw: string, salt: Buffer) => new Promise<Buffer>((ok, no) =>
  scryptCb(pw.normalize("NFKC"), salt, 64, { N: 32768, r: 8, p: 1, maxmem: 128 * 32768 * 8 * 2 }, (e, k) => (e ? no(e) : ok(k))));

export async function hashPassword(pw: string): Promise<string> {
  const salt = randomBytes(16);
  return `s1$${salt.toString("base64")}$${(await scrypt(pw, salt)).toString("base64")}`;
}

export async function checkPassword(pw: string, stored: string | null): Promise<boolean> {
  const [v, salt, hash] = (stored || "").split("$");
  // Always do the work, so a missing account takes as long as a wrong password.
  const got = await scrypt(pw, Buffer.from(salt || "AAAAAAAAAAAAAAAAAAAAAA==", "base64"));
  const want = Buffer.from(hash || "", "base64");
  return v === "s1" && want.length === got.length && timingSafeEqual(got, want);
}

export function passwordProblem(pw: string, email: string): string | null {
  if (pw.length < 12) return "Use at least 12 characters.";
  if (pw.length > 200) return "That is too long.";
  if (pw.toLowerCase().includes(email.split("@")[0].toLowerCase())) return "Do not use your email name in the password.";
  if (/^(.)\1+$/.test(pw) || /^(password|12345|qwerty)/i.test(pw)) return "That password is too easy to guess.";
  return null;
}

export function cookieOf(req: Request, name: string): string | null {
  for (const part of (req.headers.get("cookie") || "").split(/;\s*/)) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i) === name) return decodeURIComponent(part.slice(i + 1));
  }
  return null;
}

export async function currentUser(req: Request): Promise<User | null> {
  const sid = cookieOf(req, COOKIE);
  if (!sid || sid.length > 100) return null;
  const rows = await q(
    `SELECT u.id, u.email, u.name, u.team FROM rs_sessions s JOIN rs_users u ON u.id = s.user_id
     WHERE s.token_hash = $1 AND s.expires_at > now() AND u.active`, [sha(sid)]);
  return (rows[0] as User) ?? null;
}

export async function startSession(userId: number): Promise<string> {
  const t = token();
  await q(`INSERT INTO rs_sessions(token_hash, user_id, expires_at) VALUES ($1, $2, now() + ($3 || ' days')::interval)`, [sha(t), userId, String(SESSION_DAYS)]);
  await q("DELETE FROM rs_sessions WHERE expires_at < now()");
  await q("UPDATE rs_users SET last_login = now() WHERE id = $1", [userId]);
  return t;
}

export const sessionCookie = (value: string, secure: boolean, maxAge = SESSION_DAYS * 86400) =>
  `${COOKIE}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure ? "; Secure" : ""}`;

export const ipOf = (req: Request) => (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "unknown";

/** Too many wrong passwords for this email or from this address in the last 15 minutes. */
export async function lockedOut(email: string, ip: string): Promise<boolean> {
  const r = (await q(
    `SELECT count(*) FILTER (WHERE email = $1) AS by_email, count(*) FILTER (WHERE ip = $2) AS by_ip
     FROM rs_attempts WHERE at > now() - interval '15 minutes'`, [email, ip]))[0] as Row;
  return Number(r.by_email) >= 8 || Number(r.by_ip) >= 30;
}

export async function recordFailure(email: string, ip: string) {
  await q("INSERT INTO rs_attempts(email, ip) VALUES ($1, $2)", [email.slice(0, 200), ip.slice(0, 80)]);
  await q("DELETE FROM rs_attempts WHERE at < now() - interval '1 day'");
}

/** What each team may submit. Everyone may comment; only the commercial team decides illustrations, only the legal team the law. */
export function allowed(team: Team, path: string): boolean {
  if (team === "admin") return true;
  if (/^\/(notes\/|comment\/|digest\/[^/]+\/note$)/.test(path)) return true;
  if (/^\/commercial\//.test(path)) return team === "joulewise";
  return team === "urja";
}
