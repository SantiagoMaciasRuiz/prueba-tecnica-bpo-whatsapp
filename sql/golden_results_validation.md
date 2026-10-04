# Validación SQL Contra Python

## Estado de ejecución

Los golden results provienen de [reports/pre_sql_analysis.json](../reports/pre_sql_analysis.json). Las consultas se ejecutaron contra PostgreSQL 16 mediante Docker Compose y la comparación real quedó registrada en [reports/sql_validation_report.json](../reports/sql_validation_report.json). El cliente `psql` no está instalado directamente en Windows, pero no fue necesario porque la validación utilizó `psycopg2` y `COPY FROM STDIN` contra el contenedor PostgreSQL.

## Golden results

| Indicador | Python |
|---|---:|
| Registros | 3687 |
| IDs únicos | 3687 |
| Conversaciones | 2153 |
| Incoming | 430 |
| Incoming con respuesta | 369 |
| Incoming sin respuesta | 61 |
| Outgoing | 2507 |
| Outgoing read | 708 |
| Outgoing delivered | 83 |
| Outgoing failed | 1396 |
| SLA promedio, minutos | 127.24 |
| SLA mediano, minutos | 0.68 |
| SLA P95, minutos | 1152.68 |
| SLA máximo, minutos | 2695.82 |
| Incoming total de curva horaria | 430 |

## Comparación esperada

### Funnel

`01_delivery_funnel.sql`, con los tres parámetros en `NULL`, debe devolver todos los estados outgoing observados:

- delivered: 83, 3.31%
- failed: 1396, 55.68%
- read: 708, 28.24%
- sent: 320, 12.76%
- denominador: 2507

La suma de porcentajes de read, delivered y failed no es 100% porque existen 320 outgoing `sent`.

### SLA

`02_response_sla.sql`, con parámetros `NULL`, debe producir:

- total incoming: 430
- responded: 369
- unanswered: 61
- average: aproximadamente 127.24
- median: aproximadamente 0.68
- P95: aproximadamente 1152.68
- max: aproximadamente 2695.82

Las diferencias aceptables se limitan al redondeo decimal. Una diferencia de conteos indicaría una discrepancia de orden, condición de evento posterior o filtro aplicado antes de construir la secuencia.

### Curva horaria

`03_hourly_incoming.sql` debe devolver 24 filas y la suma de `incoming_count` debe ser 430. Las horas sin mensajes deben contener cero y no representan mensajes inventados.

## Índices recomendados

- `(conversation_id, created_at, id)`: búsqueda y orden de acciones dentro de cada conversación.
- `(message_type, status)`: filtro de funnel y selección de incoming/outgoing.
- `(created_at)`: filtros temporales posteriores.

No se recomienda crear índices adicionales hasta observar planes `EXPLAIN ANALYZE` con el volumen real.
