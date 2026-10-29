function phaseWrap(baseSql, row, sessionId, monitorSql) {
  const q = (s) => String(s == null ? '' : s).replace(/'/g, "''").slice(0, 180);
  const nint = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? String(Math.trunc(n)) : '0';
  };
  const conf = Number(row && row.confidence);
  const confSql = Number.isFinite(conf) ? String(conf) : 'NULL';
  const delta = Math.max(-100, Math.min(100, Math.round(Number(row && row.leadDelta || 0))));
  const stage = q((row && row.buyingStage) || 'explorer');
  const objection = q((row && row.objection) || 'none');
  const board = q((row && row.boardIntent) || 'general');
  const intent = q((row && row.intent) || '');
  const model = q((row && row.modelName) || 'gemini-2.5-flash');
  const mon = String(monitorSql || '').trim().replace(/;+\s*$/, '');
  const monCte = mon ? `mon AS (\n${mon}\nRETURNING id\n),` : '';
  return `WITH saved AS (${baseSql} RETURNING session_id),
${monCte}
mem AS (
  INSERT INTO arik_session_memory (session_id, lead_score, buying_stage, objection, last_board_intent, turn_count, updated_at)
  SELECT s.session_id,
    LEAST(100, GREATEST(0, COALESCE(old.lead_score, 0) + (${delta}))),
    '${stage}',
    '${objection}',
    '${board}',
    COALESCE(old.turn_count, 0) + 1,
    NOW()
  FROM saved s
  LEFT JOIN arik_session_memory old ON old.session_id = s.session_id
  ON CONFLICT (session_id) DO UPDATE SET
    lead_score = EXCLUDED.lead_score,
    buying_stage = EXCLUDED.buying_stage,
    objection = EXCLUDED.objection,
    last_board_intent = EXCLUDED.last_board_intent,
    turn_count = EXCLUDED.turn_count,
    updated_at = NOW()
  RETURNING session_id
)
INSERT INTO arik_observability (session_id, intent, board_intent, buying_stage, objection, confidence, latency_ms, prompt_tokens, output_tokens, model)
SELECT s.session_id, '${intent}', '${board}', '${stage}', '${objection}', ${confSql}, ${nint(row && row.latencyMs)}, ${nint(row && row.promptTokens)}, ${nint(row && row.outputTokens)}, '${model}'
FROM saved s
WHERE EXISTS (SELECT 1 FROM mem)`;
}
