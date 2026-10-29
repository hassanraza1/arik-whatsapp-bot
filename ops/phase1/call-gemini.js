const prev = $json;
const products = Array.isArray(prev.products) ? prev.products : [];
const MENU = "How can I help you today?\n1️⃣ Buy Smart Home Products\n2️⃣ Learn about Smart Home Automation\n3️⃣ Smart Home Installation\n4️⃣ Talk to Human Support\n\n📦 Type any product name to search.\n🛒 Type *buy [product name]* to add to cart.\n🧾 Type *cart* to view your cart.\n✅ Type *checkout* to place your order.\n\nAap Urdu mein bhi baat kar saktay hain!";

function q(s) {
  return String(s == null ? '' : s).replace(/'/g, "''").slice(0, 160);
}
function monitorSql(kind, intent, confidence, detail) {
  const sid = q(prev.sessionId || '');
  const conf = confidence == null || !Number.isFinite(Number(confidence)) ? 'NULL' : String(Number(confidence));
  return "INSERT INTO arik_turn_monitor (session_id, kind, intent, confidence, detail) SELECT '" + sid + "', '" + q(kind) + "', '" + q(intent) + "', " + conf + ", '" + q(detail) + "'";
}
function card(p) {
  const price = Number(p.price);
  const bank = Math.round(price * 0.95);
  return '╭─ *' + p.product_name + '*\n│ 💰 *Price:* PKR ' + price + '\n│ 💳 *Bank Transfer:* PKR ' + bank + '\n╰ ⚡ *Status:* ' + (p.stock || 'In stock') + ' | ' + (p.condition || 'New');
}
function footer() {
  return '\n\n🛒 Type *buy [product name]* to add to cart.\n🧾 Type *cart* to view your cart.\nType *menu* to return to main menu.';
}
function byId(id) {
  return products.find(p => Number(p.id) === Number(id)) || null;
}
function abuseReply(count) {
  if (count >= 3) {
    return 'Arik has stopped on this chat because of repeated abuse. A teammate has to release it before I can reply again.';
  }
  if (count === 2) {
    return 'Second warning. One more abusive message and Arik will stop replying until a teammate reopens this chat.\n\nType *menu* for options.';
  }
  return 'Please keep it respectful. I can help with products, your cart, or a quotation.\n\nType *menu* for options.';
}

const parts = [{ text: prev.systemPrompt || '' }];
const photoCandidates = Array.isArray(prev.photoCandidates) ? prev.photoCandidates : [];
const photoMode = !!(prev.customerImageB64 && String(prev.customerImageB64).length > 20);
let exactPhoto = null;

function hostOk(url) {
  try {
    const u = new URL(url);
    const host = u.hostname;
    return (u.protocol === 'https:' || u.protocol === 'http:') && (host === 'cdn.shopify.com' || host === 'waltonmarket.com' || host.endsWith('.shopifycdn.com'));
  } catch (e) {
    return false;
  }
}
if (photoMode) {
  const cust = String(prev.customerImageB64 || '');
  const pullImage = async (url) => {
    if (!hostOk(url)) return '';
    try {
      const img = await this.helpers.httpRequest({
        method: 'GET',
        url: url,
        encoding: 'arraybuffer',
        timeout: 12000,
        returnFullResponse: true
      });
      const body = img.body || img;
      const buf = Buffer.isBuffer(body) ? body : Buffer.from(body);
      if (buf.length > 0 && buf.length < 1500000) return buf.toString('base64');
    } catch (e) {}
    return '';
  }
  const seen = {};
  for (const c of photoCandidates) {
    c.imageB64 = await pullImage(c.image_url);
    c.imageMime = /\.png(\?|$)/i.test(String(c.image_url || '')) ? 'image/png' : 'image/jpeg';
    seen[Number(c.id)] = 1;
    if (!exactPhoto && c.imageB64 && c.imageB64 === cust) exactPhoto = byId(c.id);
  }
  if (!exactPhoto) {
    for (const p of products) {
      if (!p || seen[Number(p.id)] || !p.image_url) continue;
      const b64 = await pullImage(p.image_url);
      if (b64 && b64 === cust) {
        exactPhoto = p;
        break;
      }
    }
  }
  parts.push({ text: 'CUSTOMER PHOTO (match this image):' });
  parts.push({ inline_data: { mime_type: prev.customerImageMime || 'image/jpeg', data: prev.customerImageB64 } });
  for (const c of photoCandidates) {
    parts.push({ text: 'CANDIDATE id=' + c.id + ' name=' + c.product_name });
    if (c.imageB64) parts.push({ inline_data: { mime_type: c.imageMime || 'image/jpeg', data: c.imageB64 } });
  }
  parts.push({ text: 'Pick bestProductId only from the candidate ids. Use 0 if none match. Set confidence from 0 to 1. Do not name any product that is not a candidate.' });
}

const customerText = String(prev.lowerMsg || prev.message || '');
function lastAssistantText() {
  const hist = Array.isArray(prev.history) ? prev.history : [];
  const last = [...hist].reverse().find(h => h && h.role === 'assistant' && h.text);
  return last ? String(last.text).slice(0, 3500) : '';
}
const forceTranslate = !photoMode && /urdu/.test(customerText) && /(baro|banao|batao|likho|translate|mein|mien)/.test(customerText);
if (forceTranslate) {
  parts.length = 0;
  parts.push({ text: 'Translate ASSISTANT TEXT into Urdu script. Keep product names in Latin letters. Do not add a shop address, a map link, a city, or any location. If ASSISTANT TEXT is empty, say there is no earlier answer to translate.\n\nASSISTANT TEXT:\n' + lastAssistantText() });
}
function keywordAbuse(text) {
  return [/\bbsdk\b/i, /\bloru\b/i, /\bloray\b/i, /\blora\b/i, /\bbhenchod\b/i, /\bbehenchod\b/i, /\bmadarchod\b/i, /\bchutiya\b/i, /\bchutia\b/i, /\bgandu\b/i, /\bharami\b/i, /\bkanjar\b/i, /\brandi\b/i, /\bpanchod\b/i, /piece of shit/i, /\bfuck\b/i, /\bbastard\b/i, /\bbitch\b/i, /\bbullshit\b/i, /\bbund\b/i].some(r => r.test(text));
}
const playful = /(payar|pyar|piyar|\blove\b|\bjaan\b)/i.test(customerText) && !keywordAbuse(customerText);

let response;
let attempts = 0;
let latencyMs = 0;
let promptTokens = 0;
let outputTokens = 0;
const callStarted = Date.now();
while (attempts < 3) {
  try {
    response = await this.helpers.httpRequest({
      method: 'POST',
      url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
      headers: { 'Content-Type': 'application/json' },
      qs: { key: '__GEMINI_KEY__' },
      body: JSON.stringify({
        contents: [{ parts: parts }],
        generationConfig: {
          temperature: 0,
          responseMimeType: 'application/json',
          responseSchema: {
            type: 'OBJECT',
            properties: {
              intent: { type: 'STRING' },
              confidence: { type: 'NUMBER' },
              abuse: { type: 'BOOLEAN' },
              reply: { type: 'STRING' },
              useLastProduct: { type: 'BOOLEAN' },
              qty: { type: 'INTEGER' },
              bestProductId: { type: 'INTEGER' },
              matchIds: { type: 'ARRAY', items: { type: 'INTEGER' } },
              items: {
                type: 'ARRAY',
                items: {
                  type: 'OBJECT',
                  properties: {
                    productId: { type: 'INTEGER' },
                    qty: { type: 'INTEGER' }
                  },
                  required: ['productId', 'qty']
                }
              },
              cartOp: { type: 'STRING' },
              boardIntent: { type: 'STRING' },
              buyingStage: { type: 'STRING' },
              objection: { type: 'STRING' }
            },
            required: ['intent', 'confidence', 'abuse', 'reply', 'items']
          },
          thinkingConfig: { thinkingBudget: 0 }
        }
      }),
      timeout: 45000
    });
    break;
  } catch (err) {
    attempts++;
    if (attempts >= 3) {
      return [{ json: {
        ...prev,
        customerImageB64: '',
        intent: 'menu',
        reply: "Sorry, I'm having trouble right now. Please try again in a moment. Type *menu* for options.",
        items: [],
        monitorSql: monitorSql('error', 'menu', null, 'gemini_http')
      }}];
    }
    await new Promise(r => setTimeout(r, 1000 * attempts));
  }
}

latencyMs = Date.now() - callStarted;
let ai;
try {
  if (typeof response === 'string') response = JSON.parse(response);
  if (response && response.body && response.body.candidates) response = response.body;
  const usage = (response && response.usageMetadata) || {};
  promptTokens = Number(usage.promptTokenCount || 0) || 0;
  outputTokens = Number(usage.candidatesTokenCount || 0) || 0;
  if (!outputTokens && usage.totalTokenCount) outputTokens = Math.max(0, Number(usage.totalTokenCount) - promptTokens);
  const raw = response.candidates[0].content.parts[0].text;
  ai = JSON.parse(raw);
} catch (e) {
  return [{ json: {
    ...prev,
    customerImageB64: '',
    intent: 'menu',
    reply: "Sorry, I didn't understand that. Type *menu* for options.",
    items: [],
    monitorSql: monitorSql('invalid_json', 'menu', null, 'parse')
  }}];
}

let intent = String(ai.intent || 'menu');
let confidence = Number(ai.confidence);
if (!Number.isFinite(confidence)) confidence = 0.7;
let reply = String(ai.reply || '');
let items = Array.isArray(ai.items) ? ai.items : [];
items = items.map(it => ({ productId: Number(it && it.productId), qty: Number(it && it.qty) })).filter(it => Number.isFinite(it.productId) && Number.isFinite(it.qty));
let useLastProduct = ai.useLastProduct === true;
let qty = Number(ai.qty);
if (!Number.isFinite(qty) || qty < 1) qty = 1;
let monitor = '';
let clearForms = false;
let abuseCount = Number(prev.abuseCount || 0);
let abuseLock = false;
let lastProduct = prev.lastProduct || null;
let matchedProductId = null;
let cartOp = String(ai.cartOp || 'none').toLowerCase();
if (!['add', 'set', 'remove', 'none'].includes(cartOp)) cartOp = 'none';
if (playful) ai.abuse = false;

if (ai.abuse === true) {
  abuseCount += 1;
  clearForms = true;
  items = [];
  useLastProduct = false;
  reply = abuseReply(abuseCount);
  intent = abuseCount >= 3 ? 'abuse_lock' : 'abuse_warn';
  if (abuseCount >= 3) abuseLock = true;
  monitor = monitorSql('abuse', intent, confidence, 'model_flag');
}

if (!ai.abuse && photoMode) {
  const allowed = photoCandidates.map(c => Number(c.id));
  const best = Number(ai.bestProductId || 0);
  const product = allowed.includes(best) ? byId(best) : null;
  items = [];
  useLastProduct = false;
  if (product && confidence >= 0.75) {
    intent = 'product_search';
    reply = card(product) + footer();
    lastProduct = product;
    matchedProductId = product.id;
  } else if (photoCandidates.length >= 1) {
    intent = 'clarify';
    const lines = photoCandidates.slice(0, 3).map((c, i) => (i + 1) + '. *' + c.product_name + '*');
    reply = "I'm not sure which catalogue product this photo is. Reply with a number:\n\n" + lines.join('\n') + '\n\nType *menu* to return to main menu.';
    monitor = monitorSql('low_confidence', 'clarify', confidence, 'photo_pick');
  } else {
    intent = 'clarify';
    reply = "I couldn't match that photo to a catalogue product.\n\nType *menu* to return to main menu.";
    monitor = monitorSql('low_confidence', 'clarify', confidence, 'photo_none');
  }
  if (exactPhoto) {
    intent = 'product_search';
    reply = card(exactPhoto) + footer();
    lastProduct = exactPhoto;
    matchedProductId = exactPhoto.id;
    monitor = '';
  }
}

if (!ai.abuse && !photoMode && intent === 'product_search') {
  const ids = (Array.isArray(ai.matchIds) ? ai.matchIds : []).map(Number).filter(id => byId(id));
  let chosen = ids.map(byId);
  if (!chosen.length) {
    const replyLc = reply.toLowerCase();
    chosen = products.filter(p => p.product_name && replyLc.includes(String(p.product_name).toLowerCase()));
  }
  chosen = chosen.slice(0, 3);
  if (chosen.length) {
    reply = chosen.map((p, i) => '╭─ *' + (i + 1) + '. ' + p.product_name + '*\n│ 💰 *Price:* PKR ' + Number(p.price) + '\n│ 💳 *Bank Transfer:* PKR ' + Math.round(Number(p.price) * 0.95) + '\n╰ ⚡ *Status:* ' + (p.stock || 'In stock') + ' | ' + (p.condition || 'New')).join('\n\n') + footer();
    lastProduct = chosen[0];
    matchedProductId = chosen[0].id;
  } else {
    intent = 'clarify';
    reply = "I couldn't find that in the catalogue.\n\nType *menu* to return to main menu.";
    monitor = monitor || monitorSql('fallback', 'clarify', confidence, 'search_none');
  }
}

if (!ai.abuse && !photoMode && intent === 'buy') {
  const valid = items.filter(it => byId(it.productId) && it.qty >= 1 && it.qty <= 999);
  if (confidence < 0.45 || (!valid.length && !useLastProduct)) {
    intent = 'clarify';
    items = [];
    useLastProduct = false;
    reply = 'Please tell me which product you want!\n\nType *catalogue* to keep browsing.\nType *menu* to return to main menu.';
    monitor = monitor || monitorSql('low_confidence', 'clarify', confidence, 'buy_unclear');
  } else {
    items = valid;
  }
}

if ((intent === 'greeting' || intent === 'menu') && !reply.includes('1️⃣')) {
  reply = (intent === 'greeting' ? "Hi! I'm Arik, your smart home assistant at WaltonMarket.\n\n" : '') + MENU;
}

if (intent === 'installation' && !reply) {
  reply = 'Great! Let me prepare a smart home quotation for you.';
}

function phraseCart(text) {
  const t = String(text || '').toLowerCase().replace(/\s+/g, ' ').trim();
  if (/^remove\s+\d{1,2}$/.test(t)) return null;
  if (/\b(badhe|more)\b/.test(t) && !/\b(sirf|only|bas)\b/.test(t)) return null;
  const setM = t.match(/\b(?:sirf|only|bas)\s+(\d{1,3})\b/);
  if (setM && /\b(chahiye|chahye|chahta|chahti|want|need|nahi)\b/.test(t)) {
    return { cartOp: 'set', qty: Number(setM[1]) };
  }
  if (/\b(remove|hatao|nikal|nikalo)\b/.test(t)) {
    const nums = t.match(/\d{1,3}/g) || [];
    const q = nums.length ? Number(nums[nums.length - 1]) : 0;
    if (q >= 1 && q <= 999) return { cartOp: 'remove', qty: q };
  }
  return null;
}
function guessProduct(text, list, cart) {
  const t = String(text || '').toLowerCase();
  const scoreOf = (name) => {
    const words = String(name || '').toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length > 3 && !['wifi', 'smart', 'with', 'touch'].includes(w));
    let s = 0;
    for (const w of words) if (t.includes(w)) s += 1;
    return s;
  };
  let best = null;
  let score = 0;
  for (const c of cart || []) {
    const s = scoreOf(c.name);
    if (s > score) {
      score = s;
      best = list.find(p => p.product_name === c.name) || null;
    }
  }
  if (score >= 1 && best) return best;
  for (const p of list) {
    const s = scoreOf(p.product_name);
    if (s > score) { score = s; best = p; }
  }
  return score >= 1 ? best : null;
}
function woodenIndoor(text) {
  const t = String(text || '').toLowerCase();
  return /indoor|andaroon|bedroom|kamre|kamray/.test(t) && /wood|wooden|lakdi|lakri|lakkri/.test(t) && /lock|darwaza|\bdoor\b/.test(t);
}

if (!playful && !forceTranslate && !woodenIndoor(customerText)) {
  const phrase = phraseCart(customerText);
  if (phrase) {
    intent = 'buy';
    cartOp = phrase.cartOp;
    qty = phrase.qty;
    const named = guessProduct(prev.message || customerText, products, prev.cart);
    if (named) items = [{ productId: Number(named.id), qty: qty }];
    else if (Array.isArray(prev.cart) && prev.cart.length === 1) {
      const only = products.find(p => p.product_name === prev.cart[0].name);
      if (only) items = [{ productId: Number(only.id), qty: qty }];
    } else if (prev.lastProduct && prev.lastProduct.id) {
      items = [{ productId: Number(prev.lastProduct.id), qty: qty }];
      useLastProduct = true;
    }
    clearForms = false;
  } else if (/\b(badhe|more)\b/.test(customerText) && !/\b(sirf|only|bas)\b/.test(customerText)) {
    cartOp = 'add';
  } else if (intent === 'buy' && cartOp === 'none') {
    cartOp = 'add';
  }
}
if (/^remove\s+\d{1,2}$/.test(customerText.trim())) {
  intent = 'cart_remove';
  items = [];
  cartOp = 'none';
  useLastProduct = false;
}
if (!playful && !forceTranslate && woodenIndoor(customerText)) {
  const locks = products.filter(p => /door lock/i.test(p.product_name || ''));
  const indoor = locks.find(p => /bedroom/i.test(String(p.room || '')) && !/outdoor/i.test(String(p.product_name || ''))) || null;
  const name = indoor ? indoor.product_name : 'Smart WiFi Door Lock - 5 Way Unlock';
  intent = 'product_search';
  items = [];
  useLastProduct = false;
  cartOp = 'none';
  if (indoor) {
    lastProduct = indoor;
    matchedProductId = indoor.id;
  }
  reply = 'No catalogue lock is listed for a wooden door. The closest indoor option is *' + name + '*' + (indoor ? ' (PKR ' + Number(indoor.price) + ')' : '') + ', and its room list includes Bedroom.\n\nOutdoor door locks are for the main or front door. I am not using those as the wooden indoor match.\n\nType *menu* to return to main menu.';
}
if (playful) {
  abuseCount = Number(prev.abuseCount || 0);
  abuseLock = false;
  clearForms = false;
  items = [];
  intent = 'greeting';
  reply = "Haha, shukriya. Main products, cart, aur quotation mein madad ke liye hoon.\n\n" + MENU;
}
if (forceTranslate && !playful) {
  intent = 'translate';
  items = [];
  useLastProduct = false;
  cartOp = 'none';
  const badPlace = /maps\.app|goo\.gl|jinnah|physical store/i.test(reply);
  if (!reply || badPlace) {
    const source = lastAssistantText();
    reply = source
      ? 'Main pehle wale jawab ko Urdu mein dohraata hoon:\n\n' + source
      : 'Pehle koi jawab nahi tha jo main Urdu mein dohra sakoon.\n\nType *menu* for options.';
  }
}

let buyingStage = String(ai.buyingStage || '').toLowerCase();
const stages = ['explorer', 'comparer', 'ready_to_buy', 'hesitation', 'existing_customer'];
if (!stages.includes(buyingStage)) {
  if (intent === 'buy' || intent === 'checkout') buyingStage = 'ready_to_buy';
  else if (intent === 'product_search') buyingStage = 'comparer';
  else buyingStage = 'explorer';
}
let objection = String(ai.objection || 'none').toLowerCase().replace(/\s+/g, '_');
if (objection === 'installation') objection = 'installation_fear';
const objections = ['none', 'price', 'trust', 'installation_fear', 'compatibility', 'warranty'];
if (!objections.includes(objection)) objection = 'none';
if (/warranty|waranti|guarantee/.test(customerText) && /bharosa|trust|confus|hesitat|dar|nahi/.test(customerText)) {
  objection = /bharosa|trust/.test(customerText) ? 'trust' : 'warranty';
  buyingStage = 'hesitation';
  if (intent === 'support') intent = 'product_search';
}
if (!playful && !forceTranslate && (objection === 'trust' || objection === 'warranty' || objection === 'installation_fear') && buyingStage === 'hesitation' && !/\*human\*/i.test(reply)) {
  reply += '\n\nAgar aap kisi insaan se baat karna chahen to *human* likh dein.';
}
let boardIntent = String(ai.boardIntent || 'general').slice(0, 60);
if (intent === 'buy' || cartOp === 'set' || cartOp === 'remove' || intent === 'cart_remove') boardIntent = 'cart';
else if (intent === 'product_search') boardIntent = 'product_recommendation';
else if (intent === 'support') boardIntent = 'human_escalation';
let leadDelta = 0;
if (intent === 'product_search') leadDelta += 10;
if (intent === 'buy') leadDelta += 20;
if (intent === 'checkout') leadDelta += 15;
if (objection !== 'none') leadDelta -= 5;

const out = {
  ...prev,
  customerImageB64: '',
  photoCandidates: photoCandidates.map(c => ({ id: c.id, product_name: c.product_name })),
  intent,
  message: prev.message,
  lowerMsg: prev.lowerMsg,
  translated: prev.lowerMsg,
  sessionId: prev.sessionId,
  session: prev.session,
  history: prev.history,
  orderState: clearForms ? null : prev.orderState,
  orderData: prev.orderData,
  lastProduct,
  matchedProductId,
  cart: prev.cart,
  currentPage: prev.currentPage,
  products,
  company: prev.company,
  isNewSession: prev.isNewSession,
  reply,
  items,
  useLastProduct,
  qty,
  confidence,
  clearForms,
  abuseCount,
  abuseLock,
  quoteState: clearForms ? null : prev.quoteState,
  quoteData: clearForms ? {} : prev.quoteData,
  monitorSql: monitor,
  cartOp,
  buyingStage,
  objection,
  boardIntent,
  leadDelta,
  latencyMs,
  promptTokens,
  outputTokens,
  modelName: 'gemini-2.5-flash'
};
return [{ json: out }];
