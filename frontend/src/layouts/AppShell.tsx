import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { PageLoader } from "@/components/PageLoader";

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        {/*
          overflow-x-hidden is deliberate: with only overflow-y-auto the CSS
          overflow spec forces overflow-x to compute to `auto`, making <main> a
          horizontal scroll container. Any descendant a hair wider than the
          panel then produces a phantom page-level horizontal scrollbar with an
          empty region after the content. The app frame must never scroll
          sideways — horizontal scrolling belongs only to inner containers that
          opt in (e.g. DataTable's overflow-x-auto).
        */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden">
          <div className="mx-auto w-full max-w-[1600px] p-6 lg:p-8 animate-fade-in">
            {/* Inner boundary: page chunks load without losing the sidebar/topbar */}
            <Suspense fallback={<PageLoader />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}
