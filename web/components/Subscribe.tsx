"use client";
import { useState } from "react";

export default function Subscribe() {
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setState("sending");
    const form = new FormData(e.currentTarget);
    const res = await fetch("/api/subscribe", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    setState(res.ok ? "done" : "error");
    setMsg(data.message ?? (res.ok ? "Check your inbox to confirm." : "Something went wrong. Please try again."));
  }
  return (
    <form className="subscribe" onSubmit={submit}>
      <label htmlFor="email">Weekly digest by email, free</label>
      <div className="row">
        <input id="email" name="email" type="email" required placeholder="you@company.com" autoComplete="email" />
        <button type="submit" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Subscribe"}</button>
      </div>
      <input name="company" tabIndex={-1} autoComplete="off" aria-hidden="true" className="sr" />
      <p className="muted small">We store your email only to send the digest, after you confirm it. Every email has an unsubscribe link.</p>
      {msg && <p role="status" className={state === "error" ? "bad" : "good"}>{msg}</p>}
    </form>
  );
}
