import { useState, type FormEvent } from "react";
import { useRecorder } from "../hooks/useRecorder";

interface Props {
  disabled: boolean;
  onAudio: (clip: Blob) => void;
  onText: (text: string) => void;
}

/** Hold-to-talk microphone button, with a text box that always works. */
export function Composer({ disabled, onAudio, onText }: Props) {
  const { status, error, start, stop } = useRecorder();
  const [text, setText] = useState("");

  async function release() {
    const clip = await stop();
    if (clip) onAudio(clip);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    onText(text.trim());
    setText("");
  }

  const recording = status === "recording";
  return (
    <div className="composer">
      <button
        type="button"
        className={`btn ptt ${recording ? "recording" : ""}`}
        disabled={disabled}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture?.(e.pointerId);
          void start();
        }}
        onPointerUp={() => void release()}
        onPointerCancel={() => void release()}
        onKeyDown={(e) => {
          if ((e.key === " " || e.key === "Enter") && !e.repeat) {
            e.preventDefault();
            void start();
          }
        }}
        onKeyUp={(e) => {
          if (e.key === " " || e.key === "Enter") void release();
        }}
      >
        {recording ? "Listening… release to send" : status === "starting" ? "Starting mic…" : "Hold to talk"}
      </button>
      {error && (
        <p className="mic-error" role="alert">
          {error}
        </p>
      )}
      <form className="text-input" onSubmit={submit}>
        <input
          aria-label="Type a message"
          placeholder="…or type here"
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
        />
        <button className="btn" type="submit" disabled={disabled || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
