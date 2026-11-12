"use client";
import { useEffect } from "react";

/** Scroll behaviour for the cover: which commission is in view, blocks easing in, and a light parallax.
 *  Without JavaScript the page is the same content, fully visible and static. */
export default function CoverScroll() {
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".cover");
    if (!root) return;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    root.classList.add("js");
    const chapters = [...root.querySelectorAll<HTMLElement>("[data-chapter]")];
    const hero = root.querySelector<HTMLElement>(".cover-hero");
    // On phones the map pins to the top once the chapters start. Holding the stage at its full height first
    // means nothing below it moves when that happens.
    const stage = root.querySelector<HTMLElement>(".stage");
    const narrow = window.matchMedia("(max-width: 980px)");
    const hold = () => {
      if (!stage || root.classList.contains("in-story")) return;
      stage.style.minHeight = "";
      if (narrow.matches) stage.style.minHeight = `${stage.offsetHeight}px`;
    };
    hold();
    window.addEventListener("resize", hold);

    const focus = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) {
        const c = (e.target as HTMLElement).dataset.chapter!;
        root.dataset.active = c;
        root.classList.add("in-story", `seen-${c}`);
      }
    }, { rootMargin: "-40% 0px -55% 0px" });
    chapters.forEach((c) => focus.observe(c));

    const reveal = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); reveal.unobserve(e.target); }
    }, { rootMargin: "0px 0px -6% 0px" });
    root.querySelectorAll(".rise").forEach((el) => reveal.observe(el));

    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        const first = chapters[0];
        if (!first || first.getBoundingClientRect().top > window.innerHeight * 0.62) {
          delete root.dataset.active;
          root.classList.remove("in-story");
        }
        if (!calm && hero) {
          const p = Math.min(1, Math.max(0, window.scrollY / Math.max(1, hero.offsetHeight)));
          root.style.setProperty("--p", p.toFixed(3));
        }
        document.documentElement.style.setProperty("--sy", calm ? "0" : String(Math.round(window.scrollY)));
      });
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", hold); focus.disconnect(); reveal.disconnect(); };
  }, []);
  return null;
}
