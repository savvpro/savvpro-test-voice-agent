import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import {
  Mic,
  MicOff,
  Send,
  Calendar,
  Clock,
  Users,
  User,
  UtensilsCrossed,
  RotateCcw,
  Volume2,
  VolumeX,
  Sparkles,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

const API_BASE = "http://localhost:8000";

export default function App() {
  const [conversationId, setConversationId] = useState(null);
  const [state, setState] = useState('IDLE');
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [interimText, setInterimText] = useState('');
  
  const [bookingDetails, setBookingDetails] = useState({
    date: null,
    time: null,
    guests: null,
    customer_name: null
  });
  const [alternatives, setAlternatives] = useState([]);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [reservationRef, setReservationRef] = useState(null);
  
  // Voice controls
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(true);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);

  const recognitionRef = useRef(null);
  const messagesEndRef = useRef(null);
  const conversationIdRef = useRef(null);
  const transcriptRef = useRef('');
  const ttsEnabledRef = useRef(true);

  useEffect(() => {
    ttsEnabledRef.current = ttsEnabled;
    if (!ttsEnabled && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, [ttsEnabled]);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        transcriptRef.current = '';
        setInterimText('');
      };

      recognition.onresult = (event) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const item = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            final += item;
          } else {
            interim += item;
          }
        }
        
        if (final) {
          transcriptRef.current = final;
          setInterimText('');
        } else {
          transcriptRef.current = interim;
          setInterimText(interim);
        }
      };

      recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        setIsListening(false);
        setInterimText('');
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterimText('');
        const textToSend = transcriptRef.current?.trim();
        if (textToSend) {
          handleUserUtterance(textToSend);
          transcriptRef.current = '';
        }
      };

      recognitionRef.current = recognition;
    } else {
      setVoiceSupported(false);
    }

    // Auto start session
    startNewConversation();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, interimText]);

  const speakMessage = (text) => {
    if (!ttsEnabledRef.current || !window.speechSynthesis) return;
    window.speechSynthesis.cancel(); // Stop prior speech
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const startNewConversation = async () => {
    try {
      setIsProcessing(true);
      const res = await fetch(`${API_BASE}/api/conversation/start`, {
        method: 'POST'
      });
      const data = await res.json();
      setConversationId(data.conversation_id);
      setState(data.state);
      setBookingDetails(data.booking_details || {});
      setAlternatives([]);
      setIsConfirmed(false);
      setReservationRef(null);
      setMessages([
        { sender: 'assistant', text: data.assistant_message, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
      ]);
      speakMessage(data.assistant_message);
    } catch (err) {
      console.error("Failed to start conversation:", err);
      setMessages([
        { sender: 'assistant', text: "Unable to connect to Tableline concierge backend. Please ensure the backend is running.", isError: true }
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleUserUtterance = async (text) => {
    const activeId = conversationIdRef.current || conversationId;
    if (!text || !text.trim() || !activeId) return;

    // Add user message
    const userMsg = {
      sender: 'user',
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsProcessing(true);

    try {
      const res = await fetch(`${API_BASE}/api/conversation/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: activeId,
          message: text.trim()
        })
      });
      const data = await res.json();

      setState(data.state);
      if (data.booking_details) {
        setBookingDetails(data.booking_details);
      }
      if (data.suggested_alternatives) {
        setAlternatives(data.suggested_alternatives);
      } else {
        setAlternatives([]);
      }
      if (data.is_confirmed) {
        setIsConfirmed(true);
        setReservationRef(data.reservation_reference);
      }

      const assistantMsg = {
        sender: 'assistant',
        text: data.assistant_message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, assistantMsg]);
      speakMessage(data.assistant_message);

    } catch (err) {
      console.error("Turn request error:", err);
      setMessages(prev => [
        ...prev,
        { sender: 'assistant', text: "Sorry, I had trouble reaching the reservation engine. Could you please try again?", isError: true }
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      window.speechSynthesis?.cancel(); // Cancel any ongoing speech so mic doesn't hear it
      recognitionRef.current.start();
    }
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    handleUserUtterance(inputText);
  };

  const selectAlternative = (altTime) => {
    handleUserUtterance(`Let's do ${altTime}`);
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">
            <UtensilsCrossed size={22} />
          </div>
          <div>
            <h1 className="brand-title">Tableline</h1>
            <p className="brand-subtitle">Conversational Reservation Concierge</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button 
            className="alt-chip"
            onClick={() => setTtsEnabled(!ttsEnabled)}
            title={ttsEnabled ? "Mute Spoken Replies" : "Enable Spoken Replies"}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            {ttsEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            {ttsEnabled ? "Voice Output On" : "Muted"}
          </button>

          <button 
            className="alt-chip"
            onClick={startNewConversation}
            title="Start Over"
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <RotateCcw size={16} /> Reset
          </button>

          <div className="header-status-badge">
            <span className="status-dot"></span>
            <span>Deterministic Engine Active</span>
          </div>
        </div>
      </header>

      {/* Main Layout */}
      <div className="main-layout">
        {/* Interaction Panel */}
        <section className="interaction-panel">
          {/* Stage Progress Bar */}
          <div className="stage-tracker">
            <div className={`stage-step ${['IDLE', 'GREETING', 'COLLECTING_DETAILS'].includes(state) ? 'active' : ''}`}>
              <span className="step-num">1</span> Details
            </div>
            <div className={`stage-step ${state === 'OFFERING_ALTERNATIVES' ? 'active' : ''}`}>
              <span className="step-num">2</span> Availability
            </div>
            <div className={`stage-step ${state === 'AWAITING_CONFIRMATION' ? 'active' : ''}`}>
              <span className="step-num">3</span> Confirmation
            </div>
            <div className={`stage-step ${state === 'CONFIRMED' ? 'active' : ''}`}>
              <span className="step-num">4</span> Booked
            </div>
          </div>

          {/* Conversation Thread */}
          <div className="conversation-thread" aria-live="polite">
            {messages.map((m, idx) => (
              <div key={idx} className={`message-bubble ${m.sender}`}>
                <div className="message-meta">
                  <span>{m.sender === 'assistant' ? 'Tableline Concierge' : 'Caller'}</span>
                  <span>•</span>
                  <span>{m.timestamp}</span>
                </div>
                <div>{m.text}</div>
                {m.sender === 'assistant' && alternatives.length > 0 && idx === messages.length - 1 && (
                  <div className="alternatives-container">
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', alignSelf: 'center' }}>
                      Suggested alternatives:
                    </span>
                    {alternatives.map((alt) => (
                      <button
                        key={alt}
                        className="alt-chip"
                        onClick={() => selectAlternative(alt)}
                      >
                        {alt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Voice Console & Input Form */}
          <div className="voice-console">
            {interimText && <div className="live-interim">"{interimText}"</div>}

            <div className="mic-button-wrapper">
              {isListening && <div className="pulse-ring" />}
              <button
                className={`mic-button ${isListening ? 'listening' : ''} ${isProcessing ? 'processing' : ''}`}
                onClick={toggleListening}
                disabled={!voiceSupported || isProcessing}
                aria-label={isListening ? "Stop listening" : "Start speaking"}
                title={voiceSupported ? (isListening ? "Listening... click to pause" : "Click to speak") : "Voice recognition not supported in this browser"}
              >
                {isListening ? <Mic size={28} /> : (voiceSupported ? <Mic size={28} /> : <MicOff size={28} />)}
              </button>
            </div>

            <div className="voice-status-text">
              {isProcessing ? "Processing reservation query..." : 
               isListening ? "Listening... speak naturally" : 
               voiceSupported ? "Click microphone or type below" : 
               "Microphone speech recognition not supported in this browser (use text below)"}
            </div>

            {/* Text Input Fallback */}
            <form className="text-input-form" onSubmit={handleTextSubmit}>
              <input
                type="text"
                className="text-input"
                placeholder="e.g. 'Table for 4 this Friday at 7 PM' or 'Actually make that 6 people'"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={isProcessing}
              />
              <button
                type="submit"
                className="send-btn"
                disabled={!inputText.trim() || isProcessing}
                aria-label="Send message"
              >
                <Send size={16} /> Send
              </button>
            </form>
          </div>
        </section>

        {/* Right Sidebar: Live Reservation State & Verification */}
        <aside className="reservation-sidebar">
          <div className="reservation-card">
            <div className="card-header">
              <h2 className="card-title">Reservation Summary</h2>
              <span className={isConfirmed ? "badge-confirmed" : "badge-pending"}>
                {isConfirmed ? "Confirmed" : "In Progress"}
              </span>
            </div>

            <div className="details-grid">
              <div className="detail-item">
                <div className="detail-icon"><Calendar size={18} /></div>
                <div>
                  <div className="detail-label">Date</div>
                  <div className="detail-val">{bookingDetails.date || "Not specified"}</div>
                </div>
              </div>

              <div className="detail-item">
                <div className="detail-icon"><Clock size={18} /></div>
                <div>
                  <div className="detail-label">Time</div>
                  <div className="detail-val">{bookingDetails.time || "Not specified"}</div>
                </div>
              </div>

              <div className="detail-item">
                <div className="detail-icon"><Users size={18} /></div>
                <div>
                  <div className="detail-label">Party Size</div>
                  <div className="detail-val">
                    {bookingDetails.guests ? `${bookingDetails.guests} Guests` : "Not specified"}
                  </div>
                </div>
              </div>

              <div className="detail-item">
                <div className="detail-icon"><User size={18} /></div>
                <div>
                  <div className="detail-label">Guest Name</div>
                  <div className="detail-val">{bookingDetails.customer_name || "Guest"}</div>
                </div>
              </div>
            </div>

            {isConfirmed && reservationRef && (
              <div className="confirmation-box">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>
                  <CheckCircle size={16} /> Booking Reference
                </div>
                <div className="ref-code">{reservationRef}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                  Keep this code for entry or cancellation inquiries.
                </div>
              </div>
            )}
          </div>

          {/* Quick Natural Language Prompts for Assessment Evaluation */}
          <div className="quick-prompts">
            <div className="quick-prompt-title">Evaluation Test Prompts</div>
            <div className="prompt-btn-group">
              <button 
                className="prompt-btn"
                onClick={() => handleUserUtterance("Table for 4 this Friday at 7 PM under Sarah")}
              >
                1. Initial Request (Unavailable 7 PM)
              </button>
              <button 
                className="prompt-btn"
                onClick={() => handleUserUtterance("Actually, make that 6 people and 8 PM instead")}
              >
                2. In-flight Correction (6 guests, 8 PM)
              </button>
              <button 
                className="prompt-btn"
                onClick={() => handleUserUtterance("Yes, please confirm that reservation")}
              >
                3. Explicit Confirmation
              </button>
              <button 
                className="prompt-btn"
                onClick={() => handleUserUtterance("Yes confirm again")}
              >
                4. Idempotent Repeated Confirmation
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
