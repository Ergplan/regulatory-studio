import type { Metadata } from "next";
import Link from "next/link";
import { orders, orderLabel, topicName } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export const metadata: Metadata = { title: "All reviewed orders", alternates: { canonical: "/orders" } };

export default function Orders() {
  return (
    <>
      <h1>Reviewed orders</h1>
      <p className="muted">{orders.length} orders, newest first. Each has a legally reviewed summary and a map of the provisions it relies on.</p>
      <table className="list">
        <thead><tr><th>Date</th><th>Commission</th><th>Order</th><th>Topics</th></tr></thead>
        <tbody>{orders.map((o) => (
          <tr key={o.id}><td>{fmtDate(o.date)}</td><td><Link href={`/commissions/${o.commission}`}>{o.commission.toUpperCase()}</Link></td>
            <td><Link href={o.path}>{o.title ?? orderLabel(o)}</Link>{o.sample && <span className="tag bad"> Sample</span>}</td>
            <td>{o.topics.map((t) => topicName(t)).join(", ")}</td></tr>
        ))}</tbody>
      </table>
    </>
  );
}
