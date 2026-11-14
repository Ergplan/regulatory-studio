import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Charts from "@/components/Charts";
import { Cites } from "@/components/Impact";
import { draftRow, LibraryRow, orderRow } from "@/components/Library";
import Subscribe from "@/components/Subscribe";
import { consultationById, digests, orderById, type DigestRef } from "@/lib/data";
import { fmtDate } from "@/lib/format";

type Params = { week: string };
export const dynamicParams = false;
export function generateStaticParams(): Params[] { return digests.map((d) => ({ week: d.id.toLowerCase() })); }
const find = (w: string) => digests.find((d) => d.id.toLowerCase() === w);
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const d = find((await params).week);
  return d ? { title: `Weekly digest, ${fmtDate(d.edition ?? d.to)}`, description: d.intro.slice(0, 160), alternates: { canonical: d.path } } : {};
}

/** Where a statement comes from: the commission, a link to the document's page, and the paragraph in its source file. */
function Source({ r }: { r: Pick<DigestRef, "href" | "code" | "pid" | "src"> }) {
  return <span className="d-src"><Link href={r.href}>{r.code.toUpperCase()}</Link><Cites basis={[r.pid]} pdf={r.src} /></span>;
}

export default async function Week({ params }: { params: Promise<Params> }) {
  const d = find((await params).week);
  if (!d) notFound();
  const orders = d.items.map((id) => orderById.get(id)).filter((o) => !!o);
  const drafts = d.items.map((id) => consultationById.get(id)).filter((c) => !!c);
  const points = d.key_points ?? [], numbers = d.numbers ?? [], charts = d.charts ?? [], watch = d.watch ?? [];
  return (
    <article className="digest">
      <p className="eyebrow">Weekly digest · edition of {fmtDate(d.edition ?? d.to)}{d.draft && <span className="pend">awaiting legal review</span>}</p>
      <h1>What changed in power regulation this week</h1>
      <p className="lede d-lead">{d.intro}</p>
      <p className="d-count">{orders.length} order{orders.length === 1 ? "" : "s"} · {drafts.length} draft regulation{drafts.length === 1 ? "" : "s"}</p>

      {points.length > 0 && <section className="glass d-points" aria-labelledby="kp">
        <h2 id="kp" className="label">Key points</h2>
        <ul>{points.map((p) => <li key={p.text}><p>{p.text}</p><p className="d-srcs">{p.basis.map((b) => <Source key={b.doc + b.pid} r={b} />)}</p></li>)}</ul>
      </section>}

      {numbers.length > 0 && <section aria-labelledby="nums" className="d-block">
        <h2 id="nums" className="label">Numbers to know</h2>
        <ul className="d-nums">{numbers.map((n) => <li key={n.value + n.doc} className="glass"><b>{n.value}</b><span>{n.label}</span><Source r={n} /></li>)}</ul>
      </section>}

      {charts.length > 0 && <section aria-labelledby="ch" className="d-block">
        <h2 id="ch" className="label">Across the documents</h2>
        <Charts figures={charts} pending={d.draft} />
      </section>}

      {watch.length > 0 && <section aria-labelledby="wt" className="glass d-watch">
        <h2 id="wt" className="label">Dates to watch</h2>
        <ol>{watch.map((w) => <li key={w.date + w.text}><time dateTime={w.date}>{fmtDate(w.date)}</time><span>{w.text}</span>{w.href && w.code && w.pid && <Source r={{ href: w.href, code: w.code, pid: w.pid, src: w.src }} />}</li>)}</ol>
      </section>}

      {orders.length > 0 && <section aria-labelledby="or" className="d-block">
        <h2 id="or" className="label">Orders in this edition</h2>
        <ul className="lib">{orders.map((o) => <LibraryRow key={o.id} r={orderRow(o)} />)}</ul>
      </section>}
      {drafts.length > 0 && <section aria-labelledby="dr" className="d-block">
        <h2 id="dr" className="label">Draft regulations in this edition</h2>
        <ul className="lib">{drafts.map((c) => <LibraryRow key={c.id} r={draftRow(c)} />)}</ul>
      </section>}

      {d.draft ? <p className="note"><b>Analysis awaiting legal review.</b> This edition was prepared with AI from documents that have not been checked by the legal team yet. Every point links to the paragraph it rests on.</p>
        : <p className="note">Reviewed and approved by the Regulatory Studio legal team on {fmtDate(d.approved_at)}.</p>}
      <div className="glass digest-signup"><Subscribe /></div>
    </article>);
}
