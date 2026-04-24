import { useState } from "react";
import { useAlerts, useCreateAlert, useDeleteAlert } from "../api/client";
import { useOrbitShieldStore } from "../stores/orbitShieldStore";

export default function AlertConfigForm() {
  const open = useOrbitShieldStore((s) => s.alertModalOpen);
  const setOpen = useOrbitShieldStore((s) => s.setAlertModalOpen);
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
    <div className="os-scrim" onClick={() => setOpen(false)}>
      <div className="os-modal" onClick={(e) => e.stopPropagation()}>
        <div className="os-modal-head">
          <h2>Alert Configuration</h2>
          <button onClick={() => setOpen(false)} className="os-icon-btn" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="os-modal-body">
          <label className="os-modal-field">
            <span>Pc Threshold</span>
            <input
              type="text"
              className="os-input"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
            />
          </label>
          <label className="os-modal-field">
            <span>Watch NORAD IDs (comma-separated, optional)</span>
            <input
              type="text"
              className="os-input"
              placeholder="25544, 48274"
              value={noradIds}
              onChange={(e) => setNoradIds(e.target.value)}
            />
          </label>
          <label className="os-modal-field">
            <span>Email (optional)</span>
            <input
              type="email"
              className="os-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <button className="os-primary-btn" onClick={handleCreate}>
            Create Alert
          </button>
        </div>

        <div className="os-modal-alerts">
          <h3>Active Alerts</h3>
          {isLoading && (
            <div style={{ fontSize: 12, color: "var(--os-fg3)" }}>Loading…</div>
          )}
          {alerts?.length === 0 && (
            <div style={{ fontSize: 12, color: "var(--os-fg3)" }}>
              No alerts configured
            </div>
          )}
          {alerts?.map((a) => (
            <div key={a.id} className="os-alert-row">
              <div>
                <span>Pc ≥ {a.pc_threshold.toExponential(1)}</span>
                {a.watched_norad_ids && (
                  <span className="os-fg2 mono" style={{ marginLeft: 8 }}>
                    [{a.watched_norad_ids.join(", ")}]
                  </span>
                )}
              </div>
              <button
                className="os-danger-link"
                onClick={() => deleteAlert.mutate(a.id)}
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
