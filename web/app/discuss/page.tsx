import type { Metadata } from "next";
import { REVIEW_SCOPE } from "@/components/ProjectCta";
import RequestForm from "@/components/RequestForm";
import { SALES_EMAIL, SALES_PHONE, SALES_TEL } from "@/lib/contact";

export const metadata: Metadata = {
  title: "Discuss my project",
  description: "Request a plant or project impact review: whether a regulatory change applies to you, which assumptions to check, what data is needed, and which options to evaluate next.",
  alternates: { canonical: "/discuss" },
};

export default function Discuss() {
  return (
    <div className="two discuss">
      <section>
        <p className="eyebrow">Plant or project impact review</p>
        <h1 className="hero">Discuss my project.</h1>
        <p className="lede">Tell us the decision you are trying to make. We look at the rules that bear on it and come back with a short review.</p>
        <h2>What the review answers</h2>
        <ol className="scope">{REVIEW_SCOPE.map((s) => <li key={s}>{s}</li>)}</ol>
        <p className="muted">What our team adds to the published analysis: an assessment of whether it applies to you, assumptions checked against
          your facts, and responsibility for the advice given. Regulatory Studio is a joint venture of jouleWise and Urja Praxis.</p>
        <p>Prefer email? Write to <a href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>, call <a href={`tel:${SALES_TEL}`}>{SALES_PHONE}</a>, or use the chat in the corner.</p>
      </section>
      <aside><div className="glass"><h2 className="label">Request a review</h2><RequestForm fromQuery /></div></aside>
    </div>
  );
}
