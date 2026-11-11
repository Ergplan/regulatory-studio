import type { Metadata } from "next";
import Link from "next/link";
import { citingOrders, clausesOf, commissionName, regulations } from "@/lib/data";

export const metadata: Metadata = { title: "Regulation registry", alternates: { canonical: "/regulations" } };

export default function Regulations() {
  const byComm = new Map<string, typeof regulations>();
  for (const r of regulations) byComm.set(r.commission, [...(byComm.get(r.commission) ?? []), r]);
  return (
    <>
      <h1>Regulation registry</h1>
      <p className="muted lede">Regulations split into clauses, each with a permanent address, showing every reviewed order that applied, interpreted or relaxed it.</p>
      {[...byComm].map(([c, regs]) => (
        <section key={c}><h2>{commissionName(c)}</h2>
          <table className="list"><thead><tr><th>Regulation</th><th>Clauses</th><th>Orders citing it</th></tr></thead>
            <tbody>{regs.map((r) => {
              const cl = clausesOf(r.id);
              const n = new Set(cl.flatMap((x) => citingOrders("clause", x.id).map((y) => y.order.id))).size;
              return <tr key={r.id}><td><Link href={r.path}>{r.title}</Link></td><td>{cl.length}</td><td>{n}</td></tr>;
            })}</tbody></table></section>
      ))}
      {!regulations.length && <div className="card empty">The registry is being built.</div>}
    </>
  );
}
