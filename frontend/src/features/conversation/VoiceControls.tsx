import { useState } from "react";
import { Icon } from "../../app/Icon";
import type { useSpeech } from "../../speech/useSpeech";

export function VoiceControls({
  speech,
  disabled,
}: {
  speech: ReturnType<typeof useSpeech>;
  disabled: boolean;
}) {
  const [consented, setConsented] = useState(false);
  const [notice, setNotice] = useState(false);
  return (
    <div className="voice-area">
      <div className="voice-controls">
        <button
          type="button"
          className={"talk-button " + (speech.listening ? "is-listening" : "")}
          disabled={disabled || !speech.supported || speech.transcribing}
          onClick={() => {
            if (speech.listening) speech.finish();
            else if (speech.speaking || speech.requesting) speech.stop();
            else if (consented) speech.start();
            else setNotice(true);
          }}
        >
          <Icon
            name={speech.listening || speech.requesting ? "stop" : "mic"}
            size={19}
          />
          {speech.transcribing
            ? "Transcribing…"
            : speech.requesting
              ? "Cancel microphone request"
              : speech.listening
                ? "Finish recording"
                : speech.speaking
                  ? "Stop reply"
                  : "Talk to the assistant"}
        </button>
        <div className="voice-secondary">
          <button
            type="button"
            className="icon-button"
            aria-label={
              speech.muted ? "Turn on spoken replies" : "Mute spoken replies"
            }
            title={
              speech.muted ? "Turn on spoken replies" : "Mute spoken replies"
            }
            disabled={!speech.synthesisSupported}
            onClick={speech.toggleMute}
          >
            <Icon name={speech.muted ? "mute" : "sound"} size={17} />
          </button>
          <button
            type="button"
            className="text-button"
            disabled={disabled || !speech.synthesisSupported}
            onClick={speech.replay}
          >
            Replay reply
          </button>
        </div>
      </div>
      {!speech.supported && (
        <p className="voice-hint">
          Microphone recording isn't available here. You can complete your
          search by typing below.
        </p>
      )}
      {speech.supported &&
        !speech.listening &&
        !speech.speaking &&
        !speech.transcribing &&
        !speech.requesting && (
          <p className="voice-hint">
            Speak naturally, then choose Finish recording. Up to 60 seconds ·
            English.
          </p>
        )}
      {speech.requesting && (
        <p className="voice-hint" role="status">
          Allow microphone access in your browser to start recording.
        </p>
      )}
      {speech.listening && (
        <div className="recording-line">
          <p className="listening-status" role="status">
            <span className="listening-bars" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
              <i />
            </span>
            Recording… tell me what you remember.
          </p>
          <button type="button" className="text-button" onClick={speech.stop}>
            Discard recording
          </button>
        </div>
      )}
      {speech.transcribing && (
        <div className="recording-line">
          <p className="voice-hint" role="status">
            Turning your recording into text…
          </p>
          <button type="button" className="text-button" onClick={speech.stop}>
            Cancel transcription
          </button>
        </div>
      )}
      {speech.speaking && (
        <p className="voice-hint" role="status">
          Reading the reply aloud. The microphone is off.
        </p>
      )}
      {notice && (
        <div className="microphone-notice">
          <p>
            Your recording is sent to Groq Whisper for transcription. Our app
            does not store audio. Use fictional details only.
          </p>
          <div>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setConsented(true);
                setNotice(false);
                speech.start();
              }}
            >
              Agree and start microphone
            </button>
            <button
              type="button"
              className="text-button"
              onClick={() => setNotice(false)}
            >
              Keep typing
            </button>
          </div>
        </div>
      )}
      {speech.error && (
        <p className="speech-error" role="alert">
          {speech.error}
        </p>
      )}
    </div>
  );
}
