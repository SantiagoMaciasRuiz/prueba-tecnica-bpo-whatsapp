-- Curva horaria de incoming.
-- Parámetros opcionales:
--   $1 = timestamp inicial
--   $2 = timestamp final exclusivo
--   $3 = status (NULL para todos)
-- generate_series muestra las 24 horas; una hora sin mensajes queda en cero.

WITH params AS (
    SELECT $1::timestamp AS start_at, $2::timestamp AS end_at, $3::text AS status_filter
), incoming_by_hour AS (
    SELECT EXTRACT(HOUR FROM m.created_at)::integer AS hour, COUNT(*) AS incoming_count
    FROM messages_clean m
    CROSS JOIN params p
    WHERE m.message_type = 'incoming'
      AND ($1::timestamp IS NULL OR m.created_at >= p.start_at)
      AND ($2::timestamp IS NULL OR m.created_at < p.end_at)
      AND (p.status_filter IS NULL OR m.status = p.status_filter)
    GROUP BY EXTRACT(HOUR FROM m.created_at)::integer
), totals AS (
    SELECT COALESCE(SUM(incoming_count), 0)::numeric AS incoming_total
    FROM incoming_by_hour
)
SELECT
    hours.hour,
    COALESCE(ibh.incoming_count, 0) AS incoming_count,
    ROUND(100.0 * COALESCE(ibh.incoming_count, 0) / NULLIF(t.incoming_total, 0), 2) AS percentage
FROM generate_series(0, 23) AS hours(hour)
LEFT JOIN incoming_by_hour ibh ON ibh.hour = hours.hour
CROSS JOIN totals t
ORDER BY hours.hour;
