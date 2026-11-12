"use client";
import { useEffect, useState } from "react";

/** Dark by default, like joulewise.tech; the reader's choice is remembered on this device. */
export default function ThemeToggle() {
  const [light, setLight] = useState(false);
  useEffect(() => { setLight(document.documentElement.dataset.theme === "light"); }, []);
  function flip() {
    const next = !light;
    setLight(next);
    if (next) document.documentElement.dataset.theme = "light"; else delete document.documentElement.dataset.theme;
    try { localStorage.setItem("rs-theme", next ? "light" : "dark"); } catch { /* storage unavailable */ }
  }
  return (
    <button type="button" className="theme-toggle" onClick={flip} aria-label={light ? "Switch to dark theme" : "Switch to light theme"}
      title={light ? "Switch to dark theme" : "Switch to light theme"}>
      {light
        ? <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><path d="M13.5 9.5A6 6 0 0 1 6.5 2.5a6 6 0 1 0 7 7z" /></svg>
        : <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><circle cx="8" cy="8" r="3.1" /><path d="M8 1.4V3M8 13v1.6M1.4 8H3M13 8h1.6M3.3 3.3l1.2 1.2M11.5 11.5l1.2 1.2M3.3 12.7l1.2-1.2M11.5 4.5l1.2-1.2" strokeLinecap="round" /></svg>}
    </button>
  );
}
