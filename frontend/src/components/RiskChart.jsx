import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { events, ApiError } from "../api";

function formatAxisTime(isoString) {
  return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function mergeSeries(history, forecast) {
  const historyPoints = history.map((p) => ({
    timestamp: p.timestamp,
    actual: p.actual_risk,
    predicted: null,
  }));

  const forecastPoints = forecast.map((p) => ({
    timestamp: p.timestamp,
    actual: null,
    predicted: p.predicted_risk,
  }));

  // Bridge the gap: the forecast line should visually continue from the
  // last actual point, not start floating in empty space.
  if (historyPoints.length && forecastPoints.length) {
    forecastPoints[0] = { ...forecastPoints[0], bridge: historyPoints[historyPoints.length - 1].actual };
  }

  return [...historyPoints, ...forecastPoints];
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="panel-raised px-3 py-2 text-xs">
      <p className="text-ink-muted font-mono mb-1">{formatAxisTime(label)}</p>
      {payload.map((entry) =>
        entry.value != null ? (
          <p key={entry.dataKey} style={{ color: entry.color }}>
            {entry.dataKey === "actual" ? "Observed" : "Forecast"}: {entry.value.toFixed(1)}
          </p>
        ) : null
      )}
    </div>
  );
}

export default function RiskChart() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await events.riskTrend(6);
        if (!cancelled) {
          setData(mergeSeries(res.history, res.forecast));
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load risk trend.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="panel flex flex-col h-full p-4">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={16} className="text-ink-secondary" />
        <h2 className="font-display text-sm font-semibold text-ink-primary">Risk Trend</h2>
        <span className="text-xs text-ink-muted ml-auto">last 6h · forecast via Linear Regression</span>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-sm text-ink-muted">Loading trend…</div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-sm text-severity-critical">{error}</div>
      ) : data.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-sm text-ink-muted">
          Not enough data yet to plot a trend.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#232A3B" vertical={false} />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatAxisTime}
              stroke="#5B6478"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={[0, 100]}
              stroke="#5B6478"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={30}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#F0B429"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="predicted"
              stroke="#2DD4BF"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}