import { useState } from "react";
import type { TurnMessage } from "../types";

interface DebugPanelProps {
  latestTurn: TurnMessage | null;
}

export function DebugPanel({ latestTurn }: DebugPanelProps) {
  const [showRaw, setShowRaw] = useState(false);

  if (!latestTurn) {
    return (
      <div className="debug-panel card">
        <div className="panel-title-bar">
          <h3>🧠 Brain State & NLU Inspector</h3>
          <span className="badge badge-neutral">Standby</span>
        </div>
        <p className="empty-state-text">Start a call to inspect real-time state machine transitions and slots.</p>
      </div>
    );
  }

  const { state, turn, slots, timings, action } = latestTurn;
  const slotEntries = slots ? Object.entries(slots) : [];

  return (
    <div className="debug-panel card">
      <div className="panel-title-bar">
        <h3>🧠 Brain State & NLU Inspector</h3>
        <span className="badge badge-accent">Turn {turn}</span>
      </div>

      <div className="debug-grid">
        <div className="debug-stat-box">
          <span className="stat-label">Current FSM State</span>
          <span className="state-badge-highlight">{state || "START"}</span>
        </div>

        {action && (
          <div className="debug-stat-box">
            <span className="stat-label">Action Executed</span>
            <span className="badge badge-success">{action}</span>
          </div>
        )}
      </div>

      {timings && (
        <div className="timings-section">
          <h4>Latency Breakdown</h4>
          <div className="timings-grid">
            <div className="timing-chip">
              <span className="timing-label">STT (Whisper)</span>
              <span className="timing-value">{Math.round(timings.stt_ms)} ms</span>
            </div>
            <div className="timing-chip">
              <span className="timing-label">Brain (FSM NLU)</span>
              <span className="timing-value highlight-fast">{Math.round(timings.brain_ms)} ms</span>
            </div>
            <div className="timing-chip">
              <span className="timing-label">TTS (Voice)</span>
              <span className="timing-value">{Math.round(timings.tts_ms)} ms</span>
            </div>
            <div className="timing-chip timing-total">
              <span className="timing-label">Round-Trip Total</span>
              <span className="timing-value">{Math.round(timings.total_ms)} ms</span>
            </div>
          </div>
        </div>
      )}

      <div className="slots-section">
        <h4>Extracted Context Slots</h4>
        {slotEntries.length === 0 ? (
          <p className="no-data">No slots populated yet.</p>
        ) : (
          <table className="slots-table">
            <thead>
              <tr>
                <th>Slot</th>
                <th>Extracted Value</th>
              </tr>
            </thead>
            <tbody>
              {slotEntries.map(([k, v]) => (
                <tr key={k}>
                  <td className="slot-key">{k}</td>
                  <td className="slot-val">{v !== null && v !== undefined ? String(v) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="raw-toggle-row">
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => setShowRaw((prev) => !prev)}
        >
          {showRaw ? "Hide Raw Frame JSON" : "View Raw Frame JSON"}
        </button>
      </div>

      {showRaw && (
        <pre className="raw-json-viewer">
          {JSON.stringify(latestTurn, null, 2)}
        </pre>
      )}
    </div>
  );
}

