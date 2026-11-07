import type { Appointment, ClinicInfo } from "../types";

const API_BASE = import.meta.env.VITE_BACKEND_URL || "";

export async function getAppointments(dateStr?: string): Promise<Appointment[]> {
  const targetDate = dateStr || new Date().toISOString().slice(0, 10);
  const resp = await fetch(`${API_BASE}/appointments?date=${targetDate}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch appointments: ${resp.statusText}`);
  }
  return await resp.json();
}

export async function getClinicInfo(): Promise<ClinicInfo> {
  const resp = await fetch(`${API_BASE}/clinic`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch clinic info: ${resp.statusText}`);
  }
  return await resp.json();
}

export async function getFreeSlots(dateStr: string): Promise<Array<{ date: string; start_time: string; end_time: string }>> {
  const resp = await fetch(`${API_BASE}/appointments/slots?date=${dateStr}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch free slots: ${resp.statusText}`);
  }
  return await resp.json();
}
