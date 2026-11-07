import { useState, useRef, useCallback, useEffect } from "react";

/**
 * Hook that records user microphone audio while holding the button (push-to-talk).
 * On release (stop), the complete recorded audio blob is emitted to `onAudioBlob`.
 */
export function useRecorder(onAudioBlob: (blob: Blob) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const start = useCallback(async () => {
    try {
      setError(null);
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        throw new Error("Audio recording is not supported in this browser.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Select supported MIME type
      let mimeType = "audio/webm;codecs=opus";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : MediaRecorder.isTypeSupported("audio/mp4")
          ? "audio/mp4"
          : "";
      }

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        if (chunksRef.current.length > 0) {
          const mime = recorder.mimeType || "audio/webm";
          const finalBlob = new Blob(chunksRef.current, { type: mime });
          // Only send if audio contains actual data (avoids empty click jitter)
          if (finalBlob.size > 500) {
            onAudioBlob(finalBlob);
          }
          chunksRef.current = [];
        }
      };

      recorder.start(100);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err: any) {
      console.error("Failed to start recording:", err);
      setError(err?.message || "Microphone access denied");
      setIsRecording(false);
    }
  }, [onAudioBlob]);

  const stop = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return { isRecording, error, start, stop };
}
