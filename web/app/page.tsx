import Link from "next/link";
import OrderCard from "@/components/OrderCard";
import Subscribe from "@/components/Subscribe";
import ConsultationCard from "@/components/ConsultationCard";
import { consultations, digests, isOpen, orderById, orders, site, regulations } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export default function Home() {
  const latest = digests[0];
  const recent = orders.slice(0, 6);
  return (
    <>
      <h1>Power sector regulatory orders, traced to the rules behind them</h1>
      <p className="lede muted">Every week we read new orders from CERC, APTEL and state electricity commissions,
        summarise the ones that matter for open access and tariffs, and map each to the regulations, Act sections and
        earlier decisions it rests on. Every summary is checked by our legal team before it is published.</p>
      <div className="two">
        <section>
          {latest ? (
            <>
              <h2>This week: <Link href={latest.path}>{fmtDate(latest.from)} to {fmtDate(latest.to)}</Link></h2>
              <p>{latest.intro}</p>
              <div className="grid">{latest.items.map((id) => orderById.get(id)).filter(Boolean).map((o) => <OrderCard key={o!.id} o={o!} />)}</div>
            </>
          ) : (
            <>
              <h2>Latest orders</h2>
              {recent.length ? <div className="grid">{recent.map((o) => <OrderCard key={o.id} o={o} />)}</div>
                : <div className="card empty">The first weekly digest is being prepared.</div>}
            </>
          )}
        </section>
        <aside>
          <h2>Get the weekly digest</h2>
          <div className="card"><Subscribe /></div>
          {consultations.some(isOpen) && (<>
            <h2>Open for comment</h2>
            {consultations.filter(isOpen).sort((a, b) => (a.comment_deadline ?? "9").localeCompare(b.comment_deadline ?? "9"))
              .slice(0, 4).map((c) => <ConsultationCard key={c.id} c={c} />)}
            <p className="small"><Link href="/consultations">All draft regulations and consultations</Link></p>
          </>)}
          <h2>Coverage</h2>
          <ul>{Object.entries(site.commissions).map(([k, v]) => <li key={k}><Link href={`/commissions/${k}`}>{v}</Link></li>)}</ul>
          <p className="muted small">{orders.length} {site.preview ? "draft" : "reviewed"} orders · {regulations.length} regulations in the registry</p>
        </aside>
      </div>
    </>
  );
}
