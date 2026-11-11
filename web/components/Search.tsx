"use client";
import { useEffect, useMemo, useState } from "react";

type Doc = { t: string; title: string; sub: string; href: string; text: string };

export default function Search() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("q") ?? "";
    setQ(initial);
    fetch("/search-index.json").then((r) => r.json()).then(setDocs).catch(() => setDocs([]));
  }, []);
  const hits = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter((w) => w.length > 1);
    if (!words.length) return [];
    return docs
      .map((d) => {
        const hay = (d.title + " " + d.text).toLowerCase();
        const score = words.reduce((s, w) => s + (hay.includes(w) ? 1 + (d.title.toLowerCase().includes(w) ? 2 : 0) : -100), 0);
        return { d, score };
      })
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 40);
  }, [q, docs]);
  return (
    <div>
      <form role="search" onSubmit={(e) => e.preventDefault()} className="subscribe">
        <label htmlFor="q">Search orders, regulations and clauses</label>
        <div className="row"><input id="q" type="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. banking, Regulation 8(4), NPCL, cross-subsidy" autoFocus /></div>
      </form>
      {q && <p className="muted small">{hits.length} results</p>}
      <ul className="links-list">{hits.map(({ d }) => (
        <li key={d.href}><span className="tag">{d.t}</span> <a href={d.href}>{d.title}</a>
          {d.sub && <div className="small muted">{d.sub}</div>}</li>
      ))}</ul>
    </div>
  );
}
