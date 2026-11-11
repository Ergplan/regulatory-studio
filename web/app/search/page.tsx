import type { Metadata } from "next";
import Search from "@/components/Search";

export const metadata: Metadata = { title: "Search", alternates: { canonical: "/search" } };

export default function SearchPage() {
  return (<><h1>Search</h1>
    <noscript><p>Search needs JavaScript. Browse <a href="/orders">all orders</a> or <a href="/regulations">the regulation registry</a> instead.</p></noscript>
    <Search /></>);
}
