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
