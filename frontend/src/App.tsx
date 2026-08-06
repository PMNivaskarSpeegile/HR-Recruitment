import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { AppShell } from "@/layouts/AppShell";
import { PageLoader } from "@/components/PageLoader";

// Route-level code splitting: each page (and its heavy deps, e.g. Recharts /
// TanStack Table) loads on demand, keeping the initial bundle small.
const LoginPage = lazy(() => import("@/pages/LoginPage"));
const DashboardPage = lazy(() => import("@/features/dashboard/DashboardPage"));
const RequirementsPage = lazy(() => import("@/features/requirements/RequirementsPage"));
const RequirementDetailsPage = lazy(() => import("@/features/requirements/RequirementDetailsPage"));
const CandidatesPage = lazy(() => import("@/features/candidates/CandidatesPage"));
const PipelinePage = lazy(() => import("@/features/pipeline/PipelinePage"));
const MasterDataPage = lazy(() => import("@/features/admin/MasterDataPage"));
const DuplicateReviewsPage = lazy(() => import("@/features/candidates/DuplicateReviewsPage"));

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/requirements" element={<RequirementsPage />} />
            <Route path="/requirements/:id" element={<RequirementDetailsPage />} />
            <Route path="/candidates" element={<CandidatesPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route element={<ProtectedRoute allow={["ADM"]} />}>
              <Route path="/admin" element={<MasterDataPage />} />
              <Route path="/duplicate-reviews" element={<DuplicateReviewsPage />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
