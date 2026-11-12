import type { Metadata } from "next";
import Library from "@/components/Library";

export const metadata: Metadata = { title: "Orders", description: "Orders of CERC and state electricity commissions, each traced to the provisions it rests on.", alternates: { canonical: "/orders" } };
export default function Orders() { return <Library kind="orders" />; }
