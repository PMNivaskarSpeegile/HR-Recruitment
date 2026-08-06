import { useState } from "react";
import type { ReactNode } from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { ColumnDef, FilterFn, SortingState, VisibilityState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown, Search, SlidersHorizontal, Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface ServerPagination {
  pageIndex: number; // 0-based
  pageSize: number;
  total: number; // total rows across all pages (server count)
  onPageChange: (pageIndex: number) => void;
}

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  isLoading?: boolean;
  searchPlaceholder?: string;
  toolbar?: ReactNode;
  emptyMessage?: string;
  pageSize?: number;
  // Opt-in server-side mode: when provided, search + paging are driven by the
  // caller/server instead of the table's client-side models. `data` is the
  // current page only. Omit both for the default client-side behaviour.
  serverPagination?: ServerPagination;
  search?: { value: string; onChange: (v: string) => void };
  // Client-side only: override how the search box matches rows (e.g. to search
  // across fields that aren't columns). Ignored in server mode.
  globalFilterFn?: FilterFn<TData>;
  onRowClick?: (row: TData) => void;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  isLoading = false,
  searchPlaceholder = "Search…",
  toolbar,
  emptyMessage = "No records found.",
  pageSize = 10,
  serverPagination,
  search,
  globalFilterFn,
  onRowClick,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});

  const serverMode = !!serverPagination;
  const serverPageCount = serverPagination
    ? Math.max(1, Math.ceil(serverPagination.total / serverPagination.pageSize))
    : 1;

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, columnVisibility },
    globalFilterFn: serverMode ? undefined : globalFilterFn,
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setColumnVisibility,
    manualPagination: serverMode,
    manualFiltering: serverMode,
    enableSorting: !serverMode, // server fixes the order (e.g. by relevance)
    pageCount: serverMode ? serverPageCount : undefined,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: serverMode ? undefined : getSortedRowModel(),
    getFilteredRowModel: serverMode ? undefined : getFilteredRowModel(),
    getPaginationRowModel: serverMode ? undefined : getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });

  const colCount = table.getAllLeafColumns().length;
  const searchValue = serverMode ? (search?.value ?? "") : globalFilter;
  const setSearchValue = serverMode ? (search?.onChange ?? (() => {})) : setGlobalFilter;

  return (
    <div className="space-y-3">
      {/* Toolbar: search · column visibility · actions */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder={searchPlaceholder}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <SlidersHorizontal className="h-4 w-4" />
                Columns
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
              {table
                .getAllColumns()
                .filter((c) => c.getCanHide())
                .map((column) => (
                  <DropdownMenuItem
                    key={column.id}
                    onSelect={(e) => {
                      e.preventDefault();
                      column.toggleVisibility(!column.getIsVisible());
                    }}
                    className="capitalize"
                  >
                    <Check className={cn("h-4 w-4", column.getIsVisible() ? "opacity-100" : "opacity-0")} />
                    {column.id.replace(/_/g, " ")}
                  </DropdownMenuItem>
                ))}
            </DropdownMenuContent>
          </DropdownMenu>
          {toolbar}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border bg-card shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/50">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b">
                  {hg.headers.map((header) => {
                    const canSort = header.column.getCanSort();
                    const sorted = header.column.getIsSorted();
                    return (
                      <th
                        key={header.id}
                        className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                      >
                        {header.isPlaceholder ? null : canSort ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className="inline-flex items-center gap-1 hover:text-foreground"
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {sorted === "asc" ? (
                              <ArrowUp className="h-3.5 w-3.5" />
                            ) : sorted === "desc" ? (
                              <ArrowDown className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
                            )}
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 6 }).map((_, r) => (
                  <tr key={r} className="border-b last:border-0">
                    {Array.from({ length: colCount }).map((__, c) => (
                      <td key={c} className="px-4 py-3">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={colCount} className="px-4 py-12 text-center text-sm text-muted-foreground">
                    {emptyMessage}
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                    className={cn(
                      "border-b last:border-0 transition-colors hover:bg-accent/40",
                      onRowClick && "cursor-pointer"
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="whitespace-nowrap px-4 py-3">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {serverMode && serverPagination ? (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {serverPagination.total} record{serverPagination.total === 1 ? "" : "s"}
          </span>
          <div className="flex items-center gap-2">
            <span>
              Page {serverPagination.pageIndex + 1} of {serverPageCount}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={() => serverPagination.onPageChange(serverPagination.pageIndex - 1)}
              disabled={serverPagination.pageIndex <= 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => serverPagination.onPageChange(serverPagination.pageIndex + 1)}
              disabled={serverPagination.pageIndex >= serverPageCount - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {table.getFilteredRowModel().rows.length} record
            {table.getFilteredRowModel().rows.length === 1 ? "" : "s"}
          </span>
          <div className="flex items-center gap-2">
            <span>
              Page {table.getState().pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}
            </span>
            <Button variant="outline" size="icon" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
