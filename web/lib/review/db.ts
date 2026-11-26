// The review site's own database (Postgres). It holds a copy of the review pages pushed by the studio's Mac,
// the forms reviewers submit (applied on the Mac, in order), and the reviewers' accounts and sessions.
// The Mac's database stays the source of truth: every page here can be rebuilt from it at any time.
import type { Pool } from "pg";

export type Row = Record<string, any>;

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS rs_pages (path text PRIMARY KEY, html text NOT NULL, hash text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())`,
  `CREATE TABLE IF NOT EXISTS rs_files (id text NOT NULL, n int NOT NULL, total int NOT NULL, size int NOT NULL DEFAULT 0, data bytea, PRIMARY KEY (id, n))`,
  `CREATE TABLE IF NOT EXISTS rs_users (id bigserial PRIMARY KEY, email text UNIQUE NOT NULL, name text NOT NULL, team text NOT NULL,
     pw_hash text, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), last_login timestamptz)`,
  `CREATE TABLE IF NOT EXISTS rs_invites (token_hash text PRIMARY KEY, email text NOT NULL, name text NOT NULL, team text NOT NULL,
     expires_at timestamptz NOT NULL, used_at timestamptz, created_by text, created_at timestamptz NOT NULL DEFAULT now())`,
  `CREATE TABLE IF NOT EXISTS rs_sessions (token_hash text PRIMARY KEY, user_id bigint NOT NULL REFERENCES rs_users(id) ON DELETE CASCADE,
     expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now())`,
  `CREATE TABLE IF NOT EXISTS rs_events (id bigserial PRIMARY KEY, path text NOT NULL, body text NOT NULL, page text NOT NULL DEFAULT '/',
     user_id bigint, user_name text NOT NULL, user_email text NOT NULL, team text NOT NULL,
     created_at timestamptz NOT NULL DEFAULT now(), applied_at timestamptz, status text, note text)`,
  `CREATE INDEX IF NOT EXISTS rs_events_pending ON rs_events (id) WHERE applied_at IS NULL`,
  `CREATE TABLE IF NOT EXISTS rs_attempts (id bigserial PRIMARY KEY, email text NOT NULL, ip text NOT NULL, at timestamptz NOT NULL DEFAULT now())`,
  `CREATE TABLE IF NOT EXISTS rs_chats (id text PRIMARY KEY, started_at timestamptz NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
     page text, ref text, name text, company text, reach text, messages jsonb NOT NULL DEFAULT '[]', ip_hash text, handled_by text, handled_at timestamptz)`,
  `CREATE TABLE IF NOT EXISTS rs_leads (id bigserial PRIMARY KEY, at timestamptz NOT NULL DEFAULT now(), name text NOT NULL, email text NOT NULL,
     org text, business text, state text, asked text, reading text, page text, message text, emailed boolean NOT NULL DEFAULT false, ip_hash text,
     handled_by text, handled_at timestamptz)`,
  `ALTER TABLE rs_chats ADD COLUMN IF NOT EXISTS mailed_at timestamptz`,   // set when the studio Mac has mailed it to sales
  `CREATE TABLE IF NOT EXISTS rs_invite_requests (id bigserial PRIMARY KEY, at timestamptz NOT NULL DEFAULT now(), name text NOT NULL, email text NOT NULL,
     team text NOT NULL, requested_by text NOT NULL, done_at timestamptz, status text, note text)`,
  `CREATE TABLE IF NOT EXISTS rs_meta (key text PRIMARY KEY, value jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())`,
];

export class NoDatabase extends Error {}

type G = typeof globalThis & { __rsPool?: Pool; __rsReady?: Promise<Pool> };
const g = globalThis as G;

async function connect(): Promise<Pool> {
  const url = process.env.REVIEW_DATABASE_URL || process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!url) throw new NoDatabase("The review site has no database yet.");
  const { Pool } = await import("pg");
  const local = /@(localhost|127\.0\.0\.1)[:/]/.test(url);
  const pool = new Pool({ connectionString: url, max: 3, idleTimeoutMillis: 10_000, connectionTimeoutMillis: 10_000, ...(local ? {} : { ssl: true }) });
  for (const s of SCHEMA) await pool.query(s);
  g.__rsPool = pool;
  return pool;
}

export async function q(text: string, params: unknown[] = []): Promise<Row[]> {
  g.__rsReady ??= connect();
  let pool: Pool;
  try {
    pool = await g.__rsReady;
  } catch (e) {
    g.__rsReady = undefined;            // try again on the next request
    throw e;
  }
  return (await pool.query(text, params as any[])).rows;
}

export async function meta(key: string): Promise<any> {
  return (await q("SELECT value FROM rs_meta WHERE key = $1", [key]))[0]?.value ?? null;
}

export async function setMeta(key: string, value: unknown) {
  await q(`INSERT INTO rs_meta(key, value) VALUES ($1, $2::jsonb) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = now()`,
    [key, JSON.stringify(value)]);
}
