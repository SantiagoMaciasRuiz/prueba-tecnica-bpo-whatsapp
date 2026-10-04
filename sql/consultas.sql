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

-- La consulta conserva cualquier estado desconocido. read, delivered y failed
-- no se fuerzan a sumar 100%; el denominador incluye todos los estados outgoing.

-- Consulta 2 --
-- SLA de respuesta: primera activity u outgoing posterior a cada incoming.
-- Parámetros opcionales:
--   $1 = timestamp inicial aplicado a los incoming analizados
--   $2 = timestamp final exclusivo aplicado a los incoming analizados
--   $3 = status del incoming (NULL para todos)
-- La secuencia se construye sobre todos los eventos antes de aplicar el rango a
-- los incoming. Así, una acción posterior fuera del rango no se pierde.

WITH incoming_events AS (
    SELECT m.*
    FROM messages_clean m
    WHERE m.message_type = 'incoming'
), candidate_actions AS (
    SELECT
        i.id AS incoming_id,
        i.conversation_id,
        i.created_at AS incoming_at,
        a.id AS response_id,
        a.message_type AS response_type,
        a.created_at AS response_at,
        ROW_NUMBER() OVER (
            PARTITION BY i.id
            ORDER BY a.created_at, a.id
        ) AS response_rank
    FROM incoming_events i
    JOIN messages_clean a
      ON a.conversation_id = i.conversation_id
     AND a.message_type IN ('activity', 'outgoing')
     AND a.created_at IS NOT NULL
     AND (
            a.created_at > i.created_at
            OR (a.created_at = i.created_at AND a.id > i.id)
         )
), first_actions AS (
    SELECT *
    FROM candidate_actions
    WHERE response_rank = 1
), response_detail AS (
    SELECT
        i.id AS incoming_id,
        i.conversation_id,
        i.created_at AS incoming_at,
        i.status AS incoming_status,
        fa.response_id,
        fa.response_type,
        fa.response_at,
        EXTRACT(EPOCH FROM (fa.response_at - i.created_at)) / 60.0 AS response_minutes
    FROM incoming_events i
    LEFT JOIN first_actions fa ON fa.incoming_id = i.id
    WHERE ($1::timestamp IS NULL OR i.created_at >= $1::timestamp)
      AND ($2::timestamp IS NULL OR i.created_at < $2::timestamp)
      AND ($3::text IS NULL OR i.status = $3::text)
)
SELECT
    COUNT(*) AS total_incoming,
    COUNT(response_at) AS responded,
    COUNT(*) - COUNT(response_at) AS unanswered,
    ROUND(AVG(response_minutes)::numeric, 2) AS average_minutes,
    ROUND((PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY response_minutes))::numeric, 2) AS median_minutes,
    ROUND(MIN(response_minutes)::numeric, 2) AS min_minutes,
    ROUND(MAX(response_minutes)::numeric, 2) AS max_minutes,
    ROUND((PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_minutes))::numeric, 2) AS p95_minutes
FROM response_detail;

-- Para auditar cada incoming, ejecutar el mismo CTE hasta response_detail y
-- reemplazar el SELECT final por: SELECT * FROM response_detail ORDER BY incoming_at, incoming_id.

--Consulta 3 --

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
