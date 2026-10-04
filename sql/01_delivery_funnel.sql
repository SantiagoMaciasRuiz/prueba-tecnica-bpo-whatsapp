-- Funnel de entrega para outgoing.
-- Parámetros opcionales de psql/prepared statement:
--   $1 = timestamp inicial (NULL para no filtrar)
--   $2 = timestamp final exclusivo (NULL para no filtrar)
--   $3 = status específico (NULL para conservar todos los estados)
-- El denominador es el total outgoing después de los filtros de fecha y, si se informa, estado.

WITH filtered_outgoing AS (
    SELECT status
    FROM messages_clean
    WHERE message_type = 'outgoing'
      AND ($1::timestamp IS NULL OR created_at >= $1::timestamp)
      AND ($2::timestamp IS NULL OR created_at < $2::timestamp)
      AND ($3::text IS NULL OR status = $3::text)
), totals AS (
    SELECT COUNT(*)::numeric AS outgoing_total
    FROM filtered_outgoing
)
SELECT
    fo.status,
    COUNT(*) AS message_count,
    ROUND(100.0 * COUNT(*) / NULLIF(t.outgoing_total, 0), 2) AS percentage
FROM filtered_outgoing fo
CROSS JOIN totals t
GROUP BY fo.status, t.outgoing_total
ORDER BY fo.status;
