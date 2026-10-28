# Changelog

## v1.0.0-2026.10.28 — 2026-10-28 (Asia/Karachi)

Sanitized snapshot of the live `/opt/waltonmarket` stack.

- Buffer gateway in front of n8n. It debounces inbound WhatsApp texts, then POSTs them to `/webhook/ai-chat`. Compose waits are 8000 ms and 15000 ms. There is no `buffer/package.json`; the image is `node:20-alpine` running `buffer/index.js`.
- Published n8n workflow **Walton Commerce Engine** (active version exported here). Catalogue cards use the bracket form (`╭─` / `│` / `╰`). `next` / `aage` / `more` advances a stored page with `skipAI`, `currentPage`, and `products.slice` instead of asking Gemini to cut the full list.
- Stack layout: Postgres (`pgvector/pgvector:pg16`), n8n custom image (`n8nio/n8n:latest`, process version 2.12.3), WAHA (`devlikeapro/waha:latest-2026.7.1`, WEBJS engine), and the buffer build.
- SQL in `sql/` is schema plus product, pricing, and company copy. Bank account fields are placeholders. Customer, order, and session dumps are omitted. Quotation uploads are omitted.

Secrets are not included. Set Postgres, WAHA, and Gemini values in the environment before use.
