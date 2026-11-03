export interface SlotData {
  name?: string;
  doctor?: string;
  date?: string;
  time?: string;
  reason?: string;
  [key: string]: string | undefined;
}

export type FSMState =
  | "GREETING"
  | "COLLECT_NAME"
  | "COLLECT_DOCTOR"
  | "COLLECT_DATE"
  | "COLLECT_TIME"
  | "COLLECT_REASON"
  | "CONFIRM"
  | "RESCHEDULE_LOOKUP"
  | "RESCHEDULE_COLLECT_DATE"
  | "RESCHEDULE_COLLECT_TIME"
  | "CANCEL_LOOKUP"
  | "CANCEL_CONFIRM"
  | "END";

export interface MessageItem {
  id: string;
  sender: "agent" | "caller";
  text: string;
  timestamp: string;
  transcription?: string;
  fsmState?: FSMState;
}

export interface AgentServerResponse {
  type?: string;
  reply: string;
  state: FSMState;
  slots: SlotData;
  transcription?: string;
  audio?: string;
  audio_format?: string;
}
