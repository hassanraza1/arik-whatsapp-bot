-- Router monitoring and abuse counters. Safe to run more than once.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS abuse_count integer NOT NULL DEFAULT 0;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS abuse_lock boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS arik_turn_monitor (
  id bigserial PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  session_id text,
  kind text NOT NULL,
  intent text,
  confidence numeric,
  detail text
);

CREATE INDEX IF NOT EXISTS arik_turn_monitor_created_idx ON arik_turn_monitor (created_at DESC);
