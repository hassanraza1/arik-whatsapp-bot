# Arik regression suite

Runs against a duplicate Walton Commerce Engine webhook. It does not contain API keys.

On the server:

```bash
ARIK_DB=1 python3 run_suite.py
```

The default webhook is `http://127.0.0.1:5678/webhook/ai-chat-router-test`. The suite refuses the live `ai-chat` path unless `--allow-live` is set.

`ops/arik-daily-summary.sh` prints fallback, low-confidence, invalid JSON, error, and abuse counts for the last 24 hours from `arik_turn_monitor`.

Publish to the live webhook only after this suite reports zero failures and at least 40 passes.
