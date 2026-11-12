import Link from "next/link";
import { BUILD_DAY, consultations, isOpen, orders, type Consultation } from "@/lib/data";
import { fmtDate } from "@/lib/format";

const day = (iso: string) => Date.parse(iso + "T00:00:00Z") / 86_400_000;
const short = (t: string) => t.replace(/^draft\s+/i, "").replace(/^(central electricity regulatory commission|[A-Z]{4,5})\s*/i, "").replace(/^\(|\)$/g, "").trim();

/** Open drafts by days left to comment, soonest first. Drafts of one commission that close on the same day are one row. */
export function Deadlines() {
  const open = consultations.filter((c) => isOpen(c) && c.comment_deadline);
  const groups = new Map<string, Consultation[]>();
  for (const c of open) { const k = `${c.commission}|${c.comment_deadline}`; groups.set(k, [...(groups.get(k) ?? []), c]); }
  const rows = [...groups.values()].map((g) => ({ g, left: Math.round(day(g[0].comment_deadline!) - day(BUILD_DAY)) })).sort((a, b) => a.left - b.left).slice(0, 6);
  if (!rows.length) return null;
  const max = Math.max(30, ...rows.map((r) => r.left));
  return (
    <figure className="chart glass">
      <figcaption><b>Comment deadlines ahead</b><span>days left</span></figcaption>
      <ul className="bars">{rows.map(({ g, left }) => { const c = g[0]; const code = c.commission.toUpperCase();
        return (
          <li key={c.id} className={left <= 7 ? "soon" : ""} title={`${code}: comments close ${fmtDate(c.comment_deadline)}`}>
            <span className="b-label">{g.length > 1
              ? <Link href={`/consultations#c-${c.commission}`}>{code} · {g.length} drafts</Link>
              : <Link href={c.path}>{code} · {c.impact?.headline || short(c.title)}</Link>}<em>closes {fmtDate(c.comment_deadline)}</em></span>
            <span className="b-track"><span className="b-fill" style={{ width: `${Math.max(1.5, (left / max) * 100)}%` }} /></span>
            <span className="b-val">{left === 0 ? "today" : left}</span>
          </li>); })}</ul>
      <p className="chart-note">Counted from {fmtDate(BUILD_DAY)}, using the last date in each commission&apos;s notice. Check the notice before you rely on a date.</p>
    </figure>
  );
}

/** Tariffs stated in recent orders, one row per order, drawn as the range between the lowest and highest figure the order itself gives. */
export function Tariffs() {
  const rows = orders.flatMap((o) => (o.figures ?? []).filter((f) => f.type === "bars" && /rs\s*\/\s*kwh|₹/i.test(f.unit ?? "")).slice(0, 1).map((f) => {
    const own = f.items.filter((i) => !i.context && typeof i.value === "number"); const vals = (own.length ? own : f.items).map((i) => i.value!);
    return { o, f, lo: Math.min(...vals), hi: Math.max(...vals), n: vals.length };
  })).sort((a, b) => (b.o.date ?? "").localeCompare(a.o.date ?? "")).slice(0, 6);
  if (rows.length < 2) return null;
  const max = Math.max(...rows.map((r) => r.hi)); const pct = (v: number) => (v / max) * 100;
  return (
    <figure className="chart glass">
      <figcaption><b>Tariffs in recent orders</b><span>Rs/kWh</span></figcaption>
      <ul className="bars ranges">{rows.map(({ o, f, lo, hi, n }) => (
        <li key={o.id} title={`${f.title}: ${lo === hi ? lo.toFixed(2) : `${lo.toFixed(2)} to ${hi.toFixed(2)}`} Rs/kWh`}>
          <span className="b-label"><Link href={o.path}>{f.title}</Link><em>{o.commission.toUpperCase()} · {fmtDate(o.date)}{o.draft ? " · awaiting review" : ""}</em></span>
          <span className="b-track">{lo === hi
            ? <span className="r-dot" style={{ left: `${pct(lo)}%` }} />
            : <span className="r-span" style={{ left: `${pct(lo)}%`, width: `${Math.max(1.2, pct(hi) - pct(lo))}%` }} />}</span>
          <span className="b-val">{lo === hi ? lo.toFixed(2) : `${lo.toFixed(2)} to ${hi.toFixed(2)}`}{n > 1 && <em>{n} figures</em>}</span>
        </li>))}</ul>
      <p className="chart-note">Each row is one order and shows the lowest and highest tariff it states for the power approved or adopted. The products differ (round-the-clock, peak, solar with storage), so read a row with its order, not against the others.</p>
    </figure>
  );
}

export default function Overview({ show }: { show: ("deadlines" | "tariffs")[] }) {
  const parts = show.map((s) => s === "deadlines" ? <Deadlines key={s} /> : <Tariffs key={s} />);
  return <div className={`charts overview n${show.length}`}>{parts}</div>;
}
