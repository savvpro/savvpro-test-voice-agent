"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Mic,
  MicOff,
  PhoneCall,
  PhoneOff,
  Volume2,
  VolumeX,
  Sparkles,
  Bot,
  User,
  Calendar,
  Clock,
  UserCheck,
  Stethoscope,
  FileText,
  Send,
  Radio,
  HelpCircle,
} from "lucide-react";
import confetti from "canvas-confetti";
import { FSMState, MessageItem, SlotData, AgentServerResponse } from "@/types/agent";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

export default function VoiceAgentApp() {
  const [isConnected, setIsConnected] = useState(false);
  const [isCalling, setIsCalling] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [currentState, setCurrentState] = useState<FSMState>("GREETING");
  const [slots, setSlots] = useState<SlotData>({});
  const [inputBuffer, setInputBuffer] = useState("");
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [volumeLevel, setVolumeLevel] = useState<number[]>(new Array(16).fill(10));

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      disconnectWebSocket();
      stopAudioAnalysis();
    };
  }, []);

  const playBase64Wav = useCallback((base64Wav: string) => {
    if (!ttsEnabled) return;
    try {
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }
      const audio = new Audio(`data:audio/wav;base64,${base64Wav}`);
      currentAudioRef.current = audio;
      setIsAgentSpeaking(true);

      audio.onended = () => {
        setIsAgentSpeaking(false);
      };
      audio.onerror = () => {
        setIsAgentSpeaking(false);
      };

      audio.play().catch((err) => {
        console.warn("Autoplay audio blocked or error:", err);
        setIsAgentSpeaking(false);
      });
    } catch (e) {
      console.error("Audio playback error:", e);
      setIsAgentSpeaking(false);
    }
  }, [ttsEnabled]);

  const handleServerMessage = useCallback((data: AgentServerResponse) => {
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // If there's caller transcription (from voice audio), append caller message if not already added
    if (data.transcription) {
      setMessages((prev) => [
        ...prev,
        {
          id: `caller-${Date.now()}`,
          sender: "caller",
          text: data.transcription!,
          timestamp: timeStr,
        },
      ]);
    }

    if (data.reply) {
      setMessages((prev) => [
        ...prev,
        {
          id: `agent-${Date.now()}`,
          sender: "agent",
          text: data.reply,
          timestamp: timeStr,
          fsmState: data.state,
        },
      ]);
    }

    if (data.state) {
      setCurrentState(data.state);
      if (data.state === "END" && data.slots?.date && data.slots?.time) {
        confetti({
          particleCount: 80,
          spread: 70,
          origin: { y: 0.6 },
        });
      }
    }

    if (data.slots) {
      setSlots(data.slots);
    }

    if (data.audio) {
      playBase64Wav(data.audio);
    }
  }, [playBase64Wav]);

  const connectWebSocket = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setIsCalling(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as AgentServerResponse;
          handleServerMessage(payload);
        } catch (e) {
          console.error("Failed to parse websocket message:", e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsCalling(false);
        setIsRecording(false);
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
    } catch (e) {
      console.error("Failed to connect websocket:", e);
    }
  }, [handleServerMessage]);

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    stopRecording();
    setIsConnected(false);
    setIsCalling(false);
  };

  const startAudioAnalysis = (stream: MediaStream) => {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateVolume = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);

        // Sample 16 frequency bands
        const bands: number[] = [];
        const step = Math.floor(dataArray.length / 16) || 1;
        for (let i = 0; i < 16; i++) {
          const val = dataArray[i * step] || 0;
          bands.push(Math.max(8, Math.min(val / 2.5, 42)));
        }
        setVolumeLevel(bands);
        animationFrameRef.current = requestAnimationFrame(updateVolume);
      };

      updateVolume();
    } catch (err) {
      console.warn("Could not start visualizer audio context:", err);
    }
  };

  const stopAudioAnalysis = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setVolumeLevel(new Array(16).fill(10));
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      alert("Microphone access is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });

      startAudioAnalysis(stream);

      // Prefer standard webm/opus or wav supported in browser
      const mimeTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/wav"];
      const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type)) || "";

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      const chunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stopAudioAnalysis();
        stream.getTracks().forEach((track) => track.stop());

        if (chunks.length === 0) return;
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/wav" });
        const arrayBuffer = await blob.arrayBuffer();

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(arrayBuffer);
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone permission denied or error:", err);
      alert("Please allow microphone permissions to talk with the agent.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const sendTextMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputBuffer.trim()) return;

    const text = inputBuffer.trim();
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Append user message immediately
    setMessages((prev) => [
      ...prev,
      {
        id: `caller-${Date.now()}`,
        sender: "caller",
        text,
        timestamp: timeStr,
      },
    ]);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ text }));
    }

    setInputBuffer("");
  };

  const startNewCall = () => {
    setMessages([]);
    setSlots({});
    setCurrentState("GREETING");
    if (isConnected) {
      disconnectWebSocket();
    }
    setTimeout(() => {
      connectWebSocket();
    }, 250);
  };

  const getStateBadge = (state: FSMState) => {
    const config: Record<FSMState, { label: string; color: string }> = {
      GREETING: { label: "Greeting", color: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30" },
      COLLECT_NAME: { label: "Collecting Name", color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
      COLLECT_DOCTOR: { label: "Selecting Doctor", color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30" },
      COLLECT_DATE: { label: "Selecting Date", color: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
      COLLECT_TIME: { label: "Selecting Time", color: "bg-orange-500/20 text-orange-300 border-orange-500/30" },
      COLLECT_REASON: { label: "Visit Reason", color: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
      CONFIRM: { label: "Confirmation", color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
      RESCHEDULE_LOOKUP: { label: "Reschedule Lookup", color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
      RESCHEDULE_COLLECT_DATE: { label: "Reschedule Date", color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
      RESCHEDULE_COLLECT_TIME: { label: "Reschedule Time", color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
      CANCEL_LOOKUP: { label: "Cancel Lookup", color: "bg-rose-500/20 text-rose-300 border-rose-500/30" },
      CANCEL_CONFIRM: { label: "Cancel Confirm", color: "bg-rose-500/20 text-rose-300 border-rose-500/30" },
      END: { label: "Call Completed", color: "bg-slate-500/20 text-slate-300 border-slate-500/30" },
    };
    const current = config[state] || { label: state, color: "bg-slate-500/20 text-slate-300 border-slate-500/30" };
    return (
      <span className={`px-2.5 py-1 text-xs font-semibold rounded-full border ${current.color}`}>
        {current.label}
      </span>
    );
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                City Dental Clinic
                <span className="text-[10px] font-medium tracking-normal px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Local AI Agent
                </span>
              </h1>
              <p className="text-xs text-slate-400">Intelligent Voice Receptionist (faster-whisper + Piper)</p>
            </div>
          </div>

          {/* Controls & Connection Indicator */}
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setTtsEnabled(!ttsEnabled)}
              title={ttsEnabled ? "Mute Voice (TTS)" : "Enable Voice (TTS)"}
              className={`p-2 rounded-lg border transition-all ${
                ttsEnabled
                  ? "bg-indigo-600/20 border-indigo-500/40 text-indigo-300 hover:bg-indigo-600/30"
                  : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              {ttsEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </button>

            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  isConnected ? "bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400" : "bg-slate-500"
                }`}
              />
              <span className="text-xs font-medium text-slate-300">
                {isConnected ? "WS Online (8000)" : "Disconnected"}
              </span>
            </div>

            {!isCalling ? (
              <button
                onClick={startNewCall}
                className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-medium text-sm shadow-lg shadow-emerald-600/25 transition-all transform active:scale-95"
              >
                <PhoneCall className="h-4 w-4" />
                <span>Start Call</span>
              </button>
            ) : (
              <button
                onClick={disconnectWebSocket}
                className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-gradient-to-r from-rose-600 to-red-500 hover:from-rose-500 hover:to-red-400 text-white font-medium text-sm shadow-lg shadow-rose-600/25 transition-all transform active:scale-95"
              >
                <PhoneOff className="h-4 w-4" />
                <span>Hang Up</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Layout */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual Agent Avatar & Interactive Mic Control */}
        <div className="lg:col-span-4 flex flex-col space-y-6">
          {/* Virtual Agent Call Card */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm flex flex-col items-center justify-center text-center relative overflow-hidden shadow-xl">
            <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 via-transparent to-transparent pointer-events-none" />

            {/* Glowing Avatar */}
            <div className="relative my-4">
              <div
                className={`h-32 w-32 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isAgentSpeaking
                    ? "bg-gradient-to-tr from-indigo-500 to-cyan-400 animate-pulse-ring"
                    : isRecording
                    ? "bg-gradient-to-tr from-rose-500 to-orange-400 animate-pulse-ring"
                    : "bg-slate-800 border-2 border-slate-700"
                }`}
              >
                <Bot
                  className={`h-16 w-16 transition-colors duration-300 ${
                    isAgentSpeaking ? "text-white" : isRecording ? "text-white" : "text-slate-400"
                  }`}
                />
              </div>

              {/* Status pill overlay */}
              <div className="absolute -bottom-2 left-1/2 -translate-x-1/2">
                {isAgentSpeaking ? (
                  <span className="px-3 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500 text-white shadow-md flex items-center gap-1.5 whitespace-nowrap">
                    <Radio className="h-3 w-3 animate-spin" /> Speaking
                  </span>
                ) : isRecording ? (
                  <span className="px-3 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500 text-white shadow-md flex items-center gap-1.5 whitespace-nowrap animate-pulse">
                    <Mic className="h-3 w-3" /> Listening...
                  </span>
                ) : isCalling ? (
                  <span className="px-3 py-0.5 rounded-full text-[11px] font-semibold bg-slate-700 text-slate-300 shadow-md">
                    Ready
                  </span>
                ) : (
                  <span className="px-3 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-500">
                    Idle
                  </span>
                )}
              </div>
            </div>

            <h3 className="mt-4 text-lg font-bold text-white">AI Dental Receptionist</h3>
            <p className="text-xs text-slate-400 max-w-xs mt-1">
              Natural conversation with correction detection and appointment scheduling.
            </p>

            {/* Audio Wave Visualizer */}
            <div className="h-12 flex items-center justify-center gap-1 mt-6 w-full px-4">
              {volumeLevel.map((height, i) => (
                <div
                  key={i}
                  style={{ height: `${height}px` }}
                  className={`w-1.5 rounded-full transition-all duration-75 ${
                    isRecording
                      ? "bg-gradient-to-t from-rose-500 to-orange-400"
                      : isAgentSpeaking
                      ? "bg-gradient-to-t from-indigo-500 to-cyan-400"
                      : "bg-slate-800"
                  }`}
                />
              ))}
            </div>

            {/* Mic Button: Press to Speak */}
            <div className="mt-4 w-full">
              {!isRecording ? (
                <button
                  disabled={!isCalling}
                  onClick={startRecording}
                  className={`w-full py-3.5 px-4 rounded-xl font-semibold text-sm flex items-center justify-center space-x-2 transition-all shadow-lg ${
                    isCalling
                      ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30 transform active:scale-[0.98]"
                      : "bg-slate-800 text-slate-500 cursor-not-allowed"
                  }`}
                >
                  <Mic className="h-5 w-5" />
                  <span>Push to Speak</span>
                </button>
              ) : (
                <button
                  onClick={stopRecording}
                  className="w-full py-3.5 px-4 rounded-xl font-semibold text-sm flex items-center justify-center space-x-2 bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30 transition-all transform active:scale-[0.98] animate-pulse"
                >
                  <MicOff className="h-5 w-5" />
                  <span>Release & Send Audio</span>
                </button>
              )}
              <p className="text-[11px] text-slate-500 mt-2">
                {isRecording ? "Click when finished speaking" : "Or type your responses below"}
              </p>
            </div>
          </div>

          {/* Slots & Extraction Live Inspector */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm shadow-xl flex flex-col space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                <FileText className="h-4 w-4 text-indigo-400" />
                Brain Slots Extracted
              </h4>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                {Object.keys(slots).length} / 5
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              {/* Name */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/40 border border-slate-800">
                <div className="flex items-center space-x-2 text-slate-400">
                  <UserCheck className="h-4 w-4 text-blue-400" />
                  <span>Patient Name</span>
                </div>
                <span className={`font-medium ${slots.name ? "text-blue-300" : "text-slate-600 italic"}`}>
                  {slots.name || "Pending..."}
                </span>
              </div>

              {/* Doctor */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/40 border border-slate-800">
                <div className="flex items-center space-x-2 text-slate-400">
                  <Stethoscope className="h-4 w-4 text-cyan-400" />
                  <span>Doctor</span>
                </div>
                <span className={`font-medium ${slots.doctor ? "text-cyan-300" : "text-slate-600 italic"}`}>
                  {slots.doctor || "Pending..."}
                </span>
              </div>

              {/* Date */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/40 border border-slate-800">
                <div className="flex items-center space-x-2 text-slate-400">
                  <Calendar className="h-4 w-4 text-amber-400" />
                  <span>Date</span>
                </div>
                <span className={`font-medium ${slots.date ? "text-amber-300" : "text-slate-600 italic"}`}>
                  {slots.date || "Pending..."}
                </span>
              </div>

              {/* Time */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/40 border border-slate-800">
                <div className="flex items-center space-x-2 text-slate-400">
                  <Clock className="h-4 w-4 text-orange-400" />
                  <span>Time</span>
                </div>
                <span className={`font-medium ${slots.time ? "text-orange-300" : "text-slate-600 italic"}`}>
                  {slots.time || "Pending..."}
                </span>
              </div>

              {/* Reason */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/40 border border-slate-800">
                <div className="flex items-center space-x-2 text-slate-400">
                  <HelpCircle className="h-4 w-4 text-purple-400" />
                  <span>Visit Reason</span>
                </div>
                <span className={`font-medium ${slots.reason ? "text-purple-300" : "text-slate-600 italic"}`}>
                  {slots.reason || "(Optional)"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Live Conversation & Decision Stream */}
        <div className="lg:col-span-8 flex flex-col space-y-4 h-[750px]">
          {/* State Machine Status Bar */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 backdrop-blur-sm flex items-center justify-between shadow-lg">
            <div className="flex items-center space-x-3">
              <span className="text-xs text-slate-400 font-medium">Current FSM State:</span>
              {getStateBadge(currentState)}
            </div>

            <div className="flex items-center space-x-2 text-xs text-slate-400">
              <span className="h-2 w-2 rounded-full bg-indigo-400" />
              <span>Correction-Aware Brain Active</span>
            </div>
          </div>

          {/* Conversation Feed */}
          <div className="flex-1 bg-slate-900/40 border border-slate-800/80 rounded-2xl p-4 overflow-y-auto backdrop-blur-sm flex flex-col space-y-4 shadow-xl">
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-3">
                <div className="h-14 w-14 rounded-2xl bg-slate-800/80 flex items-center justify-center">
                  <Bot className="h-7 w-7 text-slate-400" />
                </div>
                <p className="text-sm font-medium text-slate-400">Ready to start the call</p>
                <p className="text-xs max-w-sm">
                  Click <strong className="text-indigo-300">&quot;Start Call&quot;</strong> above to connect to the local Python
                  voice backend. You can speak with the mic or type messages below.
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex items-start gap-3 ${
                    msg.sender === "caller" ? "flex-row-reverse" : "flex-row"
                  }`}
                >
                  <div
                    className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                      msg.sender === "caller"
                        ? "bg-gradient-to-tr from-cyan-600 to-blue-500 text-white"
                        : "bg-gradient-to-tr from-indigo-600 to-purple-500 text-white shadow-md shadow-indigo-600/20"
                    }`}
                  >
                    {msg.sender === "caller" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>

                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-md ${
                      msg.sender === "caller"
                        ? "bg-blue-600/20 border border-blue-500/30 text-blue-50 rounded-tr-none"
                        : "bg-slate-800/90 border border-slate-700/60 text-slate-100 rounded-tl-none"
                    }`}
                  >
                    <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                    <div className="flex items-center justify-end space-x-2 mt-1.5 text-[10px] text-slate-400">
                      {msg.fsmState && (
                        <span className="font-mono text-indigo-300/80">{msg.fsmState}</span>
                      )}
                      <span>{msg.timestamp}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Shortcuts & Edge-Case Test Utterances */}
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-[11px] text-slate-400 self-center">Try prompt:</span>
            {[
              "I'd like to book an appointment",
              "Dr. Khan on Monday at 3pm",
              "Actually make it Tuesday instead",
              "Actually I'd prefer Dr. Smith",
              "Yes that sounds good",
            ].map((snippet) => (
              <button
                key={snippet}
                disabled={!isCalling}
                onClick={() => {
                  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: `caller-${Date.now()}`,
                        sender: "caller",
                        text: snippet,
                        timestamp: timeStr,
                      },
                    ]);
                    wsRef.current.send(JSON.stringify({ text: snippet }));
                  }
                }}
                className={`px-3 py-1.5 rounded-lg border text-left transition-all ${
                  isCalling
                    ? "bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-indigo-600/20 hover:border-indigo-500/40 hover:text-indigo-200"
                    : "bg-slate-900 border-slate-800 text-slate-600 cursor-not-allowed"
                }`}
              >
                &quot;{snippet}&quot;
              </button>
            ))}
          </div>

          {/* Text Input Fallback Bar */}
          <form onSubmit={sendTextMessage} className="flex gap-2">
            <input
              type="text"
              disabled={!isCalling}
              value={inputBuffer}
              onChange={(e) => setInputBuffer(e.target.value)}
              placeholder={isCalling ? "Type a response or correction..." : "Start the call first to speak or chat"}
              className="flex-1 bg-slate-900/90 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-900/40 disabled:text-slate-600"
            />
            <button
              type="submit"
              disabled={!isCalling || !inputBuffer.trim()}
              className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white font-medium text-sm transition-all flex items-center gap-1.5 shadow-lg shadow-indigo-600/20"
            >
              <Send className="h-4 w-4" />
              <span>Send</span>
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
