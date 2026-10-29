# Arik regression suite

Runs against the Phase 1 copy webhook. It does not contain API keys.

On the server:

```bash
ARIK_DB=1 python3 run_suite.py
```

The default webhook is `http://127.0.0.1:5678/webhook/ai-chat-phase1-test`. The suite refuses the live `ai-chat` path unless `--allow-live` is set.

Case 44 expects the live Walton Commerce Engine to stay on `59e9d471-8ef6-401d-877f-66ab25b49141`.

`ops/arik-daily-summary.sh` prints fallback, low-confidence, invalid JSON, error, and abuse counts for the last 24 hours from `arik_turn_monitor`.

Do not point the buffer or the live webhook at this copy until a person approves cutover.
