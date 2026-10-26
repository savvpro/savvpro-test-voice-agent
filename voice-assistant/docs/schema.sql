CREATE TABLE call_session (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  outcome TEXT,
  state_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE appointment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token INTEGER NOT NULL CHECK (token BETWEEN 1 AND 35),
  appointment_date TEXT NOT NULL,
  start_min INTEGER NOT NULL,
  end_min INTEGER NOT NULL,
  guardian_name TEXT NOT NULL,
  child_name TEXT NOT NULL,
  child_age INTEGER NOT NULL CHECK (child_age BETWEEN 0 AND 18),
  contact TEXT,
  email TEXT,
  email_verified INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0,1)),
  status TEXT NOT NULL CHECK (status IN ('active','cancelled','rescheduled')),
  previous_appointment_id INTEGER REFERENCES appointment(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX ux_appointment_active_token
  ON appointment(appointment_date, token) WHERE status='active';
CREATE INDEX ix_appointment_date_status ON appointment(appointment_date, status);

CREATE TABLE appointment_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER NOT NULL REFERENCES appointment(id),
  event TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE email_verification (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  email TEXT NOT NULL,
  purpose TEXT NOT NULL,
  code_digest TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  used_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE notification_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER NOT NULL REFERENCES appointment(id),
  event TEXT NOT NULL CHECK (event IN ('booked','cancelled','rescheduled')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent')),
  attempts INTEGER NOT NULL DEFAULT 0,
  locked_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  sent_at TEXT,
  UNIQUE (appointment_id,event)
);

CREATE TABLE turn (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES call_session(id),
  idx INTEGER NOT NULL,
  user_text TEXT NOT NULL,
  intent TEXT,
  slots_json TEXT,
  state_before TEXT,
  state_after TEXT,
  action TEXT,
  reply TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (session_id, idx)
);
