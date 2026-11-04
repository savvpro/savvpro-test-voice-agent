import { useEffect, useState } from "react";
import { getClinicInfo } from "../api/client";
import type { ClinicInfo } from "../types";

export function Settings() {
  const [clinic, setClinic] = useState<ClinicInfo | null>(null);

  useEffect(() => {
    getClinicInfo()
      .then(setClinic)
      .catch((err) => console.warn("Could not load clinic config:", err));
  }, []);

  return (
    <div className="clinic-settings card">
      <div className="panel-title-bar">
        <h3>ℹ️ Clinic Rules & Specs</h3>
      </div>

      <div className="clinic-info-list">
        <div className="info-item">
          <span className="info-key">Clinic Name</span>
          <span className="info-val">{clinic?.name || "BrightSmile Dental Clinic"}</span>
        </div>

        <div className="info-item">
          <span className="info-key">Hours</span>
          <span className="info-val">
            {clinic?.open_hour ?? 9}:00 AM – {clinic?.close_hour ?? 17}:00 PM
          </span>
        </div>

        <div className="info-item">
          <span className="info-key">Days</span>
          <span className="info-val">Monday – Saturday (Closed Sunday)</span>
        </div>

        <div className="info-item">
          <span className="info-key">Slot Length</span>
          <span className="info-val">{clinic?.slot_minutes ?? 30} minutes</span>
        </div>
      </div>

      <div className="services-section">
        <span className="services-title">Covered Services:</span>
        <div className="services-tags">
          {(clinic?.services || [
            "cleaning",
            "checkup",
            "filling",
            "whitening",
            "root canal",
            "braces consultation",
          ]).map((s) => (
            <span key={s} className="service-pill">
              {s}
            </span>
          ))}
        </div>
      </div>

      <div className="tech-stack-row">
        <div className="tech-badge">
          <span className="tech-badge-dot green" />
          <span>STT: Faster-Whisper</span>
        </div>
        <div className="tech-badge">
          <span className="tech-badge-dot purple" />
          <span>Brain: Rule-Based FSM (Zero LLM)</span>
        </div>
        <div className="tech-badge">
          <span className="tech-badge-dot blue" />
          <span>TTS: EdgeTTS</span>
        </div>
      </div>
    </div>
  );
}

