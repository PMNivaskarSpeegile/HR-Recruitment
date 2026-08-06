import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { PageLoader } from "@/components/PageLoader";
import type { Role } from "@/lib/types";

/** Gate routes behind authentication and (optionally) a set of allowed roles. */
export function ProtectedRoute({ allow }: { allow?: Role[] }) {
  const { user, initialising } = useAuth();
  const location = useLocation();

  // Show the branded loader while the stored session is verified with /auth/me/.
  if (initialising) return <PageLoader fullScreen />;

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (allow && !allow.includes(user.role.code)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
