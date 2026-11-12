import { LibraryRow, orderRow } from "@/components/Library";
import type { Order } from "@/lib/data";

/** An order in a list: the same row design as everywhere else. */
export default function OrderCard({ o }: { o: Order; showSummary?: boolean }) {
  return <LibraryRow r={orderRow(o)} as="article" />;
}
