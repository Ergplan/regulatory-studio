// Weekly archive: every published order and draft regulation, grouped by the week (Monday to Sunday) of its date.
import { consultations, digests, orders, type Consultation, type Order } from "@/lib/data";

export interface Week { id: string; path: string; from: string; to: string; orders: Order[]; drafts: Consultation[]; pending: number; digest?: string }

const iso = (d: Date) => d.toISOString().slice(0, 10);

/** ISO week of a YYYY-MM-DD date: id like "2026-w47", with its Monday and Sunday. */
export function weekOf(date: string): { id: string; from: string; to: string } {
  const d = new Date(date + "T00:00:00Z");
  const monday = new Date(d); monday.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  const sunday = new Date(monday); sunday.setUTCDate(monday.getUTCDate() + 6);
  const thursday = new Date(monday); thursday.setUTCDate(monday.getUTCDate() + 3);
  const jan4 = new Date(Date.UTC(thursday.getUTCFullYear(), 0, 4));
  const week1 = new Date(jan4); week1.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7));
  const n = Math.round((monday.getTime() - week1.getTime()) / 604800000) + 1;
  return { id: `${thursday.getUTCFullYear()}-w${String(n).padStart(2, "0")}`, from: iso(monday), to: iso(sunday) };
}

function build(): Week[] {
  const map = new Map<string, Week>();
  const slot = (date: string | null) => {
    if (!date || !/^\d{4}-\d{2}-\d{2}/.test(date)) return null;
    const w = weekOf(date.slice(0, 10));
    if (!map.has(w.id)) map.set(w.id, { ...w, path: `/archive/${w.id}`, orders: [], drafts: [], pending: 0 });
    return map.get(w.id)!;
  };
  for (const o of orders) { const w = slot(o.date); if (w) { w.orders.push(o); if (o.draft) w.pending++; } }
  for (const c of consultations) { const w = slot(c.issued); if (w) { w.drafts.push(c); if (c.draft) w.pending++; } }
  for (const w of map.values()) {
    w.orders.sort((a, b) => (b.significance ?? 0) - (a.significance ?? 0) || (b.date ?? "").localeCompare(a.date ?? ""));
    w.digest = digests.find((d) => d.id.toLowerCase() === w.id)?.path;
  }
  return [...map.values()].sort((a, b) => b.from.localeCompare(a.from));
}

export const weeks: Week[] = build();
