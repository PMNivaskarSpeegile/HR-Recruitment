import { NavLink } from "react-router-dom";
import { LayoutDashboard, Briefcase, Users, GitBranch, Database, CopyCheck, Briefcase as Logo } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { APP_NAME, APP_VERSION } from "@/lib/brand";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

interface NavEntry {
  label: string;
  to: string;
  icon: LucideIcon;
  soon?: boolean;
}

const NAV: Record<Role, NavEntry[]> = {
  ADM: [
    { label: "Dashboard", to: "/", icon: LayoutDashboard },
    { label: "Requirements", to: "/requirements", icon: Briefcase },
    { label: "Candidates", to: "/candidates", icon: Users },
    { label: "Duplicate Review", to: "/duplicate-reviews", icon: CopyCheck },
    { label: "Master Data", to: "/admin", icon: Database },
  ],
  HM: [
    { label: "Dashboard", to: "/", icon: LayoutDashboard },
    { label: "Requirements", to: "/requirements", icon: Briefcase },
    { label: "Candidates", to: "/candidates", icon: Users },
  ],
  REC: [
    { label: "Dashboard", to: "/", icon: LayoutDashboard },
    { label: "Requirements", to: "/requirements", icon: Briefcase },
    { label: "Candidates", to: "/candidates", icon: Users },
    { label: "Pipeline", to: "/pipeline", icon: GitBranch },
  ],
};

export function Sidebar() {
  const { user } = useAuth();
  const items = user ? NAV[user.role.code] : [];

  return (
    <aside className="hidden md:flex md:w-64 md:shrink-0 md:flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 items-center gap-2.5 px-5 border-b border-sidebar-border">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Logo className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">{APP_NAME}</div>
          <div className="text-[11px] text-sidebar-muted">Enterprise</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <p className="px-3 pb-2 pt-1 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted">
          Workspace
        </p>
        <ul className="space-y-1">
          {items.map((item) => {
            const Icon = item.icon;
            if (item.soon) {
              return (
                <li key={item.to}>
                  <div className="flex cursor-not-allowed items-center justify-between rounded-md px-3 py-2 text-sm text-sidebar-muted/70">
                    <span className="flex items-center gap-3">
                      <Icon className="h-[18px] w-[18px]" />
                      {item.label}
                    </span>
                    <span className="rounded bg-sidebar-border px-1.5 py-0.5 text-[10px] font-medium">Soon</span>
                  </div>
                </li>
              );
            }
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-sidebar-foreground/80 hover:bg-white/5 hover:text-sidebar-foreground"
                    )
                  }
                >
                  <Icon className="h-[18px] w-[18px]" />
                  {item.label}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-sidebar-border p-4 text-[11px] text-sidebar-muted">
        {APP_VERSION} · Phase 1
      </div>
    </aside>
  );
}
