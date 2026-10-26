import type { Slots } from "./api";

export const STATE_LABELS: Record<string, string> = {
  ask_service: "Asking for the treatment",
  ask_when: "Asking for day and time",
  offer_alternative: "Offering other slots",
  ask_patient: "Asking for the patient's name",
  ask_phone: "Asking for a phone number",
  confirm: "Waiting for confirmation",
  done: "Call finished",
};

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state;
}

export function slotRows(slots: Slots): { label: string; value: string | null }[] {
  return [
    { label: "Treatment", value: slots.service },
    { label: "Date", value: slots.date },
    { label: "Time", value: slots.time },
    { label: "Patient", value: slots.name },
    { label: "Phone", value: slots.phone },
  ];
}

export function filledCount(slots: Slots): number {
  return slotRows(slots).filter((row) => row.value !== null).length;
}
