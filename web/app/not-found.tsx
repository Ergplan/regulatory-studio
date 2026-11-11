import Link from "next/link";
export default function NotFound() {
  return <div className="card empty"><h1>Not found</h1><p>That page does not exist. <Link href="/orders">Browse reviewed orders</Link>.</p></div>;
}
