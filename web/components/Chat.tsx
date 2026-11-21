"use client";
// The chat box in the corner: a visitor asks a question or leaves a note, and it is saved for the jouleWise team
// (POST /api/chat). Common questions get an automatic answer, marked as automatic. There is no language model
// here and nothing pretends to be a person. The conversation is kept in this tab so a reload does not lose it.
import { useEffect, useRef, useState } from "react";
import { CHAT, type Topic } from "@/lib/chatData";
import { SALES_EMAIL, SALES_PHONE, SALES_TEL } from "@/lib/contact";

type Line = { by: "you" | "helper"; text: string; at: number };
type State = { id: string; started: number; lines: Line[]; contact: { name?: string; company?: string; reach?: string }; asked: boolean };
const KEY = "rs-chat";
const hex = (n: number) => [...crypto.getRandomValues(new Uint8Array(n))].map((b) => b.toString(16).padStart(2, "0")).join("");
const fresh = (): State => ({ id: hex(16), started: Date.now(), lines: [], contact: {}, asked: false });

/** A suggested question always has its answer; a typed one gets an automatic answer only when it clearly matches. */
function topicFor(text: string, viaChip: boolean): Topic | null {
  if (viaChip) return CHAT.topics.find((t) => t.chip === text) ?? null;
  const t = ` ${text.toLowerCase()} `;
  let best: Topic | null = null, score = 0;
  for (const topic of CHAT.topics) { const s = topic.keys.reduce((n, k) => n + (t.includes(k) ? 1 : 0), 0); if (s > score) { best = topic; score = s; } }
  return score >= 2 || (score === 1 && text.length <= 40) ? best : null;
}

export default function Chat() {
  const [open, setOpen] = useState(false);
  const [S, setS] = useState<State | null>(null);
  const [status, setStatus] = useState<{ text: string; bad?: boolean }>({ text: "" });
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const trap = useRef<HTMLInputElement>(null), log = useRef<HTMLDivElement>(null), box = useRef<HTMLTextAreaElement>(null), opener = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let s: State | null = null;
    try { s = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch { s = null; }
    setS(s && s.id && Array.isArray(s.lines) ? s : fresh());
  }, []);
  useEffect(() => { if (S) { try { sessionStorage.setItem(KEY, JSON.stringify(S)); } catch { /* this page view only */ } } }, [S]);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [S?.lines.length, open]);
  useEffect(() => { if (open) box.current?.focus({ preventScroll: true }); }, [open]);

  async function save(next: State): Promise<boolean> {
    setStatus({ text: "Saving…" });
    try {
      const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        id: next.id, started: next.started, page: window.location.pathname, ref: document.referrer.slice(0, 300), contact: next.contact,
        website: trap.current?.value ?? "", messages: next.lines.filter((l) => l.by === "you").map((l) => ({ at: l.at, text: l.text })) }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(j.error || String(r.status));
      setStatus({ text: "Saved for the jouleWise team." });
      return true;
    } catch {
      setStatus({ text: `Not saved: the message did not reach us. Send again, write to ${SALES_EMAIL} or call ${SALES_PHONE}.`, bad: true });
      return false;
    }
  }

  async function send(raw: string, viaChip: boolean) {
    const said = raw.trim();
    if (!said || busy || !S) return;
    setBusy(true);
    let next: State = { ...S, lines: [...S.lines, { by: "you", text: said, at: Date.now() }] };
    setS(next); setText("");
    const ok = await save(next);
    const topic = viaChip || said.length <= 90 ? topicFor(said, viaChip) : null;
    const add = (t: string) => { next = { ...next, lines: [...next.lines, { by: "helper", text: t, at: Date.now() }] }; };
    const has = Boolean(next.contact.reach);
    if (topic) add(topic.a);
    if (ok && !topic) add(has ? CHAT.noted : CHAT.notedAsk);
    else if (ok && topic && !has && !next.asked) add(CHAT.ask);
    if (ok && !has) next = { ...next, asked: true };
    setS(next); setBusy(false);
  }

  async function leaveDetails(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!S) return;
    const f = new FormData(e.currentTarget);
    const contact = { name: String(f.get("name") || "").trim(), company: String(f.get("company") || "").trim(), reach: String(f.get("reach") || "").trim() };
    if (!contact.reach) return;
    const next = { ...S, contact };
    if (await save(next)) setS({ ...next, lines: [...next.lines, { by: "helper", text: CHAT.thanks, at: Date.now() }] });
    else setS(next);
  }

  const close = () => { setOpen(false); setTimeout(() => opener.current?.focus({ preventScroll: true }), 0); };
  const showWho = Boolean(S && S.asked && !S.contact.reach);
  return (<>
    <button ref={opener} type="button" className="chat-open" aria-expanded={open} aria-controls="chat" hidden={open} onClick={() => setOpen(true)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z" /></svg><span>Message the jouleWise team</span>
    </button>
    <div className="chat" id="chat" role="dialog" aria-label="Message the jouleWise team" hidden={!open} onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
      <header><div><b>Message the jouleWise team</b><small>Saved for the team. Quick answers are automatic.</small></div>
        <button type="button" className="chat-x" aria-label="Close the chat" onClick={close}>×</button></header>
      <div className="chat-log" ref={log} aria-live="polite">
        <div className="chat-line helper"><small>Automatic reply</small><p>{CHAT.hello}</p></div>
        {S?.lines.map((l, i) => <div key={i} className={`chat-line ${l.by}`}>{l.by === "helper" && <small>Automatic reply</small>}<p>{l.text}</p></div>)}
      </div>
      {!S?.lines.length && <div className="chat-chips" aria-label="Common questions">
        {CHAT.topics.filter((t) => t.chip).map((t) => <button key={t.chip} type="button" onClick={() => send(t.chip!, true)}>{t.chip}</button>)}</div>}
      {showWho && <form className="chat-who" onSubmit={leaveDetails}>
        <input name="name" placeholder="Your name" autoComplete="name" aria-label="Your name" maxLength={160} />
        <input name="company" placeholder="Company" autoComplete="organization" aria-label="Company" maxLength={160} />
        <input className="wide" name="reach" placeholder="Phone or email, for the reply" aria-label="Phone or email" maxLength={160} required />
        <button className="btn small wide" type="submit">Send my details</button>
      </form>}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(text, false); }}>
        <input ref={trap} className="hp" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" />
        <textarea ref={box} rows={2} maxLength={2000} value={text} placeholder="Write a question or a note" aria-label="Your message"
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text, false); } }} />
        <button type="submit" className="btn small" disabled={busy || !text.trim()}>Send</button>
      </form>
      <p className={`chat-status${status.bad ? " bad" : ""}`} role="status">{status.text}</p>
      <p className="chat-foot">Or call <a href={`tel:${SALES_TEL}`}>{SALES_PHONE}</a> · <a href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a><br />
        What you write here is kept so the team can reply: <a href="/privacy">privacy</a>.</p>
    </div>
  </>);
}
