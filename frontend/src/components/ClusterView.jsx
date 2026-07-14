import { useEffect, useState } from "react";
import { Layers } from "lucide-react";
import { events, ApiError } from "../api";

const SEVERITY_STYLES = {
  normal: "bg-severity-normal/15 text-severity-normal border-severity-normal/30",
  suspicious: "bg-severity-suspicious/15 text-severity-suspicious border-severity-suspicious/30",
  critical: "bg-severity-critical/15 text-severity-critical border-severity-critical/30",
};

export default function ClusterView() {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await events.clusters();
        if (!cancelled) {
          setClusters(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load clusters.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 20000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="panel flex flex-col h-full p-4">
      <div className="flex items-center gap-2 mb-3">
        <Layers size={16} className="text-ink-secondary" />
        <h2 className="font-display text-sm font-semibold text-ink-primary">Behavior Clusters</h2>
        <span className="text-xs text-ink-muted ml-auto">unsupervised · K-Means</span>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-sm text-ink-muted">Loading clusters…</div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-sm text-severity-critical">{error}</div>
      ) : clusters.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-sm text-ink-muted">
          Clusters appear once enough events have been classified.
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto scrollbar-thin grid grid-cols-1 sm:grid-cols-2 gap-3 content-start">
          {clusters.map((cluster) => (
            <div key={cluster.cluster_id} className="panel-raised p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-ink-secondary">Cluster {cluster.cluster_id}</span>
                <span
                  className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${
                    SEVERITY_STYLES[cluster.dominant_severity] || SEVERITY_STYLES.normal
                  }`}
                >
                  {cluster.dominant_severity}
                </span>
              </div>

              <p className="text-2xl font-display font-semibold text-ink-primary">
                {cluster.event_count}
                <span className="text-xs text-ink-muted font-sans font-normal ml-1">events</span>
              </p>

              <ul className="mt-2 space-y-1">
                {cluster.sample_messages.map((msg, i) => (
                  <li key={i} className="text-xs text-ink-muted font-mono truncate" title={msg}>
                    {msg}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}