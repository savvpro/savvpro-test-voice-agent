interface Props {
  active: boolean;
  busy: boolean;
  onStart: () => void;
  onEnd: () => void;
}

export function CallControls({ active, busy, onStart, onEnd }: Props) {
  return (
    <div className="call-controls">
      {active ? (
        <button className="btn btn-end" onClick={onEnd}>
          End call
        </button>
      ) : (
        <button className="btn btn-start" onClick={onStart} disabled={busy}>
          {busy ? "Connecting…" : "Start call"}
        </button>
      )}
      <span className={`call-status ${active ? "live" : ""}`}>{active ? "On call" : "Not connected"}</span>
    </div>
  );
}
