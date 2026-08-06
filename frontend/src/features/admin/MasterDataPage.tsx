import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { cn } from "@/lib/utils";
import { RESOURCES } from "./config";
import { ResourceManager } from "./ResourceManager";

// Domains are classification data for Skills only, so they're managed as a
// lightweight section inside the Skill master rather than a top-level nav entry.
const HIDDEN_FROM_NAV = new Set(["domains"]);
const DOMAINS_CONFIG = RESOURCES.find((r) => r.key === "domains")!;

export default function MasterDataPage() {
  const navResources = RESOURCES.filter((r) => !HIDDEN_FROM_NAV.has(r.key));
  // Deep-link support: /admin?resource=users focuses that master on load.
  const [searchParams] = useSearchParams();
  const requested = searchParams.get("resource");
  const initialKey = navResources.some((r) => r.key === requested) ? requested! : navResources[0].key;
  const [activeKey, setActiveKey] = useState(initialKey);
  const config = RESOURCES.find((r) => r.key === activeKey)!;

  return (
    <div>
      <PageHeader title="Master Data" description="Manage the reference data used across the system" />

      {/*
        minmax(0,1fr) (not plain 1fr): grid tracks default to min-width:auto, so a
        plain 1fr track won't shrink below its content's intrinsic width and the
        DataTable would push the column wider than the panel (clipped now that the
        shell no longer scrolls sideways). minmax(0,1fr) lets the track shrink so
        the table's own overflow-x container handles horizontal scroll.
      */}
      <div className="grid gap-6 lg:grid-cols-[210px_minmax(0,1fr)]">
        <nav className="flex flex-row flex-wrap gap-1 lg:flex-col">
          {navResources.map((r) => (
            <button
              key={r.key}
              onClick={() => setActiveKey(r.key)}
              className={cn(
                "rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
                r.key === activeKey ? "bg-primary text-primary-foreground" : "text-foreground/80 hover:bg-accent"
              )}
            >
              {r.label}
            </button>
          ))}
        </nav>

        <div className="min-w-0 space-y-8">
          {/* The selected master. Keyed so per-resource state resets on switch. */}
          <ResourceManager key={config.key} config={config} />

          {/* Lightweight Domains management, embedded within the Skill master. */}
          {activeKey === "skills" && (
            <div className="border-t pt-6">
              <ResourceManager
                config={DOMAINS_CONFIG}
                heading="Domains"
                description="Classification used to organise Skills. Rename a domain and every linked skill updates automatically; a domain can be permanently deleted only when no skills use it."
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
