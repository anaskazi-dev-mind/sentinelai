import { useEffect, useState, useCallback } from "react";
import { Shield, LogIn, LogOut, X } from "lucide-react";

import { auth, events, ApiError } from "./api";
import LiveFeed from "./components/LiveFeed";
import RiskChart from "./components/RiskChart";
import ClusterView from "./components/ClusterView";
import FileVault from "./components/FileVault";
import ChatPanel from "./components/ChatPanel";

const SEVERITY_COLOR = {
  normal: "#2DD4BF",
  suspicious: "#F0B429",
  critical: "#E5484D",
};

const SEVERITY_RANK = { normal: 0, suspicious: 1, critical: 2 };

// =====================================================================
// Signature element: a slow, breathing gauge showing aggregate system
// risk. This is the single visual that communicates "always watching,
// nothing dramatic unless something's actually wrong" -- the core
// SentinelAI concept, at a glance, before reading a single word.
// =====================================================================

function useSystemRisk() {
  const [state, setState] = useState({ score: 0, severity: "normal", loading: true });

  const load = useCallback(async () => {
    try {
      const data = await events.list({ limit: 20 });
      const items = data.items;

      if (items.length === 0) {
        setState({ score: 0, severity: "normal", loading: false });
        return;
      }

      const avgScore = items.reduce((sum, e) => sum + e.risk_score, 0) / items.length;
      const dominant = items.reduce(
        (worst, e) => (SEVERITY_RANK[e.severity] > SEVERITY_RANK[worst] ? e.severity : worst),
        "normal"
      );

      setState({ score: avgScore, severity: dominant, loading: false });
    } catch {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, [load]);

  return state;
}

function RiskPulse({ score, severity, loading }) {
  const color = SEVERITY_COLOR[severity] || SEVERITY_COLOR.normal;

  return (
    <div className="flex items-center gap-3">
      <div className="relative w-14 h-14 shrink-0">
        <span
          className="absolute inset-0 rounded-full animate-pulse-ring"
          style={{ backgroundColor: color }}
          aria-hidden="true"
        />
        <span
          className="absolute inset-0 rounded-full animate-pulse-ring"
          style={{ backgroundColor: color, animationDelay: "1.2s" }}
          aria-hidden="true"
        />
        <div
          className="relative w-full h-full rounded-full flex items-center justify-center border-2 bg-surface"
          style={{ borderColor: color }}
        >
          <span className="text-sm font-display font-bold text-ink-primary">
            {loading ? "—" : Math.round(score)}
          </span>
        </div>
      </div>
      <div className="leading-tight">
        <p className="text-[11px] uppercase tracking-wider text-ink-muted">System Risk</p>
        <p className="text-sm font-medium capitalize" style={{ color }}>
          {loading ? "assessing…" : severity}
        </p>
      </div>
    </div>
  );
}

// =====================================================================
// Compact auth widget -- sign in / register without leaving the dashboard
// =====================================================================

function AuthControl() {
  const [user, setUser] = useState(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    auth.me().then(setUser).catch(() => setUser(null));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        await auth.register(form.username, form.email, form.password);
      }
      await auth.login(form.username, form.password);
      const me = await auth.me();
      setUser(me);
      setOpen(false);
      setForm({ username: "", email: "", password: "" });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail || err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    auth.logout();
    setUser(null);
  }

  if (user) {
    return (
      <button
        onClick={handleLogout}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-ink-secondary hover:text-severity-critical border border-border rounded-lg hover:border-severity-critical/40 transition-colors"
      >
        <LogOut size={13} /> {user.username}
      </button>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-void bg-severity-suspicious rounded-lg hover:brightness-110 transition-all"
      >
        <LogIn size={13} /> Sign in
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-72 panel p-4 z-50">
          <div className="flex items-center justify-between mb-3">
            <div className="flex gap-3 text-xs font-medium">
              <button
                onClick={() => setMode("login")}
                className={mode === "login" ? "text-severity-suspicious" : "text-ink-muted"}
              >
                Login
              </button>
              <button
                onClick={() => setMode("register")}
                className={mode === "register" ? "text-severity-suspicious" : "text-ink-muted"}
              >
                Register
              </button>
            </div>
            <button onClick={() => setOpen(false)} className="text-ink-muted hover:text-ink-primary">
              <X size={14} />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-2">
            <input
              type="text"
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required
              className="w-full bg-surface-raised border border-border rounded-lg px-3 py-1.5 text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-severity-suspicious"
            />
            {mode === "register" && (
              <input
                type="email"
                placeholder="Email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
                className="w-full bg-surface-raised border border-border rounded-lg px-3 py-1.5 text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-severity-suspicious"
              />
            )}
            <input
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={8}
              className="w-full bg-surface-raised border border-border rounded-lg px-3 py-1.5 text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-severity-suspicious"
            />

            {error && <p className="text-xs text-severity-critical">{error}</p>}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-1.5 text-xs font-semibold text-void bg-severity-suspicious rounded-lg hover:brightness-110 transition-all disabled:opacity-50"
            >
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

// =====================================================================
// App shell
// =====================================================================

export default function App() {
  const risk = useSystemRisk();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
        <div className="flex items-center gap-2.5">
          <Shield size={20} className="text-severity-suspicious" />
          <span className="font-display text-lg font-semibold text-ink-primary">SentinelAI</span>
          <span className="text-xs text-ink-muted hidden sm:inline">Log Intelligence & File Security Copilot</span>
        </div>

        <div className="flex items-center gap-5">
          <RiskPulse score={risk.score} severity={risk.severity} loading={risk.loading} />
          <AuthControl />
        </div>
      </header>

      <main className="flex-1 min-h-0 p-4 grid grid-cols-1 xl:grid-cols-12 gap-4">
        <section className="xl:col-span-4 h-[560px] xl:h-auto">
          <LiveFeed />
        </section>

        <section className="xl:col-span-5 flex flex-col gap-4">
          <div className="h-[270px]">
            <RiskChart />
          </div>
          <div className="h-[270px]">
            <ClusterView />
          </div>
        </section>

        <section className="xl:col-span-3 h-[560px] xl:h-auto">
          <ChatPanel />
        </section>

        <section className="xl:col-span-12 h-[240px]">
          <FileVault />
        </section>
      </main>
    </div>
  );
}