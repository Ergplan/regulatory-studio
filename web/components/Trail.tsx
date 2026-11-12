import { fmtDate } from "@/lib/format";
import type { Checked } from "@/lib/data";

interface Step { label: string; note: string; state: "done" | "wait" | "skip" }

/** Where an analysis stands, drawn as the steps it passes through: AI summary, three checks, then the legal reviewer. */
export default function Trail({ checked, draft, approvedAt, reviewer }: { checked?: Checked | null; draft?: boolean; approvedAt?: string | null; reviewer?: string | null }) {
  const n = checked?.reviewers ?? 0;
  const steps: Step[] = [
    { label: "AI summary", note: "every statement tied to a paragraph", state: "done" },
    { label: "Number check", note: "each figure looked up in the text", state: checked?.numbers ? "done" : "skip" },
    { label: "Fact checker", note: "AI reviewer: figures, dates, parties", state: n >= 1 ? "done" : "skip" },
    { label: "Legal reader", note: "second AI reviewer: holding and conditions", state: n >= 2 ? "done" : "skip" },
    { label: "Legal review", note: draft ? "by our legal team: not done yet" : `approved ${fmtDate(approvedAt ?? null)}${reviewer ? ` by ${reviewer}` : ""}`, state: draft ? "wait" : "done" },
  ];
  return (
    <section className="trail" aria-label="How this analysis was checked">
      <ol>{steps.map((s) => (
        <li key={s.label} className={s.state}>
          <span className="tr-mark" aria-hidden="true">{s.state === "done" ? "✓" : s.state === "wait" ? "…" : "–"}</span>
          <b>{s.label}</b><span className="tr-note">{s.state === "skip" ? "not run on this item" : s.note}</span>
        </li>))}</ol>
      <p>{draft ? "The checks before legal review are automatic. What they find goes to the reviewer and is not shown here. Do not rely on this analysis until the last step is done."
        : "The automatic checks ran before the legal review. Only the reviewed text is published."}</p>
    </section>
  );
}

/** The same path, for the About page: how any update travels from a commission's website to this site. */
export function Pipeline() {
  const steps = [
    ["Collect", "New orders, drafts and regulations are downloaded from each commission's website."],
    ["Parse", "Text is split into numbered paragraphs. Tables are kept row by row so a figure stays with its heading."],
    ["Summarise", "An AI writes the summary, impact notes, charts and schematics. Each statement cites a paragraph."],
    ["Check numbers", "Software looks up every figure and date of the summary in the document."],
    ["Two AI reviewers", "A fact checker and a legal reader test the summary separately. Neither sees the other's answer."],
    ["Legal review", "A named reviewer reads the findings, edits and approves. Only then is it published as reviewed."],
  ];
  return <ol className="pipeline">{steps.map(([t, d], i) => <li key={t}><span aria-hidden="true">{i + 1}</span><b>{t}</b><p>{d}</p></li>)}</ol>;
}
