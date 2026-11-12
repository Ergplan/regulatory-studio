"use client";
import { useEffect, useState } from "react";
import GroupIcon from "@/components/GroupIcon";
import type { CommentDraft, GroupKey } from "@/lib/data";

export interface DeskDraft {
  id: string; title: string; commission: string; commissionName: string; path: string; url: string; deadline: string | null; deadlineLabel: string;
  summary: string; proposes: string[]; effect: Partial<Record<string, string>>; comments: Record<string, CommentDraft>;
}
type Group = [GroupKey, string, string];
const cite = (b: string[]) => b.map((p) => `p.${p.slice(1).split(".")[0]} ¶${p.split(".")[1]}`).join(", ");

/** A short brief the reader can paste into their own AI assistant. It carries the cues and where to read the draft; no letter. */
function agentBrief(d: DeskDraft, long: string, c?: CommentDraft): string {
  return [`I am preparing comments on a draft electricity regulation, as: ${long}.`, ``,
    `Draft: ${d.title}`, `Commission: ${d.commissionName}`, `Status: ${d.deadlineLabel}`, `Summary and analysis (plain text): ${d.url}.md`, ``,
    `Summary: ${d.summary}`, ``,
    ...(c ? [`Points to consider (cues from Regulatory Studio; check each against the draft):`,
      ...c.points.flatMap((p, i) => [`${i + 1}. ${p.clause} (${cite(p.basis)})`, `   Why it matters: ${p.comment}`, ...(p.suggestion ? [`   One possible ask: ${p.suggestion}`] : [])]), ``]
      : d.proposes.length ? [`Main proposed changes:`, ...d.proposes.map((p, i) => `${i + 1}. ${p}`), ``] : []),
    `Help me work out my own position on each point, ask me for the facts you need about my organisation, and do not invent any.`].join("\n");
}

export default function StudioDesk({ drafts, groups, contact }: { drafts: DeskDraft[]; groups: Group[]; contact: string | null }) {
  const [g, setG] = useState<string>("");
  const [id, setId] = useState<string>("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  const d = drafts.find((x) => x.id === id);
  const long = groups.find(([k]) => k === g)?.[2] ?? "";

  useEffect(() => {  // deep link from a draft's page, and the reader's last choice of group
    const q = new URLSearchParams(window.location.search);
    const want = q.get("draft"); const as = q.get("as");
    const hit = want ? drafts.find((x) => x.id.startsWith(want)) : undefined;
    if (hit) setId(hit.id);
    let last = ""; try { last = localStorage.getItem("rs-studio-as") ?? ""; } catch { /* storage unavailable */ }
    const pick = as || last;
    if (pick && groups.some(([k]) => k === pick)) setG(pick);
  }, [drafts, groups]);
  useEffect(() => { setNote(""); setState("idle"); setMsg(""); }, [g, id]);

  const cues = d && g ? d.comments[g] : undefined;
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
  const mail = d && contact ? `mailto:${contact}?subject=${encodeURIComponent(`Analysis request: ${d.title}`)}&body=${encodeURIComponent(`Draft: ${d.title}\n${d.url}\nWriting as: ${long}\n\nWhat we need:\n`)}` : null;

  return (
    <div className="desk">
      <section className="glass step">
        <h2 className="label"><span>1</span> Who are you?</h2>
        <div className="personas" role="radiogroup" aria-label="Who are you?">{groups.map(([k, , name]) => (
          <button key={k} type="button" role="radio" aria-checked={g === k} className={`persona${g === k ? " on" : ""}`}
            onClick={() => { setG(k); try { localStorage.setItem("rs-studio-as", k); } catch { /* storage unavailable */ } }}><GroupIcon g={k} size={22} /><span>{name}</span></button>))}</div>
      </section>

      <section className="glass step">
        <h2 className="label"><span>2</span> Which draft?</h2>
        {drafts.length === 0 ? <p className="muted">No draft regulation is open for comment right now.</p> : (
          <div className="draft-list" role="radiogroup" aria-label="Which draft?">{drafts.map((x) => {
            const ready = g ? !!x.comments[g] : Object.keys(x.comments).length > 0;
            return (
              <button key={x.id} type="button" role="radio" aria-checked={id === x.id} className={`draft-pick${id === x.id ? " on" : ""}`} onClick={() => setId(x.id)}>
                <span className="meta">{x.commission.toUpperCase()} · {x.deadlineLabel}</span>
                <b>{x.title}</b>
                <em className={ready ? "ready" : ""}>{ready ? (g ? "Cues ready for you" : "Cues ready") : "Summary only"}</em>
              </button>);
          })}</div>)}
      </section>

      <section className="glass step" aria-live="polite">
        <h2 className="label"><span>3</span> Cues for your comments</h2>
        {!d || !g ? <p className="muted">Choose who you are and a draft. The points worth commenting on appear here.</p> : (<>
          <p className="small">{cues
            ? <>Points in the draft that matter to: {long}. Each comes with its paragraph.{cues.draft ? <> <b className="warn">AI draft, not yet reviewed by the legal team.</b></> : <> Reviewed by the Regulatory Studio legal team.</>} These are cues, not a submission: your comments should be your own.</>
            : <>No cues are prepared for this group on this draft yet. The main proposed changes are listed so you can start; <a href={d.path}>read the summary</a>.</>}</p>
          {d.effect[g] && <p className="cue-effect"><b>How it touches you.</b> {d.effect[g]}</p>}
          {cues ? (
            <ol className="cues">{cues.points.map((p, i) => (
              <li key={i}>
                <h3>{p.clause}</h3>
                <dl><dt>Why it matters</dt><dd>{p.comment}</dd>
                  {p.suggestion && (<><dt>You could ask for</dt><dd>{p.suggestion}</dd></>)}</dl>
                <p className="cue-ref">Draft reference: {cite(p.basis)} · <a href={d.path}>open the draft&apos;s page</a></p>
              </li>))}</ol>
          ) : d.proposes.length > 0 && (
            <ol className="cues">{d.proposes.map((p, i) => <li key={i}><h3>{p}</h3><dl><dt>Ask yourself</dt><dd>What does this change for you, and what would you want the Commission to do differently?</dd></dl></li>)}</ol>)}

          <div className="next">
            <h3>Want a full analysis?</h3>
            <p className="small">We do not draft submissions on this page. For a full analysis of this draft for your organisation, leave a request with the team{mail ? " or mail us" : ""}. You can also take these cues to your own AI agent.</p>
            <div className="desk-actions">
              {mail && <a className="btn" href={mail}>Mail us</a>}
              <button type="button" className="btn ghost" onClick={async () => { try { await navigator.clipboard.writeText(agentBrief(d, long, cues)); setNote("Brief copied. Paste it into your AI agent."); } catch { setNote("Copy failed on this browser."); } }}>Copy brief for your agent</button>
              <span className="muted small" role="status">{note}</span>
            </div>
            {state === "done" ? <p className="good" role="status">{msg}</p> : (
              <form className="request" onSubmit={send}>
                <h4>Leave a request</h4>
                <input type="hidden" name="draft" value={d.title} /><input type="hidden" name="group" value={long} /><input type="hidden" name="link" value={d.url} />
                <div className="row2">
                  <label>Your name<input name="name" required maxLength={120} autoComplete="name" /></label>
                  <label>Work email<input name="email" type="email" required maxLength={200} autoComplete="email" placeholder="you@company.com" /></label>
                </div>
                <label className="full">Organisation<input name="org" maxLength={160} autoComplete="organization" /></label>
                <label className="full">What do you need?<textarea name="message" maxLength={2000} rows={4} placeholder="For example: effect on our 40 MW open access contracts, and a draft submission before the deadline." /></label>
                <input name="company" tabIndex={-1} autoComplete="off" aria-hidden="true" className="sr" />
                <div className="desk-actions"><button type="submit" className="btn" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Send request"}</button>
                  {msg && <span role="status" className={state === "error" ? "bad small" : "good small"}>{msg}</span>}</div>
                <p className="muted small">Your details are emailed to the Regulatory Studio team to reply to you, and are not stored on this site.</p>
              </form>)}
          </div>
        </>)}
      </section>
    </div>
  );
}
