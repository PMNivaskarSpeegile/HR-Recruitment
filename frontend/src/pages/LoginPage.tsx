import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, CheckCircle2, Eye, EyeOff } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { APP_NAME, APP_VERSION } from "@/lib/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

const HIGHLIGHTS = [
  "Track every requirement and candidate in one place",
  "Move candidates through a structured screening pipeline",
  "Role-based access for recruiters, managers and admins",
];

export default function LoginPage() {
  const { login, user, initialising } = useAuth();
  const navigate = useNavigate();

  // A valid, backend-verified session shouldn't see the login form.
  useEffect(() => {
    if (!initialising && user) navigate("/", { replace: true });
  }, [initialising, user, navigate]);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err: any) {
      if (err?.response) {
        // Server responded (e.g. 401) — show its message.
        setError(err.response.data?.message ?? "Invalid username or password.");
      } else {
        // No response → network/CORS/backend-down.
        setError("Cannot reach the server. Make sure the backend is running on http://127.0.0.1:8000.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left — brand story */}
      <div className="relative hidden overflow-hidden bg-sidebar text-sidebar-foreground lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-primary/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-teal/20 blur-3xl" />

        <div className="relative flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Briefcase className="h-5 w-5" />
          </div>
          <span className="text-sm font-semibold">{APP_NAME}</span>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-4xl font-bold leading-tight tracking-tight">Build Exceptional Teams</h1>
          <p className="mt-4 text-sidebar-muted">
            A modern applicant tracking system that brings requirements, candidates and screening
            into one fast, structured workflow.
          </p>
          <ul className="mt-8 space-y-3">
            {HIGHLIGHTS.map((h) => (
              <li key={h} className="flex items-start gap-3 text-sm text-sidebar-foreground/90">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-teal" />
                {h}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative text-xs text-sidebar-muted">© 2026 {APP_NAME} · {APP_VERSION}</div>
      </div>

      {/* Right — login card */}
      <div className="flex items-center justify-center bg-background p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Briefcase className="h-5 w-5" />
            </div>
            <span className="text-sm font-semibold">{APP_NAME}</span>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight">Welcome back</h2>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to continue to your workspace.</p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="e.g. priya.sharma"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  required
                  className="pr-10"
                />
                <button
                  type="button"
                  // Prevent the click from stealing focus, so the field keeps
                  // focus and caret position when toggling visibility.
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  title={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 flex items-center rounded-md px-3 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox id="remember" defaultChecked />
              <Label htmlFor="remember" className="text-sm font-normal text-muted-foreground">
                Remember me on this device
              </Label>
            </div>

            {error && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="mt-8 text-center text-xs text-muted-foreground">
            Protected workspace · Authorized users only
          </p>
        </div>
      </div>
    </div>
  );
}
