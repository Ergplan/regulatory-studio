import Link from "next/link";
import GroupIcon from "@/components/GroupIcon";
import { Direction } from "@/components/Impact";
import { GROUPS, type Impact, type Rating } from "@/lib/data";

export interface Block {
  id: string; href: string; kind: "Draft" | "Order"; tab: string; title: string; summary: string; date: string;
  impact?: Impact | null; draftable: boolean; unreviewed: boolean; rating?: Rating; closed?: boolean;
}

/** "High impact" is the review team's rating, never the model's. */
export function HighBadge() {
  return <span className="high" title="Rated high impact by the Regulatory Studio team during review"><svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1l1.5 3.4 3.5.4-2.6 2.4.7 3.6L6 9l-3.1 1.8.7-3.6L1 4.8l3.5-.4z" fill="currentColor" /></svg>High impact</span>;
}

/** Icons for the groups a document affects, each with its direction. */
export function ImpactAreas({ impact }: { impact?: Impact | null }) {
  const hit = impact ? GROUPS.filter(([g]) => impact.stakeholders[g]) : [];
  if (!hit.length) return <p className="areas-none">Impact areas not assessed yet</p>;
  return (
    <ul className="who-chips" aria-label="Impact areas">{hit.map(([g, short]) => {
      const c = impact!.stakeholders[g]!;
      return <li key={g} className={`e-${c.effect}`} title={c.comment}><GroupIcon g={g} size={16} /> {short} <Direction effect={c.effect} /></li>;
    })}</ul>
  );
}

/** One order or draft as a folder-style block: what it is, what it changes, whom it touches. */
export default function AnalysisBlock(b: Block & { showAreasEmpty?: boolean }) {
  return (
    <article className={`folder rise${b.kind === "Draft" && !b.closed ? " is-draft" : ""}${b.rating === "high" ? " is-high" : ""}`} id={`u-${b.id.slice(0, 10)}`}>
      <span className="tab">{b.tab}{b.unreviewed ? " · analysis awaiting review" : ""}</span>
      {b.rating === "high" && <HighBadge />}
      <h3><Link href={b.href}>{b.impact?.headline || b.title}</Link></h3>
      {b.impact?.headline && <p className="formal">{b.title}</p>}
      <p className="folder-sum">{b.impact?.market_note || b.summary}</p>
      {(b.impact || b.showAreasEmpty) && <ImpactAreas impact={b.impact} />}
      <p className="folder-links"><Link href={b.impact ? `${b.href}#impact` : b.href}>{b.impact ? "Read the analysis" : "Read the summary"} →</Link>
        {b.draftable && <Link href={`/studio?draft=${b.id.slice(0, 10)}`}>Cues for your comments →</Link>}</p>
    </article>
  );
}
