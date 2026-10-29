#!/usr/bin/env python3
"""Install Phase 1 as a new workflow. Never updates the live Walton Commerce Engine."""
import hashlib, json, os, re, subprocess, sys, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE_ID = "25xrGALJPr79bTVh"
LIVE_VERSION = "59e9d471-8ef6-401d-877f-66ab25b49141"
TEST_ID = "Ph1WCE20261030"
TEST_PATH = "ai-chat-phase1-test"
PROJECT_ID = "T15P9DAkWYv9Kluf"
AUTHOR = "Muhammad Ain Ul Hassan Raza"
BACKUP = Path("/root/backups/walton-commerce-engine-59e9d471.json")

OLD_RULES = """STRUCTURED BUY AND MATCH RULES:
- items is the only purchase list. Each item is {productId, qty}. productId must be an id from PRODUCTS DATABASE or OFFERED LIST. Never invent an id.
- "teeno", "all three", "yeh teeno", and "1 2 3" mean every id in OFFERED LIST, in order. Pair quantities in order. One quantity given for all applies to each item.
- "badhe", "aur", "more", or a bare quantity of LAST PRODUCT: useLastProduct true and qty is how many MORE to add. items may be empty.
- If the customer names no product, OFFERED LIST is none, and LAST PRODUCT is none: items must be [] and useLastProduct false.
- product_search: put catalogue ids in matchIds. Never describe a product that is not in PRODUCTS DATABASE.
- Photo: bestProductId is a PHOTO CANDIDATE id, or 0. confidence is 0 to 1. Under 0.75 means unsure.
- abuse is true only for insults or harassment, not for a normal complaint.
- confidence is a number from 0 to 1.

RESPOND WITH JSON ONLY. Fields: intent, confidence, abuse, reply, items, matchIds, bestProductId, useLastProduct, qty.
JSON ONLY. No markdown backticks. No explanation outside JSON.`;"""

NEW_RULES = """STRUCTURED BUY AND MATCH RULES:
- items is the only purchase list. Each item is {productId, qty}. productId must be an id from PRODUCTS DATABASE, OFFERED LIST, or the CART. Never invent an id.
- cartOp is add, set, remove, or none.
- set means the quantity BECOMES that number. "sirf 2", "only 2", and "nahi nahi sirf 2 chahiye" are set, never add.
- remove subtracts qty from the matching CART line. "100 pieces esme se remove" and "remove smart bulb 100" are remove. If the cart has one line and no name is given, use that line.
- add is the default. "badhe", "more", and "mujhe 10 chahiye" add. They are not set.
- Exact "remove 1" or "remove 2" with no product name is intent cart_remove and items [].
- "teeno", "all three", "yeh teeno", and "1 2 3" mean every id in OFFERED LIST, in order. Pair quantities in order. One quantity given for all applies to each item.
- "badhe", "aur", "more", or a bare quantity of LAST PRODUCT: useLastProduct true, cartOp add, and qty is how many MORE to add. items may be empty.
- If the customer names no product, OFFERED LIST is none, and LAST PRODUCT is none: items must be [] and useLastProduct false.
- product_search: put catalogue ids in matchIds. Never describe a product that is not in PRODUCTS DATABASE.
- An indoor or wooden door lock is not an outdoor lock. Say no lock is listed for a wooden door. The bedroom-listed lock is the closest indoor option.
- Photo: bestProductId is a PHOTO CANDIDATE id, or 0. confidence is 0 to 1. Under 0.75 means unsure.
- abuse is false for playful affection such as "mujha payar karo". abuse is true only for insults or harassment.
- If the customer asks to repeat the previous answer in Urdu, intent is translate and reply is only that translation. Do not send the store address or a map link.
- boardIntent is one of product_recommendation, troubleshooting, order_status, human_escalation, cart, product_kb, spam, general.
- buyingStage is one of explorer, comparer, ready_to_buy, hesitation, existing_customer.
- objection is one of none, price, trust, installation_fear, compatibility, warranty.
- confidence is a number from 0 to 1.

RESPOND WITH JSON ONLY. Fields: intent, confidence, abuse, reply, items, matchIds, bestProductId, useLastProduct, qty, cartOp, boardIntent, buyingStage, objection.
JSON ONLY. No markdown backticks. No explanation outside JSON.`;"""

SAVE_NEEDLE = "return [{json: {\n  sqlQuery,"


def redact(text):
    return re.sub(r"AIza[0-9A-Za-z_\-]{8,}", "[redacted]", text or "")


def psql(sql):
    cmd = ["docker", "exec", "-i", "waltonmarket-postgres-1", "psql", "-U", "walton", "-d", "waltonmarket", "-v", "ON_ERROR_STOP=1", "-t", "-A"]
    p = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(redact(p.stderr)[-800:])
    return p.stdout


def psql_exec(sql):
    cmd = ["docker", "exec", "-i", "waltonmarket-postgres-1", "psql", "-U", "walton", "-d", "waltonmarket", "-v", "ON_ERROR_STOP=1"]
    p = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(redact(p.stderr)[-1200:])
    return p.stdout


def load_js(name):
    return (HERE / name).read_text()


def guard(wf_id):
    if wf_id == LIVE_ID:
        raise SystemExit("refusing to write the live workflow")


def live_row():
    raw = psql(f"""SELECT "activeVersionId" || E'\\n' || nodes::text FROM workflow_entity WHERE id = '{LIVE_ID}'""")
    ver, nodes_text = raw.split("\n", 1)
    return ver.strip(), nodes_text.strip()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def gemini_key_from(nodes):
    for n in nodes:
        if n.get("name") == "Call Gemini + Process":
            code = n["parameters"]["jsCode"]
            m = re.search(r"key:\s*'([^']+)'", code)
            if not m:
                raise SystemExit("gemini key pattern missing")
            return m.group(1)
    raise SystemExit("Call Gemini node missing")


def mutate(nodes):
    nodes = json.loads(json.dumps(nodes))
    key = gemini_key_from(nodes)
    gemini = load_js("call-gemini.js").replace("__GEMINI_KEY__", key)
    buy = load_js("handle-buy.js")
    phase = load_js("phase-log.js")
    save_tail = phase + "\n" + load_js("prepare-save.js")
    if "__GEMINI_KEY__" in gemini or "AIza" in buy or "AIza" in phase or "AIza" in save_tail:
        raise SystemExit("unexpected key placement")
    anchor = "// Clear escalation on the old 30 minute"
    for n in nodes:
        name = n.get("name")
        if name == "Webhook":
            n["parameters"]["path"] = TEST_PATH
            n["webhookId"] = str(uuid.uuid4())
        elif name == "Build AI Prompt":
            code = n["parameters"]["jsCode"]
            if code.count(OLD_RULES) != 1:
                raise SystemExit("prompt rules anchor missing")
            n["parameters"]["jsCode"] = code.replace(OLD_RULES, NEW_RULES, 1)
        elif name == "Call Gemini + Process":
            n["parameters"]["jsCode"] = gemini
        elif name == "Handle Buy":
            n["parameters"]["jsCode"] = buy
        elif name == "Prepare AI Save":
            code = n["parameters"]["jsCode"]
            at = code.find(anchor)
            if at < 0:
                raise SystemExit("save anchor missing")
            n["parameters"]["jsCode"] = code[:at] + save_tail
        elif name == "Save Session":
            code = phase + "\n" + n["parameters"]["jsCode"]
            code = code.replace("const sqlQuery = `INSERT INTO sessions", "let sqlQuery = `INSERT INTO sessions", 1)
            if "let sqlQuery = `INSERT INTO sessions" not in code:
                raise SystemExit("save session sql binding missing")
            if code.count(SAVE_NEEDLE) != 1:
                raise SystemExit("save session return missing")
            n["parameters"]["jsCode"] = code.replace(
                SAVE_NEEDLE,
                "sqlQuery = phaseWrap(sqlQuery, $json, sessionId, '');\n" + SAVE_NEEDLE,
                1,
            )
    return nodes


def syntax_check(nodes):
    for name in ("Build AI Prompt", "Call Gemini + Process", "Handle Buy", "Prepare AI Save", "Save Session"):
        code = next(n["parameters"]["jsCode"] for n in nodes if n["name"] == name)
        path = f"/tmp/arik-syntax-{name.replace(' ', '_')}.js"
        Path(path).write_text("async function n8nWrap() {\n" + code + "\n}\n")
        p = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        Path(path).unlink(missing_ok=True)
        if p.returncode != 0:
            raise SystemExit(f"syntax {name}: {redact(p.stderr)[-800:]}")
    print("syntax_ok")


def ddl():
    psql_exec((HERE / "sql" / "arik_phase1.sql").read_text())
    print("ddl_ok")


def write_workflow(nodes, connections, settings):
    guard(TEST_ID)
    version = str(uuid.uuid4())
    psql_exec(f"""
DELETE FROM webhook_entity WHERE "workflowId" = '{TEST_ID}';
DELETE FROM workflow_publish_history WHERE "workflowId" = '{TEST_ID}';
DELETE FROM shared_workflow WHERE "workflowId" = '{TEST_ID}';
UPDATE workflow_entity SET "activeVersionId" = NULL, active = false WHERE id = '{TEST_ID}';
DELETE FROM workflow_history WHERE "workflowId" = '{TEST_ID}';
DELETE FROM workflow_entity WHERE id = '{TEST_ID}';
INSERT INTO workflow_entity
  (id, name, active, nodes, connections, settings, "versionId", "activeVersionId", "createdAt", "updatedAt")
VALUES
  ('{TEST_ID}', 'Walton Commerce Engine - Phase 1', false, '{{}}'::json, '{{}}'::json, '{{}}'::json, '{version}', NULL, NOW(), NOW());
""")
    nodes_json = json.dumps(nodes).replace("'", "''")
    conns_json = json.dumps(connections).replace("'", "''")
    settings_json = json.dumps(settings or {}).replace("'", "''")
    if LIVE_ID in (TEST_ID,):
        raise SystemExit("refusing live write")
    big = f"""
UPDATE workflow_entity
SET nodes = '{nodes_json}'::json,
    connections = '{conns_json}'::json,
    settings = '{settings_json}'::json,
    "updatedAt" = NOW()
WHERE id = '{TEST_ID}';
INSERT INTO workflow_history
  ("versionId", "workflowId", authors, "createdAt", "updatedAt", nodes, connections, name, autosaved)
VALUES
  ('{version}', '{TEST_ID}', '{AUTHOR}', NOW(), NOW(),
   '{nodes_json}'::json, '{conns_json}'::json, 'Walton Commerce Engine - Phase 1', false);
UPDATE workflow_entity
SET "versionId" = '{version}',
    "activeVersionId" = '{version}',
    active = true,
    "updatedAt" = NOW()
WHERE id = '{TEST_ID}';
INSERT INTO shared_workflow ("workflowId", "projectId", role, "createdAt", "updatedAt")
VALUES ('{TEST_ID}', '{PROJECT_ID}', 'workflow:owner', NOW(), NOW());
INSERT INTO webhook_entity ("webhookPath", method, node, "workflowId")
VALUES ('{TEST_PATH}', 'POST', 'Webhook', '{TEST_ID}');
"""
    if f"WHERE id = '{LIVE_ID}'" in big or f"'{LIVE_ID}'" in big:
        raise SystemExit("live id leaked into copy sql")
    p = subprocess.run(
        ["docker", "exec", "-i", "waltonmarket-postgres-1", "psql", "-U", "walton", "-d", "waltonmarket", "-v", "ON_ERROR_STOP=1"],
        input=big, text=True, capture_output=True,
    )
    if p.returncode != 0:
        raise SystemExit(redact(p.stderr)[-1200:])
    print(f"workflow_written {TEST_ID} {version}")
    return version


def restart_n8n():
    subprocess.run(["docker", "restart", "waltonmarket-n8n-1"], check=True)
    for _ in range(40):
        time.sleep(2)
        p = subprocess.run(["curl", "-fsS", "http://127.0.0.1:5678/healthz"], capture_output=True, text=True)
        if p.returncode == 0:
            print("n8n_up")
            return
    raise SystemExit("n8n did not become healthy")


def started_at(container):
    p = subprocess.run(["docker", "inspect", "-f", "{{.State.StartedAt}}", container], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(p.stderr[-200:])
    return p.stdout.strip()


def install():
    ver, nodes_text = live_row()
    if ver != LIVE_VERSION:
        raise SystemExit(f"live version is {ver}")
    before = sha(nodes_text)
    waha_before = started_at("waltonmarket-waha-1")
    print("live_version", ver)
    print("live_sha", before)
    print("waha_started", waha_before)
    data_nodes = json.loads(nodes_text)
    connections = json.loads(psql(f"SELECT connections::text FROM workflow_entity WHERE id = '{LIVE_ID}'").strip())
    settings_raw = psql(f"SELECT settings::text FROM workflow_entity WHERE id = '{LIVE_ID}'").strip()
    settings = json.loads(settings_raw) if settings_raw else {}
    BACKUP.write_text(json.dumps({
        "id": LIVE_ID,
        "activeVersionId": ver,
        "nodes": data_nodes,
        "connections": connections,
        "settings": settings,
    }))
    os.chmod(BACKUP, 0o600)
    print("backup_bytes", BACKUP.stat().st_size)
    nodes = mutate(data_nodes)
    syntax_check(nodes)
    ver2, nodes_text2 = live_row()
    if ver2 != LIVE_VERSION or sha(nodes_text2) != before:
        raise SystemExit("live changed during prepare")
    ddl()
    version = write_workflow(nodes, connections, settings)
    ver3, nodes_text3 = live_row()
    if ver3 != LIVE_VERSION or sha(nodes_text3) != before:
        raise SystemExit("live changed during copy write")
    print("n8n_restart", "waltonmarket-n8n-1 only")
    restart_n8n()
    ver4, nodes_text4 = live_row()
    waha_after = started_at("waltonmarket-waha-1")
    print("live_version_after", ver4)
    print("live_sha_after", sha(nodes_text4))
    print("waha_started_after", waha_after)
    if ver4 != LIVE_VERSION or sha(nodes_text4) != before:
        raise SystemExit("live workflow changed across restart")
    if waha_after != waha_before:
        raise SystemExit("waha restarted")
    code = ""
    for _ in range(15):
        probe = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-X", "POST",
             "http://127.0.0.1:5678/webhook/" + TEST_PATH,
             "-H", "Content-Type: application/json",
             "-d", '{"payload":{"from":"test-rtr-ping@c.us","body":"menu","fromMe":false,"source":"app","type":"chat"}}'],
            capture_output=True, text=True,
        )
        code = probe.stdout.strip()
        if code == "200":
            break
        time.sleep(2)
    print("webhook_http", code)
    hooks = psql("SELECT string_agg(\"webhookPath\", ',' ORDER BY \"webhookPath\") FROM webhook_entity")
    print("webhooks", " ".join(hooks.split()))
    if "ai-chat" not in hooks or "shopify-order-created" not in hooks:
        raise SystemExit("live or shopify webhook missing")
    print("copy_version", version)
    if code != "200":
        raise SystemExit("phase1 webhook not ready")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "install":
        raise SystemExit("use install")
    install()
