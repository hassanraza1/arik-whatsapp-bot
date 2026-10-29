#!/usr/bin/env python3
"""Permanent regression suite for the Arik Commerce Engine router.

Disposable sessions only. Never sends an order confirmation.
"""
import argparse, base64, json, os, struct, subprocess, time, zlib
from urllib.request import Request, urlopen
from urllib.error import HTTPError

WEBHOOK = os.environ.get("ARIK_WEBHOOK", "http://127.0.0.1:5678/webhook/ai-chat-phase1-test")
LIVE_VERSION = "59e9d471-8ef6-401d-877f-66ab25b49141"
DB = os.environ.get("ARIK_DB") == "1"
RESULT = os.environ.get("ARIK_RESULT", "/root/backups/router-suite-result.json")

LIGHTS = [
    "Smart Wifi LED Bulb RGB 13W",
    "Smart Wifi Ceiling Downlight 10W RGB",
    "Smart Bluetooth Ceiling Downlight 10W RGB",
]
FAN = "Smart Wifi Fan Switch"
GANG = "8 Gang Wifi Touch Smart Switch"


def psql(sql):
    p = subprocess.run(
        ["docker", "exec", "-i", "waltonmarket-postgres-1", "psql", "-U", "walton", "-d", "waltonmarket", "-v", "ON_ERROR_STOP=1", "-t", "-A"],
        input=sql, text=True, capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-400:])
    return p.stdout.strip()


def png(w, h, rgb):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def post(sid, body, extra=None, timeout=30):
    payload = {"from": sid + "@c.us", "body": body, "fromMe": False, "source": "app", "type": "chat"}
    if extra:
        payload.update(extra)
    data = json.dumps({"payload": payload}).encode()
    req = Request(WEBHOOK, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status
    except HTTPError as e:
        return e.code


def snap(sid):
    if not DB:
        raise RuntimeError("ARIK_DB=1 is required")
    raw = psql(f"""
SELECT json_build_object(
  'quote', quote_state,
  'order_state', order_state,
  'page', current_page,
  'cart', cart,
  'abuse', abuse_count,
  'lock', abuse_lock,
  'esc', escalated_at IS NOT NULL,
  'hist', COALESCE(history, '[]'::jsonb),
  'updated', updated_at
)::text
FROM sessions WHERE session_id = '{sid}'
""")
    if not raw:
        return None
    row = json.loads(raw)
    hist = row["hist"] if isinstance(row["hist"], list) else []
    last = ""
    for item in reversed(hist):
        if isinstance(item, dict) and item.get("role") == "assistant":
            last = item.get("text") or ""
            break
    row["hist"] = hist
    row["last"] = last
    row["n"] = len(hist)
    return row


def wait_change(sid, before_n, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.2)
        now = snap(sid)
        if now and now["n"] > before_n:
            time.sleep(0.3)
            return snap(sid)
    return snap(sid)


def say(sid, text, extra=None, timeout=40):
    before = snap(sid)
    n = 0 if not before else before["n"]
    code = post(sid, text, extra=extra)
    if code != 200:
        return {"http": code, "last": "", "n": n, "cart": [], "quote": None, "order_state": None, "abuse": 0, "lock": False, "esc": False, "page": 0}
    got = wait_change(sid, n, timeout)
    return got or {"http": code, "last": "", "n": n, "cart": [], "quote": None, "order_state": None, "abuse": 0, "lock": False, "esc": False, "page": 0}


def seed(sid, quote=None, order=None, history=None, last=None, cart=None, abuse=0, lock=False):
    hist = json.dumps(history or []).replace("'", "''")
    last_sql = "NULL" if last is None else "'" + json.dumps(last).replace("'", "''") + "'::jsonb"
    cart_sql = "'" + json.dumps(cart or []).replace("'", "''") + "'::jsonb"
    qsql = "NULL" if not quote else "'" + quote.replace("'", "''") + "'"
    osql = "NULL" if not order else "'" + order.replace("'", "''") + "'"
    psql(f"""
INSERT INTO sessions (session_id, history, quote_state, quote_data, order_state, order_data, last_product, cart, current_page, abuse_count, abuse_lock)
VALUES ('{sid}', '{hist}'::jsonb, {qsql}, '{{}}'::jsonb, {osql}, '{{}}'::jsonb, {last_sql}, {cart_sql}, 0, {int(abuse)}, {'true' if lock else 'false'})
ON CONFLICT (session_id) DO UPDATE SET
  history = EXCLUDED.history,
  quote_state = EXCLUDED.quote_state,
  quote_data = EXCLUDED.quote_data,
  order_state = EXCLUDED.order_state,
  last_product = EXCLUDED.last_product,
  cart = EXCLUDED.cart,
  current_page = 0,
  abuse_count = EXCLUDED.abuse_count,
  abuse_lock = EXCLUDED.abuse_lock,
  escalated_at = NULL,
  updated_at = NOW()
""")


def product(name):
    raw = psql("SELECT id || '|' || price || '|' || coalesce(image_url,'') FROM products WHERE product_name = '" + name.replace("'", "''") + "'")
    if not raw:
        raise RuntimeError("missing product " + name)
    pid, price, image = raw.split("|", 2)
    return {"id": int(pid), "product_name": name, "price": float(price), "stock": "In stock", "image_url": image}


def offered_history(products):
    lines = []
    for i, p in enumerate(products, 1):
        lines.append(f"╭─ *{i}. {p['product_name']}*\n│ 💰 *Price:* PKR {int(p['price'])}")
    return [{"role": "assistant", "text": "\n\n".join(lines), "ts": 1}]


def qty_of(cart, name):
    if not cart:
        return 0
    for c in cart:
        if c.get("name") == name:
            return int(c.get("qty") or 0)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if WEBHOOK.rstrip("/").endswith("/webhook/ai-chat") and not args.allow_live:
        raise SystemExit("refusing live ai-chat webhook")
    if not DB:
        raise SystemExit("set ARIK_DB=1")

    psql("""
DELETE FROM arik_observability WHERE session_id LIKE 'test-rtr-%';
DELETE FROM arik_session_memory WHERE session_id LIKE 'test-rtr-%';
DELETE FROM arik_turn_monitor WHERE session_id LIKE 'test-rtr-%';
DELETE FROM whatsapp_identities WHERE phone LIKE 'test-rtr-%' OR chat_id LIKE 'test-rtr-%';
DELETE FROM sessions WHERE session_id LIKE 'test-rtr-%';
""")
    lights = [product(n) for n in LIGHTS]
    fan = product(FAN)
    gang = product(GANG)
    results = []

    def check(name, ok, detail=""):
        results.append({"name": name, "ok": bool(ok), "detail": detail[:180]})
        print(("PASS " if ok else "FAIL ") + name + ((" — " + detail[:120]) if detail and not ok else ""))

    def model(name, fn):
        ok, detail = fn()
        if not ok:
            time.sleep(1)
            ok, detail = fn()
            detail = (detail or "") + " (retry)"
        check(name, ok, detail)

    # 1 greeting
    def t_hi():
        r = say("test-rtr-hi", "Hi", timeout=35)
        return ("1️⃣" in r["last"], r["last"][:80])
    model("01 greeting shows menu", t_hi)

    # 2 deterministic menu
    r = say("test-rtr-menu", "menu", timeout=20)
    check("02 exact menu shows menu", "1️⃣" in r["last"], r["last"][:80])

    # 3-6 catalogue pagination
    sid = "test-rtr-pages"
    r = say(sid, "catalogue", timeout=20)
    check("03 catalogue page 1", "Page 1/" in r["last"], r["last"][:40])
    r = say(sid, "next", timeout=20)
    check("04 first next is page 2", "Page 2/" in r["last"], r["last"][:40])
    r = say(sid, "next", timeout=20)
    check("05 second next is page 3", "Page 3/" in r["last"] and r.get("page") == 2, r["last"][:40])
    r = say(sid, "prev", timeout=20)
    check("06 prev returns page 2", "Page 2/" in r["last"], r["last"][:40])

    # 7 empty checkout
    r = say("test-rtr-empty", "checkout", timeout=30)
    check("07 empty cart checkout", "empty" in r["last"].lower(), r["last"][:80])

    # 8-14 quote interrupts
    def quote_case(sid, text, label):
        seed(sid, quote="collecting_customer_info")
        r = say(sid, text, timeout=20)
        ok = "1️⃣" in r["last"] and not r.get("quote")
        check(label, ok, f"quote={r.get('quote')} last={r['last'][:70]}")

    quote_case("test-rtr-q1", "behan k loray menu khol", "08 abuse plus menu khol shows menu")
    quote_case("test-rtr-q2", "menu", "09 lone menu during quote shows menu")
    quote_case("test-rtr-q3", "cancel", "10 cancel during quote shows menu")
    quote_case("test-rtr-q4", "back", "11 back during quote shows menu")
    quote_case("test-rtr-q5", "wapas", "12 wapas during quote shows menu")
    quote_case("test-rtr-q6", "human", "13 human during quote shows menu")
    quote_case("test-rtr-q7", "menu khol do", "14 menu khol do shows menu")

    # 15 real quote answer
    seed("test-rtr-q8", quote="collecting_customer_info")
    r = say("test-rtr-q8", "Ahmad Ali\n03001234567\nLahore, DHA", timeout=20)
    check("15 name and phone advances quotation", r.get("quote") == "collecting_house_details", str(r.get("quote")))

    # 16 incomplete quote
    seed("test-rtr-q9", quote="collecting_customer_info")
    r = say("test-rtr-q9", "Ahmad only", timeout=20)
    check("16 name without phone stays on the form", r.get("quote") == "collecting_customer_info", str(r.get("quote")))

    # 17-21 abuse ladder
    seed("test-rtr-ab", quote="collecting_customer_info")
    r = say("test-rtr-ab", "Bsdk arik", timeout=20)
    check("17 first abuse warns and leaves the form", (not r.get("quote")) and r.get("abuse") == 1 and "respectful" in r["last"].lower(), r["last"][:80])
    r = say("test-rtr-ab", "loru", timeout=20)
    check("18 second abuse is a firmer warning", r.get("abuse") == 2 and "Second warning" in r["last"], r["last"][:80])
    r = say("test-rtr-ab", "piece of shit", timeout=20)
    check("19 third abuse locks the chat", r.get("abuse") == 3 and r.get("lock") and r.get("esc") and "stopped" in r["last"].lower(), r["last"][:80])
    before = snap("test-rtr-ab")
    post("test-rtr-ab", "hi")
    time.sleep(8)
    after = snap("test-rtr-ab")
    check("20 locked chat does not auto-reply", after["n"] == before["n"] and after["esc"], f"n {before['n']}->{after['n']}")
    psql("UPDATE sessions SET escalated_at = NULL, abuse_lock = false, abuse_count = 0 WHERE session_id = 'test-rtr-ab'")
    r = say("test-rtr-ab", "menu", timeout=20)
    check("21 release allows menu again", "1️⃣" in r["last"] and not r.get("esc"), r["last"][:60])

    # 22 order form menu
    seed("test-rtr-ord", order="collecting_name", cart=[{"name": FAN, "price": fan["price"], "qty": 1}])
    r = say("test-rtr-ord", "menu", timeout=20)
    check("22 menu during checkout shows menu and clears the form", "1️⃣" in r["last"] and not r.get("order_state"), str(r.get("order_state")))

    # 23 search
    def t_search():
        r = say("test-rtr-search", "8 gang black", timeout=40)
        return (GANG.split()[0] in r["last"] and "8 Gang" in r["last"] and "╭─" in r["last"], r["last"][:90])
    model("23 search 8 gang returns that product", t_search)

    # 24-26 buy, cart, checkout
    def t_buy():
        r = say("test-rtr-buy", "buy " + FAN, timeout=40)
        return (qty_of(r.get("cart"), FAN) == 1, str(r.get("cart"))[:120])
    model("24 buy exact fan switch quantity 1", t_buy)
    r = say("test-rtr-buy", "cart", timeout=35)
    check("25 cart still has the fan switch", qty_of(r.get("cart"), FAN) == 1 and FAN in r["last"], r["last"][:90])
    r = say("test-rtr-buy", "checkout", timeout=30)
    check("26 checkout asks for a name and keeps the cart", "name" in r["last"].lower() and r.get("order_state") == "collecting_name" and qty_of(r.get("cart"), FAN) == 1, str(r.get("order_state")))

    # 27 teeno quantities
    def t_teeno():
        seed("test-rtr-teeno", history=offered_history(lights))
        r = say("test-rtr-teeno", "Mujhe yeh teeno lights 100 100 unit chahiye", timeout=45)
        cart = r.get("cart") or []
        ok = all(qty_of(cart, p["product_name"]) == 100 for p in lights)
        return (ok, str(cart)[:160])
    model("27 teeno lights quantity 100 each", t_teeno)

    # 28 buy 1 2 3
    def t_nums():
        seed("test-rtr-nums", history=offered_history(lights))
        r = say("test-rtr-nums", "buy 1 2 3 in quantity 100 100 100", timeout=45)
        cart = r.get("cart") or []
        ok = all(qty_of(cart, p["product_name"]) == 100 for p in lights)
        return (ok, str(cart)[:160])
    model("28 buy 1 2 3 quantity 100 100 100", t_nums)

    # 29 teeno kism lists rather than which-product
    def t_kinds():
        seed("test-rtr-kinds", history=offered_history(lights))
        r = say("test-rtr-kinds", "Teeno kism ki lights", timeout=40)
        bad = "which product" in r["last"].lower()
        return ((not bad) and ("Bulb" in r["last"] or "Downlight" in r["last"]), r["last"][:100])
    model("29 teeno kinds lists the lights", t_kinds)

    # 30 bare buy
    def t_bare():
        r = say("test-rtr-bare", "buy", timeout=40)
        cart = r.get("cart") or []
        return (len(cart) == 0 and "which product" in r["last"].lower(), r["last"][:80])
    model("30 bare buy does not invent a cart line", t_bare)

    # 31 badhe adds 10
    def t_badhe():
        seed("test-rtr-badhe", last=lights[0], cart=[{"name": lights[0]["product_name"], "price": lights[0]["price"], "qty": 1}])
        r = say("test-rtr-badhe", "10 piece badhe", timeout=40)
        return (qty_of(r.get("cart"), lights[0]["product_name"]) >= 11, str(r.get("cart"))[:120])
    model("31 10 piece badhe adds ten", t_badhe)

    # 32 quantity 10
    def t_ten():
        seed("test-rtr-ten", last=lights[0])
        r = say("test-rtr-ten", "mujhe 10 chahiye", timeout=40)
        return (qty_of(r.get("cart"), lights[0]["product_name"]) == 10, str(r.get("cart"))[:120])
    model("32 mujhe 10 chahiye adds ten of the last product", t_ten)

    # 33 red square
    red = base64.b64encode(png(32, 32, (220, 20, 20))).decode()
    def t_red():
        r = say("test-rtr-red", "", extra={"type": "image", "hasMedia": True, "mediaBase64": red, "mediaMimetype": "image/png"}, timeout=70)
        return ("╭─" not in r["last"] and "match" in r["last"].lower(), r["last"][:100])
    model("33 red square does not invent a product card", t_red)

    # 34 catalogue photo
    def t_photo():
        if not gang["image_url"]:
            return (False, "no image url")
        req = Request(gang["image_url"], headers={"User-Agent": "WaltonMarketCatalogue/1.0"})
        with urlopen(req, timeout=30) as resp:
            b64 = base64.b64encode(resp.read()).decode()
        r = say("test-rtr-photo", "", extra={"type": "image", "hasMedia": True, "mediaBase64": b64, "mediaMimetype": "image/png"}, timeout=80)
        return ("8 Gang" in r["last"] and "╭─" in r["last"], r["last"][:100])
    model("34 catalogue photo matches 8 Gang", t_photo)

    # 35 clear cart
    def t_clear():
        seed("test-rtr-clear", cart=[{"name": FAN, "price": fan["price"], "qty": 2}])
        r = say("test-rtr-clear", "clear cart", timeout=35)
        return (not r.get("cart"), r["last"][:80])
    model("35 clear cart empties the cart", t_clear)

    # 36-37 abuse phrases
    r = say("test-rtr-ab2", "you piece of shit", timeout=20)
    check("36 english abuse warns", r.get("abuse") == 1 and "respectful" in r["last"].lower(), r["last"][:70])
    r = say("test-rtr-ab3", "behan k loray", timeout=20)
    check("37 roman urdu abuse warns and is not the menu", r.get("abuse") == 1 and "1️⃣" not in r["last"], r["last"][:70])

    # 38 next does not escape a quote form into the catalogue
    seed("test-rtr-qnext", quote="collecting_customer_info")
    r = say("test-rtr-qnext", "next", timeout=20)
    check("38 next during quotation does not open the catalogue", "Page " not in r["last"] and r.get("quote") == "collecting_customer_info", r["last"][:70])

    # 39 digit 1 after menu is catalogue
    r = say("test-rtr-digit", "menu", timeout=20)
    r = say("test-rtr-digit", "1", timeout=20)
    check("39 menu then 1 opens the catalogue", "Page 1/" in r["last"], r["last"][:50])

    # 40 cart remove by leaving one product via a second buy is not this; remove phrase
    def t_remove():
        seed("test-rtr-rm", cart=[{"name": FAN, "price": fan["price"], "qty": 1}, {"name": lights[0]["product_name"], "price": lights[0]["price"], "qty": 1}])
        r = say("test-rtr-rm", "remove 1", timeout=35)
        gone = qty_of(r.get("cart"), FAN) == 0 and qty_of(r.get("cart"), lights[0]["product_name"]) == 1
        return (gone, str(r.get("cart"))[:140])
    model("40 remove 1 drops the first cart line", t_remove)

    # 41 monitor rows
    nmon = psql("SELECT count(*) FROM arik_turn_monitor WHERE session_id LIKE 'test-rtr-%' AND kind = 'abuse'")
    check("41 abuse turns are written to the monitor table", int(nmon or 0) >= 1, nmon)

    # 42 image cached
    check("42 8 Gang catalogue image url is stored", gang["image_url"].startswith("https://"), gang["image_url"][:60])

    # 43 shopify webhooks untouched
    hooks = psql("SELECT string_agg(\"webhookPath\", ',' ORDER BY \"webhookPath\") FROM webhook_entity")
    check("43 shopify webhooks still registered", "shopify-order-created" in hooks and "shopify-order-fulfilled" in hooks and "ai-chat" in hooks, hooks)

    # 44 live router version must stay on the published router while Phase 1 is a copy
    ver = psql("SELECT \"activeVersionId\" FROM workflow_entity WHERE id = '25xrGALJPr79bTVh'")
    check("44 live workflow still on the published router", ver == LIVE_VERSION, ver)

    # 45 daily summary
    p = subprocess.run(["bash", "/usr/local/sbin/arik-daily-summary.sh"], capture_output=True, text=True)
    check("45 daily summary runs", p.returncode == 0 and "kind" in p.stdout, p.stderr[-80:])

    # 46 menu reply is not the old cancel-only sentence
    seed("test-rtr-q10", quote="collecting_customer_info")
    r = say("test-rtr-q10", "menu", timeout=20)
    check("46 quote menu is not cancel-only", "Quotation cancelled" not in r["last"] and "1️⃣" in r["last"], r["last"][:80])

    # 47 bund abuse
    r = say("test-rtr-ab4", "bund", timeout=20)
    check("47 bund is counted as abuse", r.get("abuse") == 1, r["last"][:60])

    # 48 greeting is not abuse
    row = snap("test-rtr-hi")
    check("48 greeting does not increment abuse", row and row.get("abuse") in (0, None), str(row.get("abuse") if row else None))

    bulb = lights[0]

    def t_set():
        seed("test-rtr-setq", cart=[{"name": bulb["product_name"], "price": bulb["price"], "qty": 100}])
        r = say("test-rtr-setq", "oh nahi nahi muja sirf 2 chahiye", timeout=45)
        return (qty_of(r.get("cart"), bulb["product_name"]) == 2, str(r.get("cart"))[:140])
    model("49 sirf 2 sets quantity instead of adding", t_set)

    def t_rm100():
        seed("test-rtr-rm100", cart=[{"name": bulb["product_name"], "price": bulb["price"], "qty": 2}])
        r = say("test-rtr-rm100", "100 pieces esme se remove kerdo", timeout=45)
        gone = qty_of(r.get("cart"), bulb["product_name"]) == 0 and "couldn't find" not in r["last"].lower()
        return (gone, r["last"][:100])
    model("50 remove 100 pieces from the only cart line", t_rm100)

    def t_rmname():
        seed("test-rtr-rmname", cart=[{"name": bulb["product_name"], "price": bulb["price"], "qty": 2}])
        r = say("test-rtr-rmname", "remove smart bulb 100 piece", timeout=45)
        gone = qty_of(r.get("cart"), bulb["product_name"]) == 0 and "couldn't find" not in r["last"].lower()
        return (gone, r["last"][:100])
    model("51 remove smart bulb 100 uses the cart line", t_rmname)

    def t_urdu():
        seed("test-rtr-urdu", history=[
            {"role": "user", "text": "what is a smart home", "ts": 1},
            {"role": "assistant", "text": "A smart home lets you switch lights from your phone.", "ts": 2},
        ])
        r = say("test-rtr-urdu", "esko urdu mien baro", timeout=45)
        low = r["last"].lower()
        urdu = any("\u0600" <= ch <= "\u06FF" for ch in r["last"])
        ok = ("maps.app" not in low) and ("jinnah" not in low) and ("goo.gl" not in low) and (urdu or "smart home" in low or "urdu" in low)
        return (ok, r["last"][:120])
    model("52 urdu repeat is not the store address", t_urdu)

    def t_love():
        r = say("test-rtr-love", "mujha payar karo", timeout=40)
        low = r["last"].lower()
        ok = r.get("abuse") in (0, None) and not r.get("lock") and "respectful" not in low and "stopped" not in low
        return (ok, r["last"][:100])
    model("53 playful payar is not abuse", t_love)

    def t_wood():
        r = say("test-rtr-wood", "mujhe indoor wooden door lock chahiye", timeout=45)
        low = r["last"].lower()
        ok = "wooden" in low and "bedroom" in low and "5 way unlock" in low and not r.get("cart")
        return (ok, r["last"][:140])
    model("54 indoor wooden door lock is attribute reasoning", t_wood)

    def t_hes():
        r = say("test-rtr-hes", "mujhe warranty ka bharosa nahi, main confuse hoon", timeout=45)
        mem = psql("SELECT coalesce(buying_stage,'') || '|' || coalesce(objection,'') || '|' || lead_score::text FROM arik_session_memory WHERE session_id = 'test-rtr-hes'")
        obs = psql("SELECT coalesce(latency_ms,0)::text || '|' || coalesce(prompt_tokens,0)::text || '|' || coalesce(output_tokens,0)::text FROM arik_observability WHERE session_id = 'test-rtr-hes' ORDER BY id DESC LIMIT 1")
        ok = ("human" in r["last"].lower()) and (not r.get("lock")) and (not r.get("esc")) and r.get("abuse") in (0, None) and mem.startswith("hesitation|") and obs not in ("", None)
        return (ok, mem + " obs " + obs + " " + r["last"][:80])
    model("55 hesitation offers a human and stores memory", t_hes)

    mem_buy = psql("SELECT coalesce(lead_score,0)::text || '|' || coalesce(last_board_intent,'') FROM arik_session_memory WHERE session_id = 'test-rtr-setq'")
    obs_buy = psql("SELECT coalesce(latency_ms,0)::text || '|' || coalesce(prompt_tokens,0)::text || '|' || coalesce(output_tokens,0)::text FROM arik_observability WHERE session_id = 'test-rtr-setq' ORDER BY id DESC LIMIT 1")
    check("56 set-quantity turn records lead score and tokens", mem_buy.startswith(("20|", "15|", "25|", "10|")) or (mem_buy[:2].isdigit() and int(mem_buy.split("|")[0]) >= 15), mem_buy + " " + obs_buy)
    parts = (obs_buy or "0|0|0").split("|")
    check("57 set-quantity observability has latency", len(parts) == 3 and int(parts[0]) >= 0 and (int(parts[1]) + int(parts[2])) > 0, obs_buy)

    scaffolds = psql("SELECT count(*) FROM arik_board_modules WHERE status = 'scaffold'")
    check("58 later board modules are scaffold only", int(scaffolds or 0) >= 8, scaffolds)

    cost_raw = psql("""
SELECT coalesce(sum(prompt_tokens),0)::text || '|' || coalesce(sum(output_tokens),0)::text
  || '|' || coalesce(round(avg(latency_ms)),0)::text || '|' || count(*)::text
FROM arik_observability WHERE session_id LIKE 'test-rtr-%'
""")
    pin, pout, avg_ms, nrows = (cost_raw.split("|") + ["0", "0", "0", "0"])[:4]
    # Google AI Studio standard paid text rate for gemini-2.5-flash, $0.30 / 1M input and $2.50 / 1M output.
    usd = (int(pin) * 0.30 + int(pout) * 2.50) / 1000000
    print(f"tokens_in {pin} tokens_out {pout} avg_latency_ms {avg_ms} obs_rows {nrows} paid_text_usd {usd:.6f}")

    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    out = {
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "prompt_tokens": int(pin),
        "output_tokens": int(pout),
        "avg_latency_ms": int(float(avg_ms)),
        "paid_text_usd": round(usd, 6),
        "cases": results,
    }
    try:
        with open(RESULT, "w") as f:
            json.dump(out, f, indent=2)
        os.chmod(RESULT, 0o600)
    except OSError as e:
        print("result_not_saved", e)
    psql("""
DELETE FROM arik_observability WHERE session_id LIKE 'test-rtr-%';
DELETE FROM arik_session_memory WHERE session_id LIKE 'test-rtr-%';
DELETE FROM arik_turn_monitor WHERE session_id LIKE 'test-rtr-%';
DELETE FROM whatsapp_identities WHERE phone LIKE 'test-rtr-%' OR chat_id LIKE 'test-rtr-%';
DELETE FROM sessions WHERE session_id LIKE 'test-rtr-%';
""")
    # keep the result file; monitor rows for the summary were deleted after the summary ran
    return 0 if failed == 0 and passed >= 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
