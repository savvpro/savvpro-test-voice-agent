import { useState, useEffect, useRef, useCallback } from "react";
import type { CallStatus, ServerMessage, TranscriptItem, TurnMessage } from "../types";

export function useCall(
  onAudioReceived?: (base64: string, mime: string) => void,
  onTurnComplete?: (turn: TurnMessage) => void
) {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [latestTurn, setLatestTurn] = useState<TurnMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const startCall = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus("connecting");
    setError(null);
    setTranscript([]);
    setLatestTurn(null);

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // If running with Vite dev server (port 5173), Vite proxy routes /ws to backend ws://localhost:8000
    const wsUrl = `${protocol}//${host}/ws/calls`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg: ServerMessage = JSON.parse(event.data);
        if (msg.type === "turn") {
          setLatestTurn(msg);

          // Add user text if it was transcribed or echoed
          if (msg.user_text && msg.user_text.trim()) {
            setTranscript((prev) => [
              ...prev,
              {
                id: `u-${msg.turn}-${Date.now()}`,
                turn: msg.turn,
                speaker: "user",
                text: msg.user_text,
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          }

          // Add assistant reply
          if (msg.reply_text) {
            setTranscript((prev) => [
              ...prev,
              {
                id: `a-${msg.turn}-${Date.now()}`,
                turn: msg.turn,
                speaker: "assistant",
                text: msg.reply_text,
                timestamp: new Date().toLocaleTimeString(),
                timings: msg.timings,
                state: msg.state,
              },
            ]);
          }

          // Enqueue audio
          if (msg.audio) {
            onAudioReceived?.(msg.audio, msg.audio_mime || "audio/mpeg");
          }

          onTurnComplete?.(msg);

          if (msg.end_call) {
            setStatus("idle");
          }
        } else if (msg.type === "call_ended") {
          setStatus("idle");
        } else if (msg.type === "error") {
          setError(`${msg.error}: ${msg.detail}`);
        }
      } catch (err) {
        console.error("Failed to parse WebSocket JSON message:", err);
      }
    };

    ws.onerror = (e) => {
      console.warn("WebSocket error:", e);
      setError("WebSocket connection failed. Ensure the backend server is running on port 8000.");
      setStatus("idle");
    };

    ws.onclose = () => {
      setStatus("idle");
      wsRef.current = null;
    };
  }, [onAudioReceived, onTurnComplete]);

  const endCall = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: "end" }));
      } catch (e) {
        console.warn("Failed to send end frame:", e);
      }
      wsRef.current.close(1000, "user_hangup");
    }
    setStatus("idle");
    wsRef.current = null;
  }, []);

  const sendText = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError("Call is not connected.");
        return;
      }
      const trimmed = text.trim();
      if (!trimmed) return;

      // Send JSON frame
      wsRef.current.send(JSON.stringify({ type: "user_text", text: trimmed }));
    },
    []
  );

  const sendAudio = useCallback(async (audioData: Blob | ArrayBuffer) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError("Call is not connected.");
      return;
    }

    try {
      if (audioData instanceof Blob) {
        const buffer = await audioData.arrayBuffer();
        wsRef.current.send(buffer);
      } else {
        wsRef.current.send(audioData);
      }
    } catch (err: any) {
      console.error("Failed to send audio bytes:", err);
      setError("Failed to stream audio frame to server.");
    }
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    status,
    transcript,
    latestTurn,
    error,
    startCall,
    endCall,
    sendText,
    sendAudio,
  };
}
