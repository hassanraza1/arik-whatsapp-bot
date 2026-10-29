-- Additive Phase 1 tables. Safe to run while the live workflow is untouched.
CREATE TABLE IF NOT EXISTS arik_session_memory (
  session_id text PRIMARY KEY,
  lead_score integer NOT NULL DEFAULT 0,
  buying_stage text,
  objection text,
  last_board_intent text,
  turn_count integer NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arik_observability (
  id bigserial PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  session_id text,
  intent text,
  board_intent text,
  buying_stage text,
  objection text,
  confidence numeric,
  latency_ms integer,
  prompt_tokens integer,
  output_tokens integer,
  model text
);
CREATE INDEX IF NOT EXISTS arik_observability_session_idx ON arik_observability (session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS arik_board_modules (
  module text PRIMARY KEY,
  status text NOT NULL,
  note text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO arik_board_modules (module, status, note) VALUES
  ('campaign', 'scaffold', 'FigJam AI Campaign and Marketing. Not executed.'),
  ('bundle', 'scaffold', 'FigJam Dynamic Bundle Engine. Not executed.'),
  ('sheets', 'scaffold', 'FigJam Google Sheets sync. Not executed.'),
  ('courier', 'scaffold', 'FigJam courier integration. Not executed.'),
  ('vision_embed', 'scaffold', 'FigJam vision unit beyond the current photo match. Not executed.'),
  ('instagram', 'scaffold', 'FigJam Instagram channel. Not executed.'),
  ('email', 'scaffold', 'FigJam email SMTP. Not executed.'),
  ('order_automation', 'scaffold', 'FigJam order automation. Not executed.')
ON CONFLICT (module) DO NOTHING;
