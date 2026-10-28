# Active n8n workflows

Exported from the live Postgres `activeVersionId` on 2026-10-28 (Asia/Karachi).

| File | Workflow |
|---|---|
| walton-commerce-engine.json | Walton Commerce Engine (webhook `ai-chat`) |
| walton-ai-agent.json | Walton AI — Agent |
| shopify-order-created.json | Shopify - Order Created |
| shopify-order-fulfilled.json | Shopify - Order Fulfilled |

`arik-main.json` in the repo root is the older April 2026 export (`WM Arik v2 — Modular`) and is kept for history.

Credential ids and the Gemini key are placeholders. Recreate Postgres, Shopify, and Gemini credentials in n8n before importing. Customer session rows, orders, and quotation uploads are not in this repository.
