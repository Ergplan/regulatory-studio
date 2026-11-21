"use client";
import { useEffect, useState } from "react";
import { SALES_EMAIL, SALES_PHONE } from "@/lib/contact";

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

  const [mail, setMail] = useState("");
  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setState("sending");
    const f = new FormData(e.currentTarget);
    // If the site cannot take the request, the reader can still send it from their own mail, already filled in.
    const body = [["Name", f.get("name")], ["Work email", f.get("email")], ["Organisation", f.get("org")], ["State", f.get("state")],
      ["You are", f.get("group")], ["About", f.get("draft")], ["Page", f.get("link")], ["The decision", f.get("message")]]
      .filter(([, v]) => String(v ?? "").trim()).map(([k, v]) => `${k}: ${v}`).join("\n");
    setMail(`mailto:${SALES_EMAIL}?subject=${encodeURIComponent("Regulatory Studio: project review request")}&body=${encodeURIComponent(body)}`);
    try {
      const res = await fetch("/api/request", { method: "POST", body: f });
      const data = await res.json().catch(() => ({}));
      setState(res.ok ? "done" : "error");
      setMsg(data.message ?? (res.ok ? "Request received." : "Something went wrong."));
    } catch { setState("error"); setMsg("Could not reach the site."); }
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
      {state === "error" && mail && <p className="small"><a className="btn ghost small" href={mail}>Send it from your own mail instead</a> or call {SALES_PHONE}.</p>}
      <p className="muted small">Your request goes to the jouleWise team at <a href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a> and is kept so they can reply. Bills, contracts or meter data are only asked for later, if they are needed. <a href="/privacy">Privacy</a>.</p>
    </form>
  );
}
