import Link from "next/link";
import type { Impact } from "@/lib/data";

export const REVIEW_SCOPE = [
  "Does this apply to your plant, contract or project?",
  "Which cost, eligibility or operating assumptions need checking?",
  "What documents or data are needed to be sure?",
  "Which options are worth evaluating next?",
];

/** The next step that fits what is being read. Order matters: the first match wins. */
export function askFor({ consultation = false, closed = false, impact, text = "" }: { consultation?: boolean; closed?: boolean; impact?: Impact | null; text?: string }): string {
  const t = text.toLowerCase();
  const hit = (g: string) => !!impact?.stakeholders[g];
  if (consultation && !closed) return "Request support on this consultation";
  if (hit("captive") || /captive|contract demand/.test(t)) return "Review my captive arrangement";
  if (/deviation|scheduling|forecast/.test(t)) return "Review my operating assumptions";
  if (hit("storage") && !hit("ci_consumers") || /\bbess\b|battery|storage/.test(t)) return "Discuss my BESS project";
  if (hit("ci_consumers") || /open access|tariff|surcharge|wheeling|banking/.test(t)) return "Assess my procurement assumptions";
  return "Discuss my project";
}

export function discussHref(ask: string, about: string, ref: string, as?: string): string {
  const q = new URLSearchParams({ ask, about: about.slice(0, 200), ref });
  if (as) q.set("as", as);
  return `/discuss?${q.toString()}`;
}

/** A defined offer beside the moment of relevance: a plant or project impact review, with what it covers. */
export default function ProjectCta({ ask, about, path, as, compact = false, lead }: { ask: string; about: string; path: string; as?: string; compact?: boolean; lead?: string }) {
  return (
    <div className={`glass project-cta${compact ? " compact" : ""}`}>
      <p className="eyebrow">Plant or project impact review</p>
      <p className="cta-lead">{lead ?? "Ask our team what this means for your own plant or project. A review answers:"}</p>
      {!compact && <ul>{REVIEW_SCOPE.map((s) => <li key={s}>{s}</li>)}</ul>}
      <Link href={discussHref(ask, about, path, as)} className="btn">{ask}</Link>
    </div>
  );
}
