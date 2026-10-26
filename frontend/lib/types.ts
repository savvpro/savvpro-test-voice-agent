export type Entities = {
  service: string | null;
  date: string | null;
  time: string | null;
  name: string | null;
  reference: string | null;
  period: string | null;
};
export type Decision = {
  intent: string;
  extracted_entities: Partial<Entities>;
  previous_state: string;
  current_state: string;
  matched_rule: string;
  explanation: string;
  next_action: string;
  missing_information: string[];
};
export type Appointment = {
  reference: string;
  service: string;
  service_name: string;
  customer_name: string;
  starts_at: string;
  ends_at: string;
  timezone: string;
  status: string;
  version: number;
};
export type Conversation = {
  id: string;
  state: string;
  current_intent: string;
  entities: Entities;
  missing_information: string[];
  rejected_fields: string[];
  proposed_action: string | null;
  last_committed_action: string | null;
  history: { role: "user" | "assistant"; text: string }[];
  last_decision: Decision | null;
  clarification_count: number;
  reply: string;
  appointment: Appointment | null;
  last_booking_reference: string | null;
  available_slots: string[];
  revision: number;
};
export type Business = {
  name: string;
  timezone: string;
  hours: string;
  currency: string;
  services: { id: string; name: string; minutes: number; price: number }[];
};
export type PendingTurn = {
  text: string;
  request_id: string;
  expected_revision: number;
};
