# Escalabilidad Y FinOps — 50 Supervisores, 5 Minutos

## Escenario Planteado

El escenario solicitado considera 50 usuarios actualizando el dashboard cada 5 minutos:

```
50 usuarios × 12 actualizaciones/hora = 600 consultas/hora
```

Esto equivale a aproximadamente una consulta cada 6 segundos en promedio si la carga se distribuye uniformemente.

## Carga Actual de Referencia

Las consultas validadas en este proyecto sobre 3.687 registros tienen los siguientes tiempos de ejecución (`EXPLAIN ANALYZE` en PostgreSQL 16 Docker local):

| Consulta | Tiempo |
|---|---:|
| `01_delivery_funnel.sql` | ~3,67 ms |
| `02_response_sla.sql` | ~12,45 ms |
| `03_hourly_incoming.sql` | ~1,52 ms |

La consulta SLA (`02_response_sla.sql`) es la más costosa porque construye la secuencia de primera acción posterior por conversación usando un JOIN con `ROW_NUMBER()`. Ejecutarla 600 veces por hora de forma independiente multiplica trabajo innecesariamente a medida que el volumen de datos crece.

## Riesgo Principal a Escala

Con un crecimiento proporcional del dataset:

- **3.687 registros actuales**: consulta SLA ~12 ms → 600 ejecuciones = ~7,2 segundos de cómputo acumulado por hora.
- **100.000 registros** (estimación de crecimiento mensual en operación activa): sin optimización, el tiempo puede escalar significativamente si el plan cambia de `Index Scan` a `Seq Scan`.

El índice `(conversation_id, created_at, id)` ya definido en `sql/schema.sql` es el principal control de rendimiento para la consulta SLA.

## Estrategia de Bajo Costo (Cero Sobrecoste Cloud)

### 1. Cache de Resultados en Metabase (TTL = 5 minutos)

Fijando el TTL de cache en 300 segundos:

- Los 50 usuarios leen el resultado cacheado en memoria.
- La base de datos ejecuta las consultas pesadas **12 veces por hora** en lugar de 600.
- **Reducción del 98% en carga de cómputo** del motor relacional sin ningún cambio de infraestructura.

### 2. Vistas Materializadas en PostgreSQL

```sql
-- Vista para SLA (la más costosa)
CREATE MATERIALIZED VIEW mv_response_sla AS
  -- mismo CTE de 02_response_sla.sql hasta response_detail
  SELECT * FROM response_detail;

CREATE UNIQUE INDEX ON mv_response_sla(incoming_id);

-- Refrescar cada 5 minutos (cron o pg_cron)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_response_sla;
```

```sql
-- Vista para funnel de entrega (simple, para consistencia)
CREATE MATERIALIZED VIEW mv_delivery_summary AS
SELECT status, COUNT(*) AS message_count
FROM messages_clean
WHERE message_type = 'outgoing'
GROUP BY status;

REFRESH MATERIALIZED VIEW CONCURRENTLY mv_delivery_summary;
```

Con `CONCURRENTLY`, el refresco no bloquea lecturas activas del dashboard.

### 3. Connection Pooling

Configurar un límite explícito de conexiones en PostgreSQL para evitar 50 conexiones simultáneas abiertas:

```
# postgresql.conf
max_connections = 50
# PgBouncer o similar como pooler si se supera
```

Metabase gestiona su propio pool; con el cache activo, la presión de conexiones cae drásticamente.

### 4. Índices Existentes (ya validados)

Los tres índices definidos en `sql/schema.sql` son suficientes para el volumen actual y el escenario planteado:

| Índice | Propósito |
|---|---|
| `(conversation_id, created_at, id)` | JOIN temporal en consulta SLA |
| `(message_type, status)` | Filtro funnel y demanda |
| `(created_at)` | Filtros de rango temporal |

**No agregar índices adicionales sin evidencia de plan de ejecución.**

## Arquitectura Recomendada

### Fase actual (volumen de prueba)

```
prueba.txt → ETL Python → messages_clean (PostgreSQL) → Metabase Dashboard
```

PostgreSQL local y Metabase en Docker son suficientes. No se justifica infraestructura adicional.

### Fase de escalado (operación real)

```
WhatsApp API → ETL incremental → messages_clean (PostgreSQL)
                                        ↓
                              mv_response_sla (REFRESH cada 5 min)
                              mv_delivery_summary (REFRESH cada 5 min)
                                        ↓
                              Metabase (cache TTL = 5 min)
                                        ↓
                              50 supervisores (leen desde cache)
```

## Métricas Operativas a Monitorear

| Métrica | Umbral de alerta |
|---|---|
| Duración P95 de consultas Metabase | > 2.000 ms |
| Conexiones activas PostgreSQL | > 40 simultáneas |
| Tiempo de refresco mv_response_sla | > 30 s |
| % respuestas desde cache Metabase | < 80% |
| Crecimiento diario de `messages_clean` | > 50.000 filas/día |

## Criterio de Decisión

**No materializar todo por anticipado sin medir.**

1. Activar cache de Metabase primero (costo cero, impacto inmediato).
2. Medir duración real de consultas bajo carga con 50 usuarios simultáneos.
3. Si SLA P95 de las consultas supera el presupuesto de latencia, crear `mv_response_sla`.
4. Si el crecimiento de datos supera 100.000 registros, revisar `EXPLAIN (ANALYZE, BUFFERS)` y ajustar estrategia de partición o archivado.
