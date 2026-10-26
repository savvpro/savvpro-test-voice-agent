import { useCallback, useEffect, useRef, useState } from "react";
import { ApiClient, ApiError } from "../../api/client";
import type { SessionView, TurnRequest } from "../../api/client";

export function useConversation(client: ApiClient) {
  const [session, setSession] = useState<SessionView | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [hasRetry, setHasRetry] = useState(false);
  const pending = useRef<TurnRequest | null>(null);
  const locked = useRef(false);
  const generation = useRef(0);

  const open = useCallback(async () => {
    const epoch = ++generation.current;
    setBusy(true);
    setError(null);
    try {
      const next = await client.open();
      if (generation.current === epoch) {
        setSession(next);
        pending.current = null;
        setHasRetry(false);
      }
    } catch (failure) {
      if (generation.current === epoch)
        setError(
          failure instanceof ApiError
            ? failure
            : new ApiError(
                0,
                "NETWORK_ERROR",
                "Unable to connect. Please try again.",
              ),
        );
    } finally {
      if (generation.current === epoch) setBusy(false);
    }
  }, [client]);

  const invalidate = useCallback(() => {
    generation.current++;
  }, []);
  useEffect(() => {
    let active = true;
    void client
      .open()
      .then((next) => {
        if (active) {
          setSession(next);
          setBusy(false);
        }
      })
      .catch((failure) => {
        if (active) {
          setError(
            failure instanceof ApiError
              ? failure
              : new ApiError(
                  0,
                  "NETWORK_ERROR",
                  "Unable to connect. Please try again.",
                ),
          );
          setBusy(false);
        }
      });
    return () => {
      active = false;
      invalidate();
    };
  }, [client, invalidate]);

  const deliver = useCallback(
    async (payload: TurnRequest) => {
      if (locked.current) return false;
      locked.current = true;
      const epoch = generation.current;
      pending.current = payload;
      setBusy(true);
      setError(null);
      try {
        const next = await client.send(payload);
        if (generation.current !== epoch) return false;
        setSession(next);
        pending.current = null;
        setHasRetry(false);
        return true;
      } catch (failure) {
        if (generation.current !== epoch) return false;
        const problem =
          failure instanceof ApiError
            ? failure
            : new ApiError(0, "NETWORK_ERROR", "Unable to send your message.");
        if (problem.status === 409) {
          try {
            setSession(await client.get());
          } catch {
            setSession(null);
          }
          pending.current = null;
          setHasRetry(false);
        } else if (problem.status === 401) {
          setSession(null);
          pending.current = null;
          setHasRetry(false);
        } else {
          setHasRetry(true);
        }
        setError(problem);
        return false;
      } finally {
        locked.current = false;
        if (generation.current === epoch) setBusy(false);
      }
    },
    [client],
  );

  const send = useCallback(
    (text: string) => {
      if (!session || !text.trim() || pending.current || locked.current)
        return Promise.resolve(false);
      return deliver({
        text: text.trim(),
        request_id: crypto.randomUUID(),
        expected_version: session.version,
      });
    },
    [session, deliver],
  );
  const retry = useCallback(
    () =>
      pending.current ? deliver(pending.current) : open().then(() => false),
    [deliver, open],
  );
  const erase = useCallback(async () => {
    if (locked.current) return;
    generation.current++;
    setBusy(true);
    setError(null);
    try {
      await client.erase();
      setSession(null);
      pending.current = null;
      setHasRetry(false);
      await open();
    } catch (failure) {
      setError(
        failure instanceof ApiError
          ? failure
          : new ApiError(
              0,
              "NETWORK_ERROR",
              "Unable to start a new conversation.",
            ),
      );
    } finally {
      setBusy(false);
    }
  }, [client, open]);
  return { session, busy, error, hasRetry, send, retry, open, erase };
}
