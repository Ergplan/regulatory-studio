// Server-rendered SVG map: the subject in the centre, what it rests on to the left,
// related decisions to the right. Every node is a link, so the map is navigable and
// crawlable without JavaScript. A plain list of the same links is rendered beside it.
import MapFilters from "./MapFilters";

export interface MapNode {
  key: string; label: string; sub?: string; href: string;
  side: "left" | "right"; types: string[]; kind: string;
}

const W = 760, BOX_W = 214, BOX_H = 46, GAP = 58, CENTER_W = 220;
const STYLE: Record<string, { dash?: string; tone: string }> = {
  applies: { tone: "var(--edge)" },
  interprets: { tone: "var(--accent)" },
  relaxes: { tone: "var(--warn)", dash: "6 4" },
  follows: { tone: "var(--edge)" },
  distinguishes: { tone: "var(--edge)", dash: "2 4" },
  appealed_in: { tone: "var(--accent)", dash: "6 4" },
  upholds: { tone: "var(--good)" },
  sets_aside: { tone: "var(--bad)" },
  remands: { tone: "var(--warn)" },
  amends: { tone: "var(--warn)" },
  made_under: { tone: "var(--edge)", dash: "2 4" },
};

function clip(s: string, n: number) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

export default function SpiderMap({ center, nodes, typeLabels, title }: {
  center: { label: string; sub?: string }; nodes: MapNode[]; typeLabels: Record<string, string>; title: string;
}) {
  // Balance the sides when one is empty, so a clause with ten citing orders still reads well.
  let left = nodes.filter((n) => n.side === "left");
  let right = nodes.filter((n) => n.side === "right");
  if (!left.length && right.length > 3) { left = right.filter((_, i) => i % 2 === 1); right = right.filter((_, i) => i % 2 === 0); }
  if (!right.length && left.length > 3) { right = left.filter((_, i) => i % 2 === 1); left = left.filter((_, i) => i % 2 === 0); }
  const rows = Math.max(left.length, right.length, 1);
  const H = Math.max(150, rows * GAP + 48);
  const cy = H / 2, cx = W / 2;
  const place = (list: MapNode[], side: "left" | "right") => list.map((n, i) => {
    const total = list.length * GAP;
    const y = (H - total) / 2 + i * GAP + GAP / 2;
    const x = side === "left" ? 12 : W - 12 - BOX_W;
    return { ...n, x, y, placedSide: side };
  });
  const placed = [...place(left, "left"), ...place(right, "right")];
  const types = Array.from(new Set(nodes.flatMap((n) => n.types)));

  return (
    <figure className="map">
      {types.length > 1 && <MapFilters types={types} labels={typeLabels} />}
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} className="map-svg">
        <title>{title}</title>
        {placed.map((n) => {
          const t = n.types[0]; const st = STYLE[t] ?? STYLE.applies;
          const x1 = n.placedSide === "left" ? cx - CENTER_W / 2 : cx + CENTER_W / 2;
          const x2 = n.placedSide === "left" ? n.x + BOX_W : n.x;
          const mx = (x1 + x2) / 2;
          return (
            <g key={"e" + n.key} className={"edge " + n.types.map((x) => "t-" + x).join(" ")}>
              <path d={`M${x1} ${cy} C${mx} ${cy} ${mx} ${n.y} ${x2} ${n.y}`} fill="none" stroke={st.tone}
                strokeWidth={1.4} strokeDasharray={st.dash} />
              <text x={n.placedSide === "left" ? x2 + 6 : x2 - 6} y={n.y - 6} textAnchor={n.placedSide === "left" ? "start" : "end"}
                className="edge-label">{n.types.map((x) => typeLabels[x] ?? x).join(" · ")}</text>
            </g>
          );
        })}
        <g className="center">
          <rect x={cx - CENTER_W / 2} y={cy - 30} width={CENTER_W} height={60} rx={8} />
          <text x={cx} y={cy - 4} textAnchor="middle" className="node-label">{clip(center.label, 30)}</text>
          {center.sub && <text x={cx} y={cy + 14} textAnchor="middle" className="node-sub">{clip(center.sub, 34)}</text>}
        </g>
        {placed.map((n) => (
          <a key={n.key} href={n.href} className={"node k-" + n.kind + " " + n.types.map((x) => "t-" + x).join(" ")}>
            <title>{n.label}{n.sub ? " — " + n.sub : ""}</title>
            <rect x={n.x} y={n.y - BOX_H / 2} width={BOX_W} height={BOX_H} rx={8} />
            <text x={n.x + 10} y={n.y - 3} className="node-label">{clip(n.label, 28)}</text>
            {n.sub && <text x={n.x + 10} y={n.y + 13} className="node-sub">{clip(n.sub, 32)}</text>}
          </a>
        ))}
      </svg>
      <figcaption className="muted">Left: provisions relied on. Right: related decisions. Select any box to recentre the map on it.</figcaption>
    </figure>
  );
}
