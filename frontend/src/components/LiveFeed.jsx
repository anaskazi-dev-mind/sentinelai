import { useEffect, useRef, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { RefreshCw, FileText, Terminal } from "lucide-react";
import { events, ApiError } from "../api";

const SEVERITY_STYLES = {
  normal: { dot: "bg-severity-normal", text: "text-severity-normal" },
  suspicious: { dot: "bg-severity-suspicious", text: "text-severity-suspicious" },
  critical: { dot: "bg-severity-critical", text: "text-severity-critical" },
};

const POLL_INTERVAL_MS = 5000;

function formatTime(isoString) {
  return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function EventRow({ event }) {
  const style = SEVERITY_STYLES[event.severity] || SEVERITY_STYLES.normal;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="flex items-start gap-3 px-4 py-3 border-b border-border-subtle last:border-none hover:bg-surface-hover/40 transition-colors"
    >
      <span className={`status-dot mt-1.5 ${style.dot}`} aria-hidden="true" />

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className={`text-xs font-semibold uppercase tracking-wide ${style.text}`}>
            {event.severity}
          </span>
          <span className="text-xs text-ink-muted font-mono shrink-0">{formatTime(event.created_at)}</span>
        </div>

        <p className="mt-1 text-sm text-ink-primary font-mono leading-snug break-words">
          {event.raw_message}
        </p>

        <div className="mt-1.5 flex items-center gap-3 text-xs text-ink-secondary">
          {event.file_path && (
            <span className="flex items-center gap-1 truncate">
              <FileText size={12} className="shrink-0" /> {event.file_path}
            </span>
          )}
          <span className="shrink-0">risk {event.risk_score.toFixed(0)}</span>
          <span className="shrink-0 text-ink-muted">· {event.model_used}</span>
        </div>
      </div>
    </motion.li>
  );
}

export default function LiveFeed() {
  const [events_, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);
  const intervalRef = useRef(null);

  const fetchEvents = useCallback(async () => {
    try {
      const data = await events.list({ limit: 25 });
      setEvents(data.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
    intervalRef.current = setInterval(fetchEvents, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [fetchEvents]);

  async function handleManualScan() {
    setScanning(true);
    try {
      await events.triggerScan();
      await fetchEvents();
    } catch {
      // Surfaced via the persistent error banner on next poll if it's systemic.
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <Terminal size={16} className="text-ink-secondary" />
          <h2 className="font-display text-sm font-semibold text-ink-primary">Live Feed</h2>
        </div>
        <button
          onClick={handleManualScan}
          disabled={scanning}
          className="flex items-center gap-1.5 text-xs text-ink-secondary hover:text-severity-suspicious transition-colors disabled:opacity-40"
        >
          <RefreshCw size={13} className={scanning ? "animate-spin" : ""} />
          Scan now
        </button>
      </div>

      {error && (
        <div className="px-4 py-2 text-xs text-severity-critical bg-severity-critical/10 border-b border-border-subtle">
          {error}
        </div>
      )}

      <ul className="flex-1 overflow-y-auto scrollbar-thin">
        {loading ? (
          <li className="px-4 py-8 text-center text-sm text-ink-muted">Loading events…</li>
        ) : events_.length === 0 ? (
          <li className="px-4 py-8 text-center text-sm text-ink-muted">
            No events yet. The scheduler ingests new activity automatically every few seconds.
          </li>
        ) : (
          <AnimatePresence initial={false}>
            {events_.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </AnimatePresence>
        )}
      </ul>
    </div>
  );
}