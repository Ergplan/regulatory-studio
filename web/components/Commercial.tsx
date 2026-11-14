import { Cites } from "@/components/Impact";
import type { Commercial as CommercialT } from "@/lib/data";

const num = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 2 });

/** A worked example of what a decision or tender means in money. Beta: inputs are cited or openly assumed,
 *  the arithmetic is done by software, and the jouleWise commercial team reviews it. */
export default function Commercial({ c, pdf }: { c: CommercialT; pdf?: string | null }) {
  // Steps that share a unit can be compared side by side (e.g. cost at the tariff against cost at the exchange price).
  const byUnit = new Map<string, typeof c.steps>();
  c.steps.forEach((s) => byUnit.set(s.unit, [...(byUnit.get(s.unit) ?? []), s]));
  const compare = [...byUnit.values()].find((g) => g.length >= 2 && g.every((s) => s.value > 0));
  const max = compare ? Math.max(...compare.map((s) => s.value)) : 0;
  return (
    <section className="commercial card" aria-labelledby="commercial-h">
      <p className="eyebrow">Commercial illustration <span className="beta">Beta</span>{c.draft && <span className="beta warn">Not yet reviewed</span>}</p>
      <h2 id="commercial-h">{c.title}</h2>
      <p className="muted">{c.question}</p>
      <div className="calc">
        <ol className="calc-inputs">
          {c.inputs.map((i) => (
            <li key={i.id}>
              <span className="c-label">{i.label}</span>
              <b className="c-val">{num(i.value)} <small>{i.unit}</small></b>
              <span className="c-src">{i.basis?.length ? <Cites basis={i.basis} pdf={pdf} /> : <><span className="assume">Assumption</span> {i.assumption?.replace(/^Assumption for the illustration:\s*/i, "")}</>}</span>
            </li>))}
        </ol>
        <ol className="calc-steps">
          {c.steps.map((s, n) => (
            <li key={s.id} className={n === c.steps.length - 1 ? "last" : ""}>
              <span className="c-label">{s.label}</span>
              <b className="c-val">{s.shown} <small>{s.unit}</small></b>
            </li>))}
        </ol>
      </div>
      {compare && (
        <div className="calc-bars" role="img" aria-label={compare.map((s) => `${s.label}: ${s.shown} ${s.unit}`).join("; ")}>
          {compare.map((s) => (
            <div key={s.id} className="cb-row"><span>{s.label}</span>
              <span className="cb-track"><span className="cb-bar" style={{ width: `${Math.max(2, (s.value / max) * 100)}%` }} /></span>
              <b>{s.shown} <small>{s.unit}</small></b></div>))}
        </div>)}
      <p className="takeaway">{c.takeaway}</p>
      {c.caveats.length > 0 && <ul className="caveats">{c.caveats.map((x) => <li key={x}>{x}</li>)}</ul>}
      <p className="note">A simple worked example for discussion, not advice. Figures marked with a paragraph come from the document; the rest are stated assumptions. The arithmetic is done by software from the inputs shown.
        {c.approved_by ? ` Reviewed by the jouleWise commercial team (${c.approved_by}).` : " Not yet reviewed by the jouleWise commercial team."}</p>
    </section>
  );
}
