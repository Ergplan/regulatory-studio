import type { GroupKey } from "@/lib/data";

// Simple line icons, drawn here (no icon font, no network). Decorative: the group name is always next to them.
const PATHS: Record<GroupKey, string> = {
  discoms: "M12 3v18M6 6h12M8 10h8M9 21h6M6 6v2M18 6v2M8 10v2M16 10v2",
  ci_consumers: "M3 21V11l5 3v-3l5 3v-3l5 3V5h3v16zM2 21h20M7 18h2M12 18h2",
  captive: "M4 21V12h9v9M13 21V9h7v12M2 21h20M7 7a2 2 0 1 0 0.01 0M7 2v1M3.5 3.5l.7.7M10.5 3.5l-.7.7M2 7h1M11 7h1",
  re_developers: "M12 10v11M9 21h6M12 10L12 3M12 10l-6 4M12 10l6 4M12 10a0.5 0.5 0 1 0 0.01 0",
  storage: "M3 7h16v10H3zM19 10h2v4h-2M11 8.5l-2.5 4h3.5l-2.5 3.5",
  conventional: "M6 21c1.2-4 1.2-8 0-12h9c-1.2 4-1.2 8 0 12zM4 21h13M8 6c0-1.5 1-2.5 2.5-2.5M12 6c0-1.5 1-2.5 2.5-2.5",
  transmission: "M12 2L8 22M12 2l4 20M6 8h12M7 13h10M9.4 8l5.2 5M14.6 8l-5.2 5M5 22h14",
  traders: "M3 17l5-5 4 3 8-8M15 7h5v5M3 21h18",
};

export default function GroupIcon({ g, size = 20 }: { g: GroupKey; size?: number }) {
  return (
    <svg className="gicon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[g]} />
    </svg>
  );
}
