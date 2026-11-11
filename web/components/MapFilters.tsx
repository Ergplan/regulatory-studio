"use client";
import { useState } from "react";

// Toggle link types on the map. Hidden types get a class on the figure; CSS does the rest.
export default function MapFilters({ types, labels }: { types: string[]; labels: Record<string, string> }) {
  const [off, setOff] = useState<string[]>([]);
  function toggle(t: string, el: HTMLButtonElement) {
    const next = off.includes(t) ? off.filter((x) => x !== t) : [...off, t];
    setOff(next);
    const fig = el.closest("figure");
    if (fig) fig.setAttribute("data-off", next.join(" "));
  }
  return (
    <div className="map-filters" role="group" aria-label="Show link types">
      {types.map((t) => (
        <button key={t} type="button" aria-pressed={!off.includes(t)} onClick={(e) => toggle(t, e.currentTarget)}
          className={"chip" + (off.includes(t) ? " off" : "")}>{labels[t] ?? t}</button>
      ))}
    </div>
  );
}
