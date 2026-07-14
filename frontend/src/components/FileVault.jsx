import { useEffect, useState } from "react";
import { Lock, Unlock, Save, ShieldCheck, FolderLock } from "lucide-react";
import { files, ApiError } from "../api";

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileVault() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [path, setPath] = useState("");
  const [actionState, setActionState] = useState({ busy: false, message: null, isError: false });

  async function refresh() {
    try {
      const data = await files.list();
      setRecords(data);
    } catch {
      // Non-fatal -- vault list is best-effort on a dashboard tile.
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function runAction(actionFn, label) {
    if (!path.trim()) {
      setActionState({ busy: false, message: "Enter a file path first.", isError: true });
      return;
    }
    setActionState({ busy: true, message: null, isError: false });
    try {
      await actionFn(path.trim());
      setActionState({ busy: false, message: `${label} succeeded.`, isError: false });
      setPath("");
      await refresh();
    } catch (err) {
      const isAuthError = err instanceof ApiError && err.status === 401;
      setActionState({
        busy: false,
        message: isAuthError ? "Login required to perform this action." : err.message,
        isError: true,
      });
    }
  }

  return (
    <div className="panel flex flex-col h-full p-4">
      <div className="flex items-center gap-2 mb-3">
        <FolderLock size={16} className="text-ink-secondary" />
        <h2 className="font-display text-sm font-semibold text-ink-primary">File Vault</h2>
      </div>

      <div className="flex gap-2 mb-2">
        <input
          type="text"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="/path/to/file.pdf"
          className="flex-1 bg-surface-raised border border-border rounded-lg px-3 py-1.5 text-sm font-mono text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-severity-suspicious"
        />
        <button
          onClick={() => runAction(files.backup, "Backup")}
          disabled={actionState.busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-raised border border-border text-ink-secondary hover:text-severity-normal hover:border-severity-normal/40 transition-colors disabled:opacity-40"
        >
          <Save size={13} /> Backup
        </button>
        <button
          onClick={() => runAction(files.encrypt, "Encryption")}
          disabled={actionState.busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-raised border border-border text-ink-secondary hover:text-severity-suspicious hover:border-severity-suspicious/40 transition-colors disabled:opacity-40"
        >
          <Lock size={13} /> Encrypt
        </button>
      </div>

      {actionState.message && (
        <p className={`text-xs mb-2 ${actionState.isError ? "text-severity-critical" : "text-severity-normal"}`}>
          {actionState.message}
        </p>
      )}

      <div className="flex-1 overflow-y-auto scrollbar-thin -mx-1">
        {loading ? (
          <p className="text-sm text-ink-muted px-1 py-4">Loading vault…</p>
        ) : records.length === 0 ? (
          <p className="text-sm text-ink-muted px-1 py-4">No tracked files yet. Back up or encrypt one above.</p>
        ) : (
          <ul className="space-y-1.5">
            {records.map((r) => (
              <li
                key={r.id}
                className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-surface-hover/40 transition-colors"
              >
                {r.is_encrypted ? (
                  <Lock size={13} className="text-severity-suspicious shrink-0" />
                ) : (
                  <Unlock size={13} className="text-ink-muted shrink-0" />
                )}
                <span className="text-xs font-mono text-ink-primary truncate flex-1" title={r.original_path}>
                  {r.original_path.split("/").pop()}
                </span>
                {r.backup_path && <ShieldCheck size={13} className="text-severity-normal shrink-0" title="Backed up" />}
                <span className="text-[11px] text-ink-muted shrink-0">{formatBytes(r.size_bytes)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}