#!/bin/bash
# Last-24-hour counts for Arik router fallbacks. No message text.
docker exec waltonmarket-postgres-1 psql -U walton -d waltonmarket -P pager=off -c "
SELECT kind, count(*) AS turns
FROM arik_turn_monitor
WHERE created_at > now() - interval '24 hours'
GROUP BY kind
ORDER BY turns DESC, kind;
"
