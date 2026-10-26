// Mirrors backend/app/schemas.py and app/nlu/pipeline.py.

export type Role = "caller" | "agent";

export interface Alternative {
  intent: string;
  confidence: number;
}

export interface TimeOfDay {
  label: string;
  start: string;
  end: string;
}

export interface Entities {
  date: string | null;
  time: string | null;
  time_of_day: TimeOfDay | null;
  department: string | null;
  unknown_department: string | null;
  doctor: string | null;
  patient_name: string | null;
  phone: string | null;
  booking_ref: string | null;
}

export interface NLUResult {
  text: string;
  normalized_text: string;
  intent: string;
  confidence: number;
  source: "rule" | "ml" | "fuzzy" | "context" | "fallback";
  entities: Entities;
  alternatives: Alternative[];
  rule_pattern: string | null;
}

export interface SlotOption {
  slot_id: number;
  start: string;
  doctor: string;
  department: string;
}

export interface Frame {
  state: string;
  task: string | null;
  department: string | null;
  doctor: string | null;
  date: string | null;
  time: string | null;
  time_of_day: TimeOfDay | null;
  patient_name: string | null;
  phone: string | null;
  booking_ref: string | null;
  candidate_slots: SlotOption[];
  chosen_slot: SlotOption | null;
  expected_slot: string | null;
  [key: string]: unknown;
}

export interface Decision {
  state: string;
  action: string | null;
  frame: Frame;
  end_call: boolean;
  expected_slot: string | null;
}

export interface Timings {
  stt: number;
  nlu: number;
  dm: number;
  tts: number;
}

export interface TurnResponse {
  session_id: string;
  transcript: string | null;
  transcript_confidence: number | null;
  nlu: NLUResult | null;
  decision: Decision;
  reply_text: string;
  audio_base64: string | null;
  audio_mime: string | null;
  timings_ms: Timings;
}

export interface Appointment {
  booking_ref: string;
  patient_name: string;
  phone: string;
  start: string;
  doctor: string;
  department: string;
  status: string;
}
