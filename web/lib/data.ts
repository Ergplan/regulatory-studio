// Build-time access to the approved snapshot written by `regstudio publish`.
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

export type LinkType = "applies" | "interprets" | "relaxes" | "follows" | "distinguishes" | "appealed_in"
  | "upholds" | "sets_aside" | "remands" | "amends" | "made_under";
export type TargetKind = "clause" | "regulation" | "act_section" | "document";

export interface Link { type: LinkType; kind: TargetKind; target: string; cited_as: string; pid: string; excerpt: string; page: number | null }
export interface Order {
  id: string; path: string; commission: string; doc_type: string; title: string | null; case_number: string | null;
  date: string | null; source_url: string; pdf: string; topics: string[]; significance: number;
  parties: { name: string; role: string }[]; issue: string; outcome: string; summary: string;
  reviewed_by: string; approved_at: string; revised_at: string | null; language: string | null; sample: boolean; draft?: boolean; links: Link[];
}
export interface Regulation { id: string; path: string; commission: string; title: string; short_title: string | null; notified_date: string | null; source_url: string | null; sample: boolean }
export interface ClauseVersion { text: string; in_force_from: string | null; in_force_to: string | null }
export interface Clause { id: string; path: string; regulation_id: string; number: string; heading: string | null; text: string; in_force_from: string | null; in_force_to: string | null; versions?: ClauseVersion[] }
export interface ActSection { id: string; act: string; number: string; title: string }
export interface Digest { id: string; path: string; from: string; to: string; intro: string; items: string[]; approved_at: string; reviewed_by: string; draft?: boolean }
export interface Site { generated_at: string; commissions: Record<string, string>; topics: Record<string, string>; link_types: Record<string, string>; contains_sample_data: boolean; preview?: boolean }

const DIR = resolve(process.cwd(), process.env.SNAPSHOT_DIR ?? "../data/snapshot");

function load<T>(name: string, fallback: T): T {
  const p = resolve(DIR, name);
  return existsSync(p) ? (JSON.parse(readFileSync(p, "utf8")) as T) : fallback;
}

// Until the real domain is set, the site is not indexed (see robots.ts and layout.tsx).
export const LAUNCHED = Boolean(process.env.NEXT_PUBLIC_SITE_URL);
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000")).replace(/\/$/, "");
// Coverage shown before the first publish; the published site.json replaces it.
const DEFAULT_COMMISSIONS: Record<string, string> = {
  cerc: "Central Electricity Regulatory Commission", aptel: "Appellate Tribunal for Electricity",
  uperc: "Uttar Pradesh Electricity Regulatory Commission", merc: "Maharashtra Electricity Regulatory Commission",
  gerc: "Gujarat Electricity Regulatory Commission", kerc: "Karnataka Electricity Regulatory Commission",
  rerc: "Rajasthan Electricity Regulatory Commission",
};
export const site = load<Site>("site.json", { generated_at: "", commissions: DEFAULT_COMMISSIONS, topics: {}, link_types: {}, contains_sample_data: false });
export const orders = load<Order[]>("orders.json", []).sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
export const regulations = load<Regulation[]>("regulations.json", []);
export const clauses = load<Clause[]>("clauses.json", []);
export const actSections = load<ActSection[]>("act_sections.json", []);
export const digests = load<Digest[]>("digests.json", []);

export const orderById = new Map(orders.map((o) => [o.id, o]));
export const clauseById = new Map(clauses.map((c) => [c.id, c]));
export const regulationById = new Map(regulations.map((r) => [r.id, r]));
export const actById = new Map(actSections.map((a) => [a.id, a]));

export const actPath = (id: string) => `/act/${id}`;

/** "Central Electricity Regulatory Commission (Deviation Settlement Mechanism and Related Matters) Regulations, 2024"
 *  -> "Deviation Settlement Mechanism and Related Matters Regulations, 2024", unless a reviewer set a short title. */
export function regName(r: Regulation): string {
  if (r.short_title) return r.short_title;
  const m = r.title.match(/\(([^)]+)\)\s*(Regulations?,?\s*\d{4})/);
  return m ? `${m[1]} ${m[2]}` : r.title;
}

export function targetInfo(kind: TargetKind, id: string): { label: string; sub: string; href: string } | null {
  if (kind === "clause") {
    const c = clauseById.get(id); if (!c) return null;
    const r = regulationById.get(c.regulation_id);
    return { label: `Reg. ${c.number}${c.heading ? " · " + c.heading : ""}`, sub: r ? `${r.commission.toUpperCase()} · ${regName(r)}` : "", href: c.path };
  }
  if (kind === "regulation") {
    const r = regulationById.get(id); if (!r) return null;
    return { label: regName(r), sub: r.commission.toUpperCase(), href: r.path };
  }
  if (kind === "act_section") {
    const a = actById.get(id); if (!a) return null;
    return { label: `Section ${a.number}`, sub: `Electricity Act, 2003 · ${a.title}`, href: actPath(a.id) };
  }
  const o = orderById.get(id); if (!o) return null;
  return { label: orderLabel(o), sub: `${o.commission.toUpperCase()} · ${o.date ?? ""}`, href: o.path };
}

export function orderLabel(o: Order): string {
  return o.case_number ?? o.title ?? o.id.slice(0, 12);
}

/** Orders that link to a given target, with the link types used. */
export function citingOrders(kind: TargetKind, id: string): { order: Order; links: Link[] }[] {
  const out: { order: Order; links: Link[] }[] = [];
  for (const o of orders) {
    const ls = o.links.filter((l) => l.kind === kind && l.target === id);
    if (ls.length) out.push({ order: o, links: ls });
  }
  return out;
}

export function clausesOf(regId: string): Clause[] {
  return clauses.filter((c) => c.regulation_id === regId);
}

export const linkTypeLabel = (t: string) => site.link_types[t] ?? t;
export const commissionName = (c: string) => site.commissions[c] ?? c.toUpperCase();
export const topicName = (t: string) => site.topics[t] ?? t;
