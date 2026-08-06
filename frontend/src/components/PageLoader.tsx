import { cn } from "@/lib/utils";

/** Centered spinner shown while a lazily-loaded route chunk is fetching, or
 *  (fullScreen) while the auth session is being verified before any layout. */
export function PageLoader({ fullScreen = false }: { fullScreen?: boolean }) {
  return (
    <div
      className={cn("flex w-full items-center justify-center", fullScreen ? "min-h-screen bg-background" : "h-[60vh]")}
      role="status"
      aria-label="Loading"
    >
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}
