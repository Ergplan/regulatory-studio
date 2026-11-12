"use client";
import { useEffect, useMemo, useState } from "react";
import GroupIcon from "@/components/GroupIcon";
import type { CommentDraft, GroupKey } from "@/lib/data";

export interface DeskDraft {
  id: string; title: string; commission: string; commissionName: string; path: string; deadline: string | null; deadlineLabel: string;
  summary: string; proposes: string[]; effect: Partial<Record<string, string>>; comments: Record<string, CommentDraft>;
}
type Group = [GroupKey, string, string];
const VOICE: Record<string, string> = {
  discoms: "a distribution licensee", ci_consumers: "a commercial and industrial consumer buying through open access",
  captive: "a consumer with a captive generating plant", re_developers: "a renewable energy developer",
  storage: "an energy storage developer", conventional: "a generating company", transmission: "a transmission licensee", traders: "an electricity trader",
};
const cite = (b: string[]) => b.map((p) => `p.${p.slice(1).split(".")[0]} ¶${p.split(".")[1]}`).join(", ");

function letter(d: DeskDraft, g: string, org: string, who: string): string {
  const c = d.comments[g];
  const head = [`To`, `The Secretary,`, d.commissionName, ``, `Subject: Comments on the ${d.title}`, ``,
    `From: ${org || "[Organisation name]"}, ${VOICE[g]}`, `Date: ${new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}`, ``, `Sir/Madam,`, ``];
  const sign = [``, `Yours faithfully,`, who || "[Name, designation]", org || "[Organisation name]", ``];
  if (c) return [...head, c.position, ``,
    ...c.points.flatMap((p, i) => [`${i + 1}. ${p.clause}`, p.comment, ...(p.suggestion ? [`Requested change: ${p.suggestion}`] : []), `(Draft reference: ${cite(p.basis)})`, ``]),
    c.closing, ...sign].join("\n");
  return [...head, `We write as ${VOICE[g]} on the above draft. [State your overall position in two or three sentences.]`, ``,
    ...(d.effect[g] ? [`How the draft affects us: ${d.effect[g]}`, ``] : []),
    ...(d.proposes.length ? d.proposes : ["[Provision]"]).flatMap((p, i) => [`${i + 1}. ${p}`, `[Your comment: what this changes for you, and why.]`, `Requested change: [the change or clarification you want]`, ``]),
    `We request the Commission to consider these comments before the Regulations are finalised.`, ...sign].join("\n");
}

function save(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function StudioDesk({ drafts, groups }: { drafts: DeskDraft[]; groups: Group[] }) {
  const [g, setG] = useState<string>("");
  const [id, setId] = useState<string>("");
  const [org, setOrg] = useState(""); const [who, setWho] = useState("");
  const [text, setText] = useState(""); const [edited, setEdited] = useState(false); const [note, setNote] = useState("");
  const d = drafts.find((x) => x.id === id);
  const key = d && g ? `rs-comment:${d.id.slice(0, 12)}:${g}` : "";

  useEffect(() => {  // deep link from a draft's page, and the reader's last choice of group
    const q = new URLSearchParams(window.location.search);
    const want = q.get("draft"); const as = q.get("as");
    const hit = want ? drafts.find((x) => x.id.startsWith(want)) : undefined;
    if (hit) setId(hit.id);
    let last = ""; try { last = localStorage.getItem("rs-studio-as") ?? ""; } catch { /* storage unavailable */ }
    const pick = as || last;
    if (pick && groups.some(([k]) => k === pick)) setG(pick);
    try { setOrg(localStorage.getItem("rs-studio-org") ?? ""); setWho(localStorage.getItem("rs-studio-who") ?? ""); } catch { /* storage unavailable */ }
  }, [drafts, groups]);

  const fresh = useMemo(() => (d && g ? letter(d, g, org, who) : ""), [d, g, org, who]);
  useEffect(() => {  // load this device's saved edit for this draft and group, else the prepared text
    if (!key) return;
    let saved: string | null = null; try { saved = localStorage.getItem(key); } catch { /* storage unavailable */ }
    setText(saved ?? fresh); setEdited(saved !== null); setNote("");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => { if (!edited) setText(fresh); }, [fresh, edited]);

  const remember = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } };
  const prepared = d && g ? d.comments[g] : undefined;
  const fileBase = d ? `comments-${d.commission}-${d.id.slice(0, 8)}-${g}` : "comments";

  return (
    <div className="desk">
      <section className="glass step">
        <h2 className="label"><span>1</span> Who are you?</h2>
        <div className="personas" role="radiogroup" aria-label="Who are you?">{groups.map(([k, , long]) => (
          <button key={k} type="button" role="radio" aria-checked={g === k} className={`persona${g === k ? " on" : ""}`}
            onClick={() => { setG(k); remember("rs-studio-as", k); }}><GroupIcon g={k} size={22} /><span>{long}</span></button>))}</div>
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
                <em className={ready ? "ready" : ""}>{ready ? (g ? "Comments prepared for you" : "Comments prepared") : "Outline only"}</em>
              </button>);
          })}</div>)}
      </section>

      <section className="glass step" aria-live="polite">
        <h2 className="label"><span>3</span> Your comments</h2>
        {!d || !g ? <p className="muted">Choose who you are and a draft. Your comments appear here, ready to edit.</p> : (<>
          <p className="small">{prepared
            ? <>Prepared from the text of the draft for {VOICE[g]}{prepared.draft ? <> · <b className="warn">AI draft, not yet reviewed by the legal team</b></> : <> · reviewed by the Regulatory Studio legal team</>}. Replace every [bracket] with your own facts.</>
            : <>No prepared comments for this group on this draft yet, so this is an outline built from the summary. <a href={d.path}>Read the analysis</a> and write your points in.</>}</p>
          <div className="row2">
            <label>Organisation<input value={org} onChange={(e) => { setOrg(e.target.value); remember("rs-studio-org", e.target.value); }} placeholder="Your company" autoComplete="organization" /></label>
            <label>Signed by<input value={who} onChange={(e) => { setWho(e.target.value); remember("rs-studio-who", e.target.value); }} placeholder="Name, designation" autoComplete="name" /></label>
          </div>
          <label className="sr" htmlFor="comment-text">Comment text</label>
          <textarea id="comment-text" className="sheet" value={text} spellCheck
            onChange={(e) => { setText(e.target.value); setEdited(true); remember(key, e.target.value); setNote("Saved on this device"); }} />
          <div className="desk-actions">
            <button type="button" className="btn" onClick={() => save(`${fileBase}.txt`, text, "text/plain;charset=utf-8")}>Save as .txt</button>
            <button type="button" className="btn ghost" onClick={() => save(`${fileBase}.doc`, `<html><head><meta charset="utf-8"></head><body><pre style="font:12pt/1.5 Calibri,Arial,sans-serif;white-space:pre-wrap">${text.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</pre></body></html>`, "application/msword")}>Save as Word</button>
            <button type="button" className="btn ghost" onClick={async () => { try { await navigator.clipboard.writeText(text); setNote("Copied"); } catch { setNote("Copy failed: select the text and copy it"); } }}>Copy</button>
            {edited && <button type="button" className="btn ghost" onClick={() => { try { localStorage.removeItem(key); } catch { /* storage unavailable */ } setEdited(false); setNote("Back to the prepared text"); }}>Reset</button>}
            <span className="muted small">{note}</span>
          </div>
          <p className="note">Edits are kept only in this browser. This is a starting draft, not legal advice: check each point against <a href={d.path}>the draft</a> and file it the way the commission&apos;s public notice says.</p>
        </>)}
      </section>
    </div>
  );
}
