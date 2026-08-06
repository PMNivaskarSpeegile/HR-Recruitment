import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/badge";
import { fmtDateTime } from "@/lib/format";
import { useCommunications } from "./api";
import type { Communication } from "./api";

const columns: ColumnDef<Communication>[] = [
  {
    accessorKey: "candidate_name",
    header: "Candidate",
    cell: ({ row }) => (
      <div className="min-w-0">
        <div className="font-medium">{row.original.candidate_name}</div>
        <div className="text-xs text-muted-foreground">{row.original.recipient}</div>
      </div>
    ),
  },
  {
    accessorKey: "subject",
    header: "Subject",
    cell: ({ row }) => <span className="text-muted-foreground">{row.original.subject ?? "—"}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const ok = row.original.status === "SENT";
      return (
        <Badge variant={ok ? "success" : "danger"} title={row.original.error_message ?? undefined}>
          {ok ? "Sent" : "Failed"}
        </Badge>
      );
    },
  },
  {
    accessorKey: "sent_by_name",
    header: "Sent by",
    cell: ({ row }) => row.original.sent_by_name ?? "—",
  },
  {
    accessorKey: "sent_on",
    header: "Sent on",
    cell: ({ row }) => <span className="text-muted-foreground">{fmtDateTime(row.original.sent_on)}</span>,
  },
];

/** UC4 JD tracker — every JD email send attempt logged for a requirement. */
export function JdTracker({ reqId }: { reqId: string }) {
  const comms = useCommunications(reqId);
  return (
    <DataTable
      columns={columns}
      data={comms.data?.results ?? []}
      isLoading={comms.isLoading}
      searchPlaceholder="Search sent emails…"
      emptyMessage="No JD emails have been sent for this requirement yet."
    />
  );
}
