import Link from "next/link";
import { Cites } from "@/components/Impact";
import { BUILD_DAY, type Consultation, type Figure, type FigureItem } from "@/lib/data";
import { fmtDate } from "@/lib/format";

const places = (f: Figure) => Math.min(2, Math.max(0, ...f.items.map((i) => (String(i.value ?? 0).split(".")[1] ?? "").length)));
const fmt = (v: number, d = 0) => v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: Math.max(d, 2) });
const day = (iso: string) => Date.parse(iso + "T00:00:00Z") / 86_400_000;

function Bars({ f }: { f: Figure }) {
  const d = places(f); const num = (v: number) => fmt(v, d);
  const max = Math.max(...f.items.map((i) => i.value ?? 0)) || 1;
  return (
    <ul className="bars">{f.items.map((i) => (
      <li key={i.label} className={i.context ? "ctx" : ""} title={`${i.label}: ${num(i.value ?? 0)} ${f.unit ?? ""}${i.tag ? ` (${i.tag})` : ""}`}>
        <span className="b-label">{i.href ? <Link href={i.href}>{i.label}</Link> : i.label}{i.tag && <em>{i.tag}</em>}</span>
        <span className="b-track"><span className="b-fill" style={{ width: `${Math.max(1.5, ((i.value ?? 0) / max) * 100)}%` }} /></span>
        <span className="b-val">{num(i.value ?? 0)}</span>
      </li>))}</ul>
  );
}

function Series({ f }: { f: Figure }) {
  const dp = places(f); const num = (v: number) => fmt(v, dp);
  const max = Math.max(...f.items.map((i) => i.value ?? 0)) || 1;
  return (
    <ol className="cols" style={{ gridTemplateColumns: `repeat(${f.items.length}, minmax(0, 1fr))` }}>{f.items.map((i, n) => {
      const prev = n ? f.items[n - 1].value ?? 0 : null; const d = prev === null ? null : (i.value ?? 0) - prev;
      return (
        <li key={i.label} title={`${i.label}: ${num(i.value ?? 0)} ${f.unit ?? ""}`}>
          <span className="c-plot"><span className="c-val">{num(i.value ?? 0)}{d !== null && d !== 0 && <em>{d > 0 ? "+" : "−"}{num(Math.abs(d))}</em>}</span>
            <span className="c-bar" style={{ height: `${Math.max(2, ((i.value ?? 0) / max) * 100)}%` }} /></span>
          <span className="c-label">{i.label}</span>
        </li>);
    })}</ol>
  );
}

function Timeline({ f }: { f: Figure }) {
  const pts = f.items.flatMap((i) => [day(i.start!), i.end ? day(i.end) : day(i.start!)]);
  const lo = Math.min(...pts), hi = Math.max(...pts); const span = Math.max(1, hi - lo);
  const pos = (d: number) => ((d - lo) / span) * 100;
  const today = day(BUILD_DAY); const showToday = today > lo && today < hi;
  return (
    <div className="tl">
      <ol>{f.items.map((i) => { const a = pos(day(i.start!)); const b = i.end ? pos(day(i.end)) : a; const past = (i.end ? day(i.end) : day(i.start!)) < today;
        return (
          <li key={i.label + i.start} className={past ? "past" : ""} title={`${i.label}: ${fmtDate(i.start)}${i.end ? ` to ${fmtDate(i.end)}` : ""}`}>
            <span className="t-label">{i.label}<em>{fmtDate(i.start)}{i.end ? ` to ${fmtDate(i.end)}` : ""}</em></span>
            <span className="t-track">{showToday && <span className="t-today" style={{ left: `${pos(today)}%` }} />}
              {i.end ? <span className="t-span" style={{ left: `${a}%`, width: `${Math.max(1.5, b - a)}%` }} /> : <span className="t-dot" style={{ left: `${a}%` }} />}</span>
          </li>); })}</ol>
      <p className="t-axis"><span>{fmtDate(new Date(lo * 86_400_000).toISOString().slice(0, 10))}</span>{showToday && <span className="t-now">▏today, {fmtDate(BUILD_DAY)}</span>}<span>{fmtDate(new Date(hi * 86_400_000).toISOString().slice(0, 10))}</span></p>
    </div>
  );
}

/** A schematic of a rule or a decision: steps in order, with the branch taken when a condition is not met. */
function Flow({ f, pdf }: { f: Figure; pdf?: string | null }) {
  return (
    <ol className="flowchart">{f.items.map((i, n) => (
      <li key={i.label} className={n === f.items.length - 1 ? "end" : ""}>
        <span className="f-n" aria-hidden="true">{n + 1}</span>
        <div className="f-step"><b>{i.label}</b>{i.detail && <p>{i.detail}</p>}<Cites basis={i.basis} pdf={pdf} /></div>
        {i.otherwise && <p className="f-else"><span>If not</span>{i.otherwise}</p>}
      </li>))}</ol>
  );
}

const cell = (f: Figure, i: FigureItem) => f.type === "timeline" ? `${fmtDate(i.start)}${i.end ? ` to ${fmtDate(i.end)}` : ""}` : `${fmt(i.value ?? 0, places(f))} ${f.unit ?? ""}`;

/** Dates every consultation has, drawn as a timeline when the document's own charts do not already include one. */
export function consultationTimeline(c: Consultation): Figure | null {
  const items: FigureItem[] = [];
  if (c.issued) items.push({ label: "Draft issued", start: c.issued, basis: [] });
  if (c.comment_deadline) items.push({ label: "Comments close", start: c.comment_deadline, basis: [] });
  if (c.hearing_date) items.push({ label: "Public hearing", start: c.hearing_date, basis: [] });
  return items.length >= 2 ? { type: "timeline", title: "Consultation dates", note: "Dates as given in the commission's listing.", items } : null;
}

/** Small charts chosen for a summary: bars for comparable figures, columns for a trajectory, a timeline for dates. */
export default function Charts({ figures, pdf, pending = false }: { figures: Figure[]; pdf?: string | null; pending?: boolean }) {
  if (!figures.length) return null;
  const flows = figures.filter((f) => f.type === "flow").slice(0, 1); const plots = figures.filter((f) => f.type !== "flow").slice(0, 3);
  return (<>
    {flows.map((f) => (
      <figure key={f.title} className="chart glass chart-flow">
        <figcaption><b>{f.title}</b><span>How it works{pending ? " · awaiting review" : ""}</span></figcaption>
        <Flow f={f} pdf={pdf} />
        {f.note && <p className="chart-note">{f.note}</p>}
      </figure>))}
    {plots.length > 0 && <div className={`charts n${plots.length}`}>{plots.map((f) => (
      <figure key={f.title} className={`chart glass chart-${f.type}`}>
        <figcaption><b>{f.title}</b>{f.unit && <span>{f.unit}</span>}</figcaption>
        {f.type === "bars" ? <Bars f={f} /> : f.type === "series" ? <Series f={f} /> : <Timeline f={f} />}
        {f.note && <p className="chart-note">{f.note}</p>}
        <details className="chart-data"><summary>Figures and sources{pending ? " · awaiting review" : ""}</summary>
          <table><tbody>{f.items.map((i) => (
            <tr key={i.label + (i.start ?? "")}><th scope="row">{i.label}{i.tag && <em> ({i.tag})</em>}</th><td>{cell(f, i)}</td><td><Cites basis={i.basis} pdf={pdf} /></td></tr>))}</tbody></table>
        </details>
      </figure>))}</div>}
  </>);
}
