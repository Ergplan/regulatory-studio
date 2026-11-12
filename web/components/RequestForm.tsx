"use client";
import { useEffect, useState } from "react";

const ROLES = ["Industrial or commercial energy buyer", "Captive power user", "Renewable developer", "Storage developer", "Distribution licensee", "Regulatory or legal team", "Other"];
const STATES = ["", "Gujarat", "Karnataka", "Maharashtra", "Rajasthan", "Tamil Nadu", "Uttar Pradesh", "Other state", "Several states"];

/** Request a plant or project impact review. What the reader was looking at travels with the request,
 *  so they do not have to explain it again. With `fromQuery`, the context comes from the page address. */
export default function RequestForm({ about = "", link = "", role = "", ask = "", fromQuery = false }: { about?: string; link?: string; role?: string; ask?: string; fromQuery?: boolean }) {
  const [ctx, setCtx] = useState({ about, link, role, ask });
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    if (!fromQuery) { setCtx({ about, link, role, ask }); return; }
    const q = new URLSearchParams(window.location.search);
    const ref = q.get("ref") ?? "";
    setCtx({ about: (q.get("about") ?? "").slice(0, 300), ask: (q.get("ask") ?? "").slice(0, 120), role: (q.get("as") ?? "").slice(0, 80),
      link: ref.startsWith("/") && !ref.startsWith("//") ? window.location.origin + ref : "" });
  }, [fromQuery, about, link, role, ask]);

  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setState("sending");
    try {
      const res = await fetch("/api/request", { method: "POST", body: new FormData(e.currentTarget) });
      const data = await res.json().catch(() => ({}));
      setState(res.ok ? "done" : "error");
      setMsg(data.message ?? (res.ok ? "Request received." : "Something went wrong. Please try again."));
    } catch { setState("error"); setMsg("Could not reach the site. Please try again."); }
  }
  if (state === "done") return <p className="good request-done" role="status">{msg}</p>;
  return (
    <form className="request" onSubmit={send}>
      {ctx.about && <p className="request-about"><span>About</span> {ctx.about}</p>}
      <input type="hidden" name="draft" value={ctx.about} /><input type="hidden" name="link" value={ctx.link} /><input type="hidden" name="ask" value={ctx.ask} />
      <div className="row2">
        <label>Your name<input name="name" required maxLength={120} autoComplete="name" /></label>
        <label>Work email<input name="email" type="email" required maxLength={200} autoComplete="email" placeholder="you@company.com" /></label>
      </div>
      <div className="row2">
        <label>Organisation<input name="org" maxLength={160} autoComplete="organization" /></label>
        <label>State<select name="state" defaultValue="">{STATES.map((s) => <option key={s} value={s}>{s || "Choose a state"}</option>)}</select></label>
      </div>
      <label className="full">You are<select name="group" key={ctx.role} defaultValue={ROLES.includes(ctx.role) ? ctx.role : ctx.role ? "Other" : ROLES[0]}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></label>
      <label className="full">The decision you are trying to make<textarea name="message" maxLength={2000} rows={4}
        placeholder="For example: we plan 12 MW of captive solar with storage for a plant in Rajasthan and want to know which conditions apply." /></label>
      <input name="company" tabIndex={-1} autoComplete="off" aria-hidden="true" className="sr" />
      <div className="desk-actions"><button type="submit" className="btn" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Request the review"}</button>
        {msg && <span role="status" className={state === "error" ? "bad small" : "good small"}>{msg}</span>}</div>
      <p className="muted small">Your details are emailed to the Regulatory Studio team so they can reply, and are not stored on this site. Bills, contracts or meter data are only asked for later, if they are needed.</p>
    </form>
  );
}
