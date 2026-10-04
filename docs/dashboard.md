# Dashboard Operativo En Metabase

## Objetivo

El dashboard **Supervisor operativo - Mensajeria** responde:

1. Si la campaña está llegando.
2. Si el equipo responde oportunamente.
3. En qué horarios se concentra la demanda.

Metabase se ejecuta localmente en `http://localhost:3000` y utiliza PostgreSQL como fuente.

## Fuente

- Base: `etl_db`
- Tabla validada: `messages_clean`
- Servidor PostgreSQL desde Metabase: `postgres:5432`
- El prompt funcional menciona `messages`, pero el esquema validado creó `messages_clean`; no se duplicó ni modificó la tabla para ocultar esa diferencia.

## Levantar Y Configurar

```bash
docker compose up -d --wait
python scripts/setup_metabase.py
```

La configuración crea o actualiza:

- Conexión `ETL PostgreSQL`.
- Dashboard `Supervisor operativo - Mensajeria`.
- 22 preguntas y tarjetas.
- Filtros de fecha, status y tipo de mensaje.

La contraseña del usuario local se lee desde `.env`. No se documentan credenciales en este archivo.

## Filtros

- **Fecha inicial:** límite inferior de `created_at`.
- **Fecha final:** límite superior inclusivo mediante el día siguiente.
- **Status:** `sent`, `delivered`, `read`, `failed`; se conserva cualquier valor adicional existente.
- **Tipo de mensaje:** `incoming`, `outgoing`, `activity`.

Los filtros se implementan como variables nativas de Metabase y no requieren editar SQL en la interfaz.

## Bloques Del Dashboard

### Campaña

- Total outgoing.
- Read.
- Delivered.
- Failed.
- Failure rate.
- Distribución completa de status outgoing.
- Errores de entrega sobre mensajes failed.
- Fallos por template, usando el volumen absoluto de `failed_count`.
- Tasa de fallo por template, usando `failure_rate` en porcentaje.
- Sin template: outgoing sin `template_name` identificado.
- Cobertura template: outgoing con `template_name` identificado / total outgoing.

Los dos gráficos de templates están separados para evitar mezclar conteos de hasta `1.352` con porcentajes de `0` a `100`. Así, `lanzamiento_` puede leerse correctamente como volumen y como tasa del `100%`.
Las métricas de template usan únicamente los outgoing con template identificado; el dashboard muestra explícitamente el volumen y la cobertura que quedan fuera.

### SLA

- Incoming.
- Respondidos.
- Sin respuesta.
- Response rate.
- SLA promedio.
- SLA mediano.
- SLA P95.
- Respuesta por `message_category`.

El SLA busca la primera acción posterior `activity` u `outgoing` dentro de la misma conversación y usa orden determinista `created_at, id`.

### Demanda

- Incoming por categoría.
- Incoming por hora, con las 24 horas `00` a `23`.
- Incoming y sin respuesta por hora.

Las horas sin registros se muestran con cero; no representan mensajes inventados.

## Golden Results Sin Filtros

Resultados validados sin filtros activos, reconciliados con Python, PostgreSQL y Metabase API:

| Métrica | Resultado |
|---|---:|
| Total outgoing | 2.507 |
| Read | 708 |
| Delivered | 83 |
| Failed | 1.396 |
| Sent | 320 |
| Sin template | 867 |
| Cobertura template | 65,42% |
| Incoming | 430 |
| Respondidos | 369 |
| Sin respuesta | 61 |
| SLA promedio | 127,24 min |
| SLA mediana | 0,68 min |
| SLA P95 | 1.152,68 min |
| SLA máximo | 2.695,82 min |
| Total curva horaria | 430 |

Reporte de validación completo: [`reports/sql_validation_report.json`](../reports/sql_validation_report.json)  
Auditoría integral: [`reports/final_audit.md`](../reports/final_audit.md)

## Validación Ejecutada

El script [scripts/validate_metabase_dashboard.py](../scripts/validate_metabase_dashboard.py) ejecuta las tarjetas mediante la API local de Metabase y genera [reports/metabase_dashboard_validation.json](../reports/metabase_dashboard_validation.json).

Validaciones realizadas:

- 22 tarjetas presentes en el dashboard.
- 4 filtros configurados.
- KPIs sin filtros contra golden results.
- Status `failed` devuelve `1396` outgoing.
- Status `read` devuelve `708` outgoing.
- El rango de fecha modifica el resultado.
- La curva horaria devuelve 24 filas y suma `430`.
- Tiempos aproximados de las preguntas KPI: aproximadamente `39` a `106` ms en la ejecución local observada.

## Definiciones De KPIs

- **Failure rate:** `failed outgoing / total outgoing`, con `NULLIF` para evitar división por cero.
- **Read rate:** `read outgoing / total outgoing`.
- **Delivered rate:** `delivered outgoing / total outgoing`.
- **Response rate:** incoming con una acción posterior válida / total incoming.
- **Unanswered rate:** incoming sin acción posterior válida / total incoming.
- **SLA promedio:** promedio de minutos únicamente sobre incoming respondidos.
- **SLA mediano:** percentil 50 de minutos de incoming respondidos.
- **SLA P95:** percentil 95 de minutos de incoming respondidos.

## Limitaciones

- Los timestamps no contienen timezone ni offset.
- La clasificación de mensajes usa reglas de keywords.
- `activity` cuenta como acción válida para SLA según la definición de la prueba.
- El extracto no contiene capacidad, turnos, agentes ni colas de operación.
- Los gráficos son descriptivos; no incorporan conclusiones causales.

## Detener Servicios

```bash
docker compose down
```

Para eliminar también los datos locales persistidos de PostgreSQL y Metabase:

```bash
docker compose down -v
```
