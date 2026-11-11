import type { Metadata } from "next";
import Link from "next/link";
import { digests } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = { title: "Weekly digests", alternates: { canonical: "/digest" } };
export default function Digests() {
  return (<><h1>Weekly digests</h1>
    {digests.length ? <ul className="links-list">{digests.map((d) => <li key={d.id}><Link href={d.path}>{fmtDate(d.from)} to {fmtDate(d.to)}</Link>
      <span className="muted"> · {d.items.length} orders</span><div>{d.intro}</div></li>)}</ul> : <div className="card empty">The first digest is being prepared.</div>}</>);
}
