import type { Metadata } from "next";
import Library from "@/components/Library";

export const metadata: Metadata = {
  title: "Draft regulations and public consultations",
  description: "Draft regulations, amendments and consultation papers from CERC and state electricity commissions, by commission, with comment deadlines and the groups each one affects.",
  alternates: { canonical: "/consultations" },
};
export default function Consultations() { return <Library kind="drafts" />; }
