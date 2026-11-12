import type { Metadata } from "next";
import Library from "@/components/Library";

export const metadata: Metadata = { title: "Regulations in force", description: "Notified electricity regulations split into clauses, with the orders that applied each one.", alternates: { canonical: "/regulations" } };
export default function Regulations() { return <Library kind="regulations" />; }
