// Clear escalation on the old 30 minute / menu rule only when this chat is not abuse-locked.
const bapLock = bap.abuseLock === true || (bap.session && bap.session.abuse_lock === true) || prev.abuseLock === true;
const escalatedAt = (bap.session && bap.session.escalated_at) || null;
let clearEscalation = false;
if (escalatedAt && !bapLock) {
  const mins = (Date.now() - new Date(escalatedAt).getTime()) / 60000;
  if (mins >= 30 || bap.lowerMsg === 'menu') clearEscalation = true;
}

const clearForms = prev.clearForms === true || bap.clearForms === true;
const savedOrderState = clearForms ? null : orderState;
const rawCount = prev.abuseCount != null ? prev.abuseCount : bap.abuseCount;
const abuseCount = rawCount == null || rawCount === '' ? null : Number(rawCount);
const setLock = prev.abuseLock === true || bap.abuseLock === true;
const pageNum = prev.currentPage ?? bap.currentPage ?? 0;
const monitor = String(prev.monitorSql || bap.monitorSql || '').trim();

let extraCols = '';
let extraVals = '';
let extraSet = '';
if (setLock) {
  extraCols += ', escalated_at, abuse_lock';
  extraVals += ', NOW(), true';
  extraSet += ',\n  escalated_at = NOW(),\n  abuse_lock = true';
} else if (clearEscalation) {
  extraCols += ', escalated_at';
  extraVals += ', NULL';
  extraSet += ',\n  escalated_at = NULL';
}
if (clearForms) {
  extraCols += ', quote_state, quote_data';
  extraVals += ", NULL, '{}'::jsonb";
  extraSet += ",\n  quote_state = NULL,\n  quote_data = '{}'::jsonb";
}
if (abuseCount !== null && Number.isFinite(abuseCount)) {
  extraCols += ', abuse_count';
  extraVals += ', ' + String(abuseCount);
  extraSet += ',\n  abuse_count = ' + String(abuseCount);
}

const baseSql = `INSERT INTO sessions (session_id, history, order_state, order_data, last_product, cart, current_page${extraCols})
VALUES (
  '${esc(sessionId)}',
  '${esc(trimmedHistory)}'::jsonb,
  ${savedOrderState ? "'" + esc(savedOrderState) + "'" : 'NULL'},
  '${esc(prev.orderData || bap.orderData || {})}'::jsonb,
  '${esc(lastProduct)}'::jsonb,
  '${esc(Array.isArray(prev.cart) ? prev.cart : (Array.isArray(bap.cart) ? bap.cart : []))}'::jsonb,
  ${Number(pageNum) || 0}${extraVals}
)
ON CONFLICT (session_id) DO UPDATE SET
  history = EXCLUDED.history,
  order_state = EXCLUDED.order_state,
  order_data = EXCLUDED.order_data,
  last_product = EXCLUDED.last_product,
  cart = EXCLUDED.cart,
  current_page = EXCLUDED.current_page${extraSet}`;

const phaseRow = {
  intent: prev.intent || bap.intent || '',
  buyingStage: prev.buyingStage || bap.buyingStage || 'explorer',
  objection: prev.objection || bap.objection || 'none',
  boardIntent: prev.boardIntent || bap.boardIntent || 'general',
  leadDelta: prev.leadDelta != null ? prev.leadDelta : bap.leadDelta,
  latencyMs: prev.latencyMs != null ? prev.latencyMs : bap.latencyMs,
  promptTokens: prev.promptTokens != null ? prev.promptTokens : bap.promptTokens,
  outputTokens: prev.outputTokens != null ? prev.outputTokens : bap.outputTokens,
  confidence: prev.confidence != null ? prev.confidence : bap.confidence,
  modelName: prev.modelName || bap.modelName || 'gemini-2.5-flash'
};
const sqlQuery = phaseWrap(baseSql, phaseRow, sessionId, monitor);

return [{json: {
  sqlQuery,
  reply: prev.reply
}}];
