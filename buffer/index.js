const http = require('http');

const PORT = process.env.PORT || 3002;
const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL || 'http://n8n:5678/webhook/ai-chat';
const WAHA_URL = process.env.WAHA_URL || 'http://waha:3000';
const WAHA_API_KEY = process.env.WAHA_API_KEY || 'YOUR_WAHA_API_KEY';
const DEBOUNCE_MS = parseInt(process.env.DEBOUNCE_MS || '20000', 10);
const MAX_WAIT_MS = parseInt(process.env.MAX_WAIT_MS || '35000', 10);

const buffers = new Map();

function sendTypingIndicator(chatId) {
  try {
    const data = JSON.stringify({
      session: 'default',
      chatId: chatId
    });
    const url = new URL('/api/startTyping', WAHA_URL);
    const req = http.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': WAHA_API_KEY,
        'Content-Length': Buffer.byteLength(data)
      }
    });
    req.on('error', (err) => {
      console.error('[startTyping error]:', err.message);
    });
    req.write(data);
    req.end();
  } catch (e) {
    console.error('[startTyping exception]:', e.message);
  }
}

function forwardToN8n(payload) {
  return new Promise((resolve, reject) => {
    try {
      const data = JSON.stringify(payload);
      const url = new URL(N8N_WEBHOOK_URL);
      const req = http.request(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        }
      }, (res) => {
        let respData = '';
        res.on('data', chunk => respData += chunk);
        res.on('end', () => {
          console.log(`[Forwarded to n8n] Status: ${res.statusCode}`);
          resolve(respData);
        });
      });
      req.on('error', (err) => {
        console.error('[n8n forward error]:', err.message);
        reject(err);
      });
      req.write(data);
      req.end();
    } catch (e) {
      console.error('[forwardToN8n exception]:', e.message);
      reject(e);
    }
  });
}

function flushBuffer(chatId) {
  const entry = buffers.get(chatId);
  if (!entry) return;
  buffers.delete(chatId);
  if (entry.timer) clearTimeout(entry.timer);

  const combinedBody = entry.messages.join('\n');
  const finalPayload = entry.lastPayload;
  if (finalPayload && finalPayload.payload) {
    finalPayload.payload.body = combinedBody;
  }

  console.log(`[Flushing Buffer for ${chatId}]: Aggregated ${entry.messages.length} message(s): ${combinedBody}`);
  forwardToN8n(finalPayload).catch(err => {
    console.error(`[Flush error for ${chatId}]:`, err.message);
  });
}

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && (req.url === '/webhook/ai-chat' || req.url === '/')) {
    let body = '';
    req.on('data', chunk => {
      body += chunk;
    });

    req.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'received' }));

      try {
        const json = JSON.parse(body);
        const payload = json.payload || {};
        const from = payload.from;
        const fromMe = payload.fromMe === true || payload.fromMe === 'true';
        const msgText = payload.body;

        if (fromMe || !from || !msgText || typeof msgText !== 'string') {
          console.log(`[Immediate Forward] fromMe=${fromMe}, from=${from}`);
          forwardToN8n(json).catch(() => {});
          return;
        }

        sendTypingIndicator(from);

        const now = Date.now();
        let entry = buffers.get(from);

        if (!entry) {
          entry = {
            messages: [msgText.trim()],
            lastPayload: json,
            firstMessageTime: now,
            timer: null
          };
          buffers.set(from, entry);
        } else {
          entry.messages.push(msgText.trim());
          entry.lastPayload = json;
          if (entry.timer) clearTimeout(entry.timer);
        }

        const elapsed = now - entry.firstMessageTime;
        if (elapsed >= MAX_WAIT_MS) {
          console.log(`[Max wait reached for ${from}] Flushing immediately.`);
          flushBuffer(from);
        } else {
          const waitTime = Math.min(DEBOUNCE_MS, MAX_WAIT_MS - elapsed);
          console.log(`[Buffering for ${from}] ${entry.messages.length} msg(s). Will flush in ${waitTime / 1000}s`);
          entry.timer = setTimeout(() => {
            flushBuffer(from);
          }, waitTime);
        }
      } catch (err) {
        console.error('[Webhook processing error]:', err.message);
      }
    });
  } else if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', bufferedChats: buffers.size }));
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[waltonmarket-buffer] Listening on port ${PORT}`);
  console.log(`[Target n8n] -> ${N8N_WEBHOOK_URL}`);
  console.log(`[WAHA] -> ${WAHA_URL}`);
});
