"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Mic,
  MicOff,
  PhoneOff,
  Phone,
  RotateCcw,
  Volume2,
  VolumeX,
  AlertCircle,
  Loader2,
  Brain,
  PhoneCall,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  postChat,
  postReset,
  type ChatResponse,
} from "@/lib/api";
import {
  isSttSupported,
  isTtsSupported,
  recognizeOnce,
  speak,
  stopSpeaking,
} from "@/lib/voice";

type Turn = {
  id: number;
  callerText: string;
  callerInterim?: string;
  response?: ChatResponse;
  pending?: boolean;
  error?: string;
};

const STATE_LABELS: Record<string, { label: string; color: string }> = {
  greeting: { label: "Greeting", color: "bg-slate-500" },
  ask_date: { label: "Asking: Date", color: "bg-amber-500" },
  ask_time: { label: "Asking: Time", color: "bg-amber-500" },
  ask_party_size: { label: "Asking: Party Size", color: "bg-amber-500" },
  check_availability: { label: "Checking Availability", color: "bg-blue-500" },
  ask_name: { label: "Asking: Name", color: "bg-amber-500" },
  ask_phone: { label: "Asking: Phone", color: "bg-amber-500" },
  confirm: { label: "Confirming", color: "bg-purple-500" },
  booked: { label: "Booked", color: "bg-emerald-500" },
  cancelled: { label: "Cancelled", color: "bg-rose-500" },
  goodbye: { label: "Goodbye", color: "bg-slate-500" },
};

export function VoiceAssistant() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  const [lastDecision, setLastDecision] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [callActive, setCallActive] = useState(false);
  const turnIdRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // ---- Auto-scroll to bottom on new turns ----
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns, speaking, thinking]);

  // ---- Start a fresh session on mount ----
  const initialize = useCallback(async () => {
    try {
      setError(null);
      const r = await postReset();
      setSessionId(r.session_id);
      setTurns([
        {
          id: ++turnIdRef.current,
          callerText: "",
          response: {
            session_id: r.session_id,
            text: r.last_prompt,
            state: r.state,
            slots: r.slots as ChatResponse["slots"],
            intent: "system",
            decision: "greeting",
            end_call: false,
            booking_id: null,
            history: [],
          },
        },
      ]);
      setLastDecision(null);
      setCallActive(true);
      if (!muted && isTtsSupported()) {
        setSpeaking(true);
        await speak(r.last_prompt);
        setSpeaking(false);
      }
    } catch (e) {
      setError(`Could not reach the backend. Is the Python server running on port 8000? (${(e as Error).message})`);
    }
  }, [muted]);

  useEffect(() => {
    initialize();
  }, [initialize]);

  // ---- Handle a caller utterance ----
  const handleUserText = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim()) return;
      const myTurnId = ++turnIdRef.current;
      setTurns((prev) => [
        ...prev,
        { id: myTurnId, callerText: text, pending: true },
      ]);
      setThinking(true);
      try {
        const resp = await postChat(sessionId, text);
        setTurns((prev) =>
          prev.map((t) => (t.id === myTurnId ? { ...t, response: resp, pending: false } : t)),
        );
        setLastDecision(resp);
        setThinking(false);
        if (!muted && isTtsSupported() && resp.text) {
          setSpeaking(true);
          await speak(resp.text);
          setSpeaking(false);
        }
        if (resp.end_call) {
          setCallActive(false);
        }
      } catch (e) {
        setThinking(false);
        setTurns((prev) =>
          prev.map((t) =>
            t.id === myTurnId
              ? { ...t, pending: false, error: (e as Error).message }
              : t,
          ),
        );
        setError((e as Error).message);
      }
    },
    [sessionId, muted],
  );

  // ---- Push to talk ----
  const onMicClick = useCallback(async () => {
    if (listening || thinking || speaking) return;
    if (!isSttSupported()) {
      setError(
        "Your browser does not support speech recognition. Try Chrome, Edge, or Safari.",
      );
      return;
    }
    setError(null);
    setListening(true);
    stopSpeaking();
    const myTurnId = ++turnIdRef.current;
    setTurns((prev) => [
      ...prev,
      { id: myTurnId, callerText: "", callerInterim: "", pending: true },
    ]);
    try {
      const text = await recognizeOnce((interim) => {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === myTurnId ? { ...t, callerInterim: interim } : t,
          ),
        );
      });
      setListening(false);
      if (!text.trim()) {
        // Remove the empty turn
        setTurns((prev) => prev.filter((t) => t.id !== myTurnId));
        return;
      }
      // Finalize the caller text in the turn, then send to brain
      setTurns((prev) =>
        prev.map((t) =>
          t.id === myTurnId ? { ...t, callerText: text, callerInterim: undefined } : t,
        ),
      );
      await handleUserText(text);
    } catch (e) {
      setListening(false);
      setTurns((prev) => prev.filter((t) => t.id !== myTurnId));
      setError((e as Error).message);
    }
  }, [listening, thinking, speaking, handleUserText]);

  // ---- Text input fallback (when no mic available) ----
  const [textInput, setTextInput] = useState("");
  const onTextSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!textInput.trim()) return;
      const text = textInput.trim();
      setTextInput("");
      await handleUserText(text);
    },
    [textInput, handleUserText],
  );

  const onEndCall = useCallback(() => {
    stopSpeaking();
    setSpeaking(false);
    setListening(false);
    setCallActive(false);
  }, []);

  const onToggleMute = useCallback(() => {
    if (!muted) {
      stopSpeaking();
      setSpeaking(false);
    }
    setMuted((m) => !m);
  }, [muted]);

  const onReset = useCallback(() => {
    stopSpeaking();
    setSpeaking(false);
    setListening(false);
    setThinking(false);
    initialize();
  }, [initialize]);

  const stateInfo = lastDecision
    ? STATE_LABELS[lastDecision.state] ?? { label: lastDecision.state, color: "bg-slate-500" }
    : STATE_LABELS.greeting;

  const statusText = listening
    ? "Listening…"
    : thinking
      ? "Thinking…"
      : speaking
        ? "Speaking…"
        : callActive
          ? "Tap the mic and speak"
          : "Call ended";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-orange-50 to-amber-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="container mx-auto max-w-7xl px-4 py-6 lg:py-10">
        {/* Header */}
        <header className="mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 text-sm font-medium">
              <PhoneCall className="size-4" />
              <span>The Copper Spoon · Reservations</span>
            </div>
            <h1 className="mt-1 text-3xl lg:text-4xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
              Voice Booking Assistant
            </h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 max-w-2xl">
              A rule-based voice agent that books restaurant tables over the phone.
              The brain is hand-written Python — no LLM. Speech-to-text and
              text-to-speech use your browser&apos;s Web Speech API.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onToggleMute}
              aria-label={muted ? "Unmute" : "Mute"}
            >
              {muted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
              {muted ? "Muted" : "Sound on"}
            </Button>
            <Button variant="outline" size="sm" onClick={onReset}>
              <RotateCcw className="size-4" /> Restart
            </Button>
          </div>
        </header>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-300 bg-rose-50 dark:bg-rose-950/40 dark:border-rose-800 p-3 text-sm text-rose-800 dark:text-rose-200 flex items-start gap-2">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Conversation panel (2/3) */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="h-[60vh] lg:h-[65vh] flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">Conversation</CardTitle>
                  <Badge variant={callActive ? "default" : "secondary"}>
                    {callActive ? "Live" : "Ended"}
                  </Badge>
                </div>
              </CardHeader>
              <Separator />
              <CardContent className="flex-1 overflow-hidden p-0">
                <div ref={scrollRef} className="h-full overflow-y-auto p-4 space-y-3">
                  {turns.map((turn) => (
                    <ConversationBubble key={turn.id} turn={turn} />
                  ))}
                  {turns.length === 0 && (
                    <div className="text-center text-sm text-slate-500 mt-12">
                      Tap the mic below to start talking to the assistant.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Mic + status */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-col items-center gap-3">
                  <button
                    onClick={onMicClick}
                    disabled={!callActive || listening || thinking || speaking}
                    aria-label="Push to talk"
                    className={cn(
                      "relative size-20 rounded-full flex items-center justify-center transition-all outline-none",
                      "focus-visible:ring-4 focus-visible:ring-amber-300/50",
                      "disabled:opacity-40 disabled:cursor-not-allowed",
                      listening
                        ? "bg-rose-500 text-white shadow-lg shadow-rose-500/40"
                        : "bg-amber-500 text-white shadow-lg shadow-amber-500/40 hover:bg-amber-600",
                    )}
                  >
                    {listening ? (
                      <>
                        <span className="absolute inset-0 rounded-full bg-rose-500 animate-ping opacity-60" />
                        <MicOff className="size-7 relative" />
                      </>
                    ) : thinking || speaking ? (
                      <Loader2 className="size-7 animate-spin" />
                    ) : (
                      <Mic className="size-7" />
                    )}
                  </button>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {statusText}
                  </div>

                  {/* Text fallback */}
                  <form onSubmit={onTextSubmit} className="w-full max-w-md flex gap-2 mt-2">
                    <input
                      type="text"
                      value={textInput}
                      onChange={(e) => setTextInput(e.target.value)}
                      placeholder="…or type your reply"
                      disabled={!callActive || thinking}
                      className="flex-1 px-3 py-2 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
                    />
                    <Button type="submit" size="sm" disabled={!callActive || !textInput.trim()}>
                      Send
                    </Button>
                  </form>

                  {callActive && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onEndCall}
                      className="text-rose-600 hover:text-rose-700"
                    >
                      <PhoneOff className="size-4" /> End call
                    </Button>
                  )}
                  {!callActive && (
                    <Button variant="default" size="sm" onClick={onReset}>
                      <Phone className="size-4" /> New call
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Brain panel (1/3) */}
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Brain className="size-4 text-amber-600" />
                  <CardTitle className="text-lg">Brain Decision</CardTitle>
                </div>
              </CardHeader>
              <Separator />
              <CardContent className="p-4 space-y-4">
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">
                    Current state
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={cn("size-3 rounded-full", stateInfo.color)} />
                    <span className="text-base font-medium">
                      {stateInfo.label}
                    </span>
                  </div>
                </div>

                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">
                    Last decision
                  </div>
                  {lastDecision ? (
                    <div className="space-y-1 text-sm">
                      <div>
                        <span className="text-slate-500">Intent detected:</span>{" "}
                        <code className="text-amber-700 dark:text-amber-300">
                          {lastDecision.intent}
                        </code>
                      </div>
                      <div>
                        <span className="text-slate-500">Brain action:</span>{" "}
                        <code className="text-amber-700 dark:text-amber-300">
                          {lastDecision.decision}
                        </code>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-slate-400">No turns yet.</div>
                  )}
                </div>

                {lastDecision?.booking_id && (
                  <div className="rounded-md bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 p-3">
                    <div className="text-xs uppercase tracking-wide text-emerald-700 dark:text-emerald-400 mb-1">
                      Booking confirmed
                    </div>
                    <div className="font-mono text-sm">
                      {lastDecision.booking_id}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Slots</CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="p-4">
                <SlotGrid slots={lastDecision?.slots ?? null} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Try saying</CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="p-4 space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <PromptExamples />
              </CardContent>
            </Card>
          </div>
        </div>

        <footer className="mt-8 pt-4 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 text-center">
          Backend: Python FastAPI on port 8000 · Frontend: Next.js · STT/TTS: Web Speech API · Brain: 100% rule-based (no LLM)
        </footer>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function ConversationBubble({ turn }: { turn: Turn }) {
  // Assistant-only bubble (no caller text yet — system greeting)
  if (!turn.callerText && turn.response) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-2.5 text-sm">
          <div className="text-xs text-amber-600 dark:text-amber-400 font-medium mb-1">
            Assistant
          </div>
          <div className="text-slate-800 dark:text-slate-100">{turn.response.text}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Caller bubble */}
      {turn.callerText && (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-amber-500 text-white px-4 py-2.5 text-sm">
            <div className="text-xs text-amber-100 font-medium mb-1">You</div>
            <div>{turn.callerText}</div>
          </div>
        </div>
      )}
      {/* Interim transcript while listening */}
      {turn.callerInterim && !turn.callerText && (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-amber-200 text-amber-900 px-4 py-2.5 text-sm italic">
            <div className="text-xs text-amber-700 font-medium mb-1">Listening…</div>
            <div>{turn.callerInterim}</div>
          </div>
        </div>
      )}
      {/* Error */}
      {turn.error && (
        <div className="text-xs text-rose-600 text-right pr-1">{turn.error}</div>
      )}
      {/* Assistant reply */}
      {turn.response && (
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-2.5 text-sm">
            <div className="text-xs text-amber-600 dark:text-amber-400 font-medium mb-1 flex items-center gap-1">
              Assistant
              <span className="text-[10px] text-slate-400 font-normal">
                · {turn.response.decision}
              </span>
            </div>
            <div className="text-slate-800 dark:text-slate-100">{turn.response.text}</div>
          </div>
        </div>
      )}
      {/* Pending */}
      {turn.pending && !turn.response && (
        <div className="flex justify-start">
          <div className="rounded-2xl rounded-tl-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-3 text-sm">
            <Loader2 className="size-3.5 animate-spin text-slate-400" />
          </div>
        </div>
      )}
    </div>
  );
}

function SlotGrid({ slots }: { slots: ChatResponse["slots"] | null }) {
  const rows: Array<{ key: string; label: string; value: string | null }> = [
    { key: "date", label: "Date", value: slots?.date ?? null },
    { key: "time", label: "Time", value: slots?.time ?? null },
    { key: "party_size", label: "Party size", value: slots?.party_size?.toString() ?? null },
    { key: "name", label: "Name", value: slots?.name ?? null },
    { key: "phone", label: "Phone", value: slots?.phone ?? null },
  ];
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center justify-between text-sm">
          <span className="text-slate-500">{r.label}</span>
          {r.value ? (
            <code className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs">
              {r.value}
            </code>
          ) : (
            <span className="text-slate-300 dark:text-slate-600 text-xs">—</span>
          )}
        </div>
      ))}
    </div>
  );
}

function PromptExamples() {
  const examples = [
    "Hi, I'd like to book a table",
    "Tomorrow at 7pm for 4 people",
    "Friday at 8 for 2",
    "Actually change the time to 6:30",
    "What are your hours?",
    "Can you repeat that?",
    "Cancel",
  ];
  return (
    <ul className="space-y-1.5">
      {examples.map((ex) => (
        <li key={ex} className="italic">&ldquo;{ex}&rdquo;</li>
      ))}
    </ul>
  );
}
