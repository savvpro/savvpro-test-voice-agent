import type { PendingTurn } from "./types";

const SESSION_KEY = "voxdesk.session";
const PENDING_KEY = "voxdesk.pending";
const STORAGE_WARNING =
  "Browser storage is unavailable. You can continue in this tab; keep it open until pending messages are resolved.";

function validTurn(value: unknown): value is PendingTurn {
  if (!value || typeof value !== "object") return false;
  const turn = value as Partial<PendingTurn>;
  return (
    typeof turn.text === "string" &&
    turn.text.trim().length > 0 &&
    turn.text.length <= 1000 &&
    typeof turn.request_id === "string" &&
    /^[a-zA-Z0-9_-]{8,100}$/.test(turn.request_id) &&
    typeof turn.expected_revision === "number" &&
    Number.isInteger(turn.expected_revision) &&
    turn.expected_revision >= 0
  );
}

/** Storage improves reload recovery; failure must never lock the live tab. */
export function createSessionCache(report: (message: string) => void) {
  function read(key: string): string | null {
    try {
      return window.sessionStorage.getItem(key);
    } catch {
      report(STORAGE_WARNING);
      return null;
    }
  }
  function write(key: string, value: string | null) {
    try {
      if (value === null) window.sessionStorage.removeItem(key);
      else window.sessionStorage.setItem(key, value);
    } catch {
      report(STORAGE_WARNING);
    }
  }
  return {
    session: () => read(SESSION_KEY),
    rememberSession: (id: string) => write(SESSION_KEY, id),
    rememberPending: (sessionId: string, request: PendingTurn) =>
      write(PENDING_KEY, JSON.stringify({ sessionId, request })),
    clearPending: () => write(PENDING_KEY, null),
    pending(sessionId: string): PendingTurn | null {
      const raw = read(PENDING_KEY);
      if (!raw) return null;
      try {
        const value: unknown = JSON.parse(raw);
        if (
          value &&
          typeof value === "object" &&
          "sessionId" in value &&
          "request" in value
        ) {
          if (value.sessionId === sessionId && validTurn(value.request))
            return value.request;
        } else if (validTurn(value) && read(SESSION_KEY) === sessionId) {
          return value; // Validated cache format from earlier versions.
        }
      } catch {
        /* Report malformed data without attempting a request. */
      }
      write(PENDING_KEY, null);
      report(
        "Saved message data was invalid and has been cleared. Review the conversation before continuing.",
      );
      return null;
    },
  };
}
