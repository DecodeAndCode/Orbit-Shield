import { useState } from "react";
import { useAlerts, useCreateAlert, useDeleteAlert } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";

export default function AlertConfigForm() {
  const open = useColliderStore((s) => s.alertModalOpen);
  const setOpen = useColliderStore((s) => s.setAlertModalOpen);
  const { data: alerts, isLoading } = useAlerts();
  const createAlert = useCreateAlert();
  const deleteAlert = useDeleteAlert();

  const [threshold, setThreshold] = useState("1e-4");
  const [noradIds, setNoradIds] = useState("");
  const [email, setEmail] = useState("");

  if (!open) return null;

  const handleCreate = () => {
    createAlert.mutate({
      watched_norad_ids: noradIds
        ? noradIds.split(",").map((s) => parseInt(s.trim(), 10))
        : null,
      pc_threshold: parseFloat(threshold),
      notification_channels: email ? { email } : null,
      enabled: true,
    });
    setThreshold("1e-4");
    setNoradIds("");
    setEmail("");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-[480px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-4 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Alert Configuration</h2>
          <button
            onClick={() => setOpen(false)}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            ✕
          </button>
        </div>

        <div className="p-4 space-y-3 border-b border-[var(--color-border)]">
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">
              Pc Threshold
            </label>
            <input
              type="text"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="w-full px-2 py-1 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">
              Watch NORAD IDs (comma-separated, optional)
            </label>
            <input
              type="text"
              value={noradIds}
              onChange={(e) => setNoradIds(e.target.value)}
              placeholder="25544, 48274"
              className="w-full px-2 py-1 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">
              Email (optional)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-2 py-1 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
            />
          </div>
          <button
            onClick={handleCreate}
            className="w-full py-1.5 text-sm rounded bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
          >
            Create Alert
          </button>
        </div>

        <div className="p-4 max-h-48 overflow-y-auto">
          <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-2">
            Active Alerts
          </h3>
          {isLoading && <div className="text-xs text-[var(--color-text-secondary)]">Loading...</div>}
          {alerts?.length === 0 && (
            <div className="text-xs text-[var(--color-text-secondary)]">No alerts configured</div>
          )}
          {alerts?.map((a) => (
            <div
              key={a.id}
              className="flex justify-between items-center py-1.5 border-b border-[var(--color-border)] last:border-0"
            >
              <div className="text-xs">
                <span>Pc ≥ {a.pc_threshold.toExponential(1)}</span>
                {a.watched_norad_ids && (
                  <span className="ml-2 text-[var(--color-text-secondary)]">
                    [{a.watched_norad_ids.join(", ")}]
                  </span>
                )}
              </div>
              <button
                onClick={() => deleteAlert.mutate(a.id)}
                className="text-xs text-[var(--color-risk-high)] hover:underline"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
