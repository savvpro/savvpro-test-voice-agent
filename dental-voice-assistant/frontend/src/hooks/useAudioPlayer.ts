import { useEffect, useRef, useState, useCallback } from "react";

export function useAudioPlayer() {
  const [isPlaying, setIsPlaying] = useState(false);
  const queueRef = useRef<Array<{ data: string; mime: string }>>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const playNext = useCallback(() => {
    if (queueRef.current.length === 0) {
      setIsPlaying(false);
      return;
    }

    const item = queueRef.current.shift();
    if (!item || !item.data) {
      playNext();
      return;
    }

    try {
      const mime = item.mime || "audio/mpeg";
      const src = `data:${mime};base64,${item.data}`;
      const audio = new Audio(src);
      audioRef.current = audio;
      setIsPlaying(true);

      audio.onended = () => {
        setIsPlaying(false);
        playNext();
      };

      audio.onerror = (e) => {
        console.warn("Audio playback error:", e);
        setIsPlaying(false);
        playNext();
      };

      audio.play().catch((err) => {
        console.warn("Audio autoplay blocked or failed:", err);
        setIsPlaying(false);
        playNext();
      });
    } catch (e) {
      console.error("Failed to construct audio element:", e);
      setIsPlaying(false);
      playNext();
    }
  }, []);

  const enqueue = useCallback(
    (base64Data: string, mimeType = "audio/mpeg") => {
      queueRef.current.push({ data: base64Data, mime: mimeType });
      if (!isPlaying) {
        playNext();
      }
    },
    [isPlaying, playNext]
  );

  const stop = useCallback(() => {
    queueRef.current = [];
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return { enqueue, stop, isPlaying };
}
