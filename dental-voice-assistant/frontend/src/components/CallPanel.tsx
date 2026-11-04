import React, { useState, useRef, useEffect } from "react";
import type { CallStatus, TranscriptItem } from "../types";

interface CallPanelProps {
  status: CallStatus;
  transcript: TranscriptItem[];
  isRecording: boolean;
  isPlayingAudio: boolean;
  error: string | null;
  startCall: () => void;
  endCall: () => void;
  sendText: (text: string) => void;
  startRecording: () => void;
  stopRecording: () => void;
}

const QUICK_PROMPTS = [
  "Book a cleaning tomorrow at 10 AM",
  "I want to book an appointment",
  "Sara Khan",
  "0300-1234567",
  "Yes, confirm it",
  "Cancel my appointment",
  "Reschedule my appointment",
  "What services do you offer?",
  "Goodbye",
];

export function CallPanel({
  status,
  transcript,
  isRecording,
  isPlayingAudio,
  error,
  startCall,
  endCall,
  sendText,
  startRecording,
  stopRecording,
}: CallPanelProps) {
  const [inputText, setInputText] = useState("");
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const handleSend = () => {
    if (inputText.trim()) {
      sendText(inputText.trim());
      setInputText("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  return (
    <div className="call-panel card">
      <div className="panel-header">
        <div className="clinic-title-row">
          <div className="logo-icon">🦷</div>
          <div>
            <h2>BrightSmile Dental Assistant</h2>
            <p className="subtitle">Real-time Rule-Based Voice Agent (Deterministic FSM)</p>
          </div>
        </div>

        <div className="status-badges">
          <span className={`status-pill ${status}`}>
            <span className="dot" />
            {status === "idle" && "Ready to Call"}
            {status === "connecting" && "Connecting..."}
            {status === "connected" && (isPlayingAudio ? "Speaking 🔊" : isRecording ? "Listening 🎙️" : "Call Active")}
          </span>
        </div>
      </div>

      {error && <div className="error-banner">⚠️ {error}</div>}

      <div className="transcript-container">
        {transcript.length === 0 ? (
          <div className="empty-transcript">
            <div className="empty-icon">📞</div>
            <h3>No Active Call</h3>
            <p>Click <strong>Start Call</strong> to initiate a session with the BrightSmile Voice Assistant.</p>
            <p className="hint">You can speak by holding the microphone button or type your message below.</p>
          </div>
        ) : (
          transcript.map((item) => (
            <div key={item.id} className={`message-bubble ${item.speaker}`}>
              <div className="bubble-avatar">
                {item.speaker === "assistant" ? "🤖" : "👤"}
              </div>
              <div className="bubble-content">
                <div className="bubble-meta">
                  <span className="speaker-name">
                    {item.speaker === "assistant" ? "BrightSmile AI" : "Caller"}
                  </span>
                  <span className="timestamp">{item.timestamp}</span>
                  {item.state && <span className="state-tag">{item.state}</span>}
                </div>
                <div className="message-text">{item.text}</div>
                {item.timings && (
                  <div className="timing-note">
                    ⏱️ Total: {Math.round(item.timings.total_ms)}ms (NLU: {Math.round(item.timings.brain_ms)}ms, TTS: {Math.round(item.timings.tts_ms)}ms)
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={transcriptEndRef} />
      </div>

      {status !== "idle" && (
        <div className="quick-prompts-row">
          <span className="prompts-label">Quick Prompts:</span>
          <div className="prompts-scroll">
            {QUICK_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                className="chip-btn"
                onClick={() => sendText(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="call-controls">
        {status === "idle" ? (
          <button type="button" className="btn btn-primary start-btn" onClick={startCall}>
            <span className="btn-icon">📞</span> Start Call
          </button>
        ) : (
          <>
            <button
              type="button"
              className={`btn push-to-talk-btn ${isRecording ? "recording" : ""}`}
              onMouseDown={startRecording}
              onMouseUp={stopRecording}
              onTouchStart={startRecording}
              onTouchEnd={stopRecording}
              title={status !== "connected" ? "Waiting for call to connect..." : "Click and hold to speak"}
              disabled={status !== "connected"}
            >
              <span className="btn-icon">{isRecording ? "🔴" : "🎙️"}</span>
              {status !== "connected"
                ? "Connecting..."
                : isRecording
                ? "Listening... (Release to send)"
                : "Hold to Speak"}
            </button>

            <div className="text-input-group">
              <input
                type="text"
                placeholder="Or type what caller says..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={status === "connecting"}
              />
              <button
                type="button"
                className="btn btn-secondary send-btn"
                onClick={handleSend}
                disabled={!inputText.trim()}
              >
                Send
              </button>
            </div>

            <button type="button" className="btn btn-danger end-btn" onClick={endCall}>
              <span className="btn-icon">📵</span> Hang Up
            </button>
          </>
        )}
      </div>
    </div>
  );
}
