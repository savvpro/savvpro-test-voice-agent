export type CallStatus = "idle" | "connecting" | "connected" | "speaking" | "listening";

export interface TurnTimings {
  stt_ms: number;
  brain_ms: number;
  tts_ms: number;
  total_ms: number;
}

export interface TurnMessage {
  type: "turn";
  turn: number;
  user_text: string;
  reply_text: string;
  state: string;
  end_call: boolean;
  action?: string | null;
  slots?: Record<string, any> | null;
  audio?: string | null;
  audio_mime?: string;
  timings?: TurnTimings;
}

export interface ErrorMessage {
  type: "error";
  error: string;
  detail: string;
}

export interface CallEndedMessage {
  type: "call_ended";
  reason: "completed" | "idle_timeout" | "max_turns" | "user_hangup" | string;
}

export type ServerMessage = TurnMessage | ErrorMessage | CallEndedMessage;

export interface TranscriptItem {
  id: string;
  turn: number;
  speaker: "assistant" | "user";
  text: string;
  timestamp: string;
  timings?: TurnTimings;
  state?: string;
}

export interface Appointment {
  id: string;
  patient_name: string;
  patient_phone: string;
  service: string;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: string;
}

export interface ClinicInfo {
  name: string;
  open_hour: number;
  close_hour: number;
  slot_minutes: number;
  open_weekdays: number[];
  services: string[];
}

