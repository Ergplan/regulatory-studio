import CoverScroll from "@/components/CoverScroll";
import IndiaMap, { GEO, LeaderLines, VB, geoCss } from "@/components/IndiaMap";
import { commissionName } from "@/lib/data";

export interface StageItem { code: string; href: string; note: string; idle?: boolean }

/** The dotted India map with a card per commission around it. Sits beside (on phones, above) chapters marked
 *  data-chapter="<code>"; the commission in view lights up its state. Must be the first child of a .cover element. */
export default function Stage({ items }: { items: StageItem[] }) {
  const pct = (x: number, y: number) => ({ left: `${((x - VB.x) / VB.w) * 100}%`, top: `${((y - VB.y) / VB.h) * 100}%` });
  return (
    <div className="stage" aria-label="Commissions covered">
      <style dangerouslySetInnerHTML={{ __html: geoCss() }} />
      <CoverScroll />
      <div className="pin">
      <div className="orbit">
        <LeaderLines />
        <div className="india-box"><IndiaMap /></div>
        <div className="ccards">
          {items.filter((c) => GEO[c.code]).map((c) => (
            <a key={c.code} href={c.href} className={`ccard cc-${c.code}${c.idle ? " idle" : ""}`} style={pct(...GEO[c.code].card)}>
              <b>{c.code.toUpperCase()}</b><span>{GEO[c.code].place}</span><em>{c.note}</em>
            </a>))}
        </div>
      </div>
      <p className="now" aria-hidden="true">{items.map((c) => <span key={c.code} className={`now-${c.code}`}><i />{commissionName(c.code)}</span>)}</p>
      </div>
    </div>
  );
}
