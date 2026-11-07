import { useEffect, useState, useCallback } from "react";
import { getAppointments } from "../api/client";
import type { Appointment, TurnMessage } from "../types";

interface AppointmentsPanelProps {
  latestTurn: TurnMessage | null;
}

export function AppointmentsPanel({ latestTurn }: AppointmentsPanelProps) {
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    return new Date().toISOString().slice(0, 10);
  });
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSchedule = useCallback(async (dateStr: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAppointments(dateStr);
      setAppointments(data);
    } catch (err: any) {
      console.warn("Failed to load appointments:", err);
      setError("Could not load clinic appointments.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch when selectedDate changes
  useEffect(() => {
    fetchSchedule(selectedDate);
  }, [selectedDate, fetchSchedule]);

  // Refresh if an action (booked, cancelled, rescheduled) was executed
  useEffect(() => {
    if (latestTurn?.action) {
      fetchSchedule(selectedDate);
    }
  }, [latestTurn?.action, selectedDate, fetchSchedule]);

  const handleDateShift = (offsetDays: number) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + offsetDays);
    setSelectedDate(d.toISOString().slice(0, 10));
  };

  return (
    <div className="appointments-panel card">
      <div className="panel-title-bar">
        <div>
          <h3>📅 Clinic Appointments</h3>
          <p className="subtitle">Live database schedule for BrightSmile Dental</p>
        </div>
        <button
          type="button"
          className="btn btn-icon-only"
          onClick={() => fetchSchedule(selectedDate)}
          title="Refresh appointments"
          disabled={loading}
        >
          🔄
        </button>
      </div>

      <div className="date-picker-row">
        <button
          type="button"
          className="btn btn-sm btn-outline"
          onClick={() => handleDateShift(-1)}
        >
          ◀ Prev Day
        </button>

        <input
          type="date"
          className="date-input"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
        />

        <button
          type="button"
          className="btn btn-sm btn-outline"
          onClick={() => handleDateShift(1)}
        >
          Next Day ▶
        </button>

        <button
          type="button"
          className="btn btn-sm btn-secondary"
          onClick={() => setSelectedDate(new Date().toISOString().slice(0, 10))}
        >
          Today
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="appointments-list-wrapper">
        {loading ? (
          <div className="loading-state">Loading appointments...</div>
        ) : appointments.length === 0 ? (
          <div className="empty-appointments">
            <span className="calendar-icon">🗓️</span>
            <p>No appointments booked for this date.</p>
          </div>
        ) : (
          <table className="appointments-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Patient</th>
                <th>Phone</th>
                <th>Service</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((appt) => (
                <tr key={appt.id} className={`status-row-${appt.status}`}>
                  <td className="time-col">
                    {appt.start_time.slice(0, 5)} - {appt.end_time.slice(0, 5)}
                  </td>
                  <td className="patient-col font-semibold">{appt.patient_name}</td>
                  <td className="phone-col font-mono text-muted">{appt.patient_phone}</td>
                  <td className="service-col">
                    <span className="service-badge">{appt.service}</span>
                  </td>
                  <td className="status-col">
                    <span className={`status-tag status-${appt.status}`}>
                      {appt.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

