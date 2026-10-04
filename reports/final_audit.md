# Auditoría Integral Y Pre-Entrega

Fecha de auditoría: 2026-09-26  
Entorno de ejecución: Windows 11 / Python 3.10.11 / PostgreSQL 16-alpine (Docker) / Metabase v0.51.8 (Docker)

---

## 1. Estado General

# READY

El proyecto se encuentra en estado **READY** para entrega. La solución técnica, los datos procesados, las consultas SQL, las funciones de ventana, la configuración del dashboard en Metabase, la documentación técnica y las propuestas de negocio y FinOps se encuentran íntegramente validadas, consistentes y reconciliadas entre sí con cero discrepancias funcionales.

---

## 2. Hallazgos Críticos

No se detectaron fallos críticos de integridad de datos, lógica analítica, consultas SQL o disponibilidad del entorno.

El único punto de atención crítico a nivel de entrega es:
- **Exclusión obligatoria de `.env` en la entrega**: El archivo `.env` local contiene contraseñas de desarrollo para PostgreSQL y Metabase. Aunque está debidamente ignorado en `.gitignore`, si la entrega se realiza mediante un archivo comprimido manual (`.zip` o `.tar.gz`), `.env` no debe ser incluido. Solo debe entregarse `.env.example`.

---

## 3. Hallazgos Importantes

1. **Operación destructiva en script de validación local**:  
   El script [scripts/validate_sql_results.py](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/scripts/validate_sql_results.py#L70) ejecuta `DROP TABLE IF EXISTS messages_clean` antes de cargar el esquema y los datos mediante `COPY FROM STDIN`. Esto garantiza idempotencia y reproducibilidad en un entorno de pruebas controlado o contenedor efímero, pero debe advertirse explícitamente para evitar su ejecución accidental contra bases de datos productivas o compartidas.
2. **Cobertura parcial de análisis por plantilla (65,42%)**:  
   De los `2.507` mensajes salientes (`outgoing`), `1.640` poseen una plantilla identificada y `867` no tienen plantilla informada. Es fundamental que la tasa de fallo de plantillas (como el 100% de `lanzamiento_`) se interprete estrictamente sobre el subconjunto con plantilla y no sobre el total de mensajes salientes. El dashboard y la documentación abordan esto correctamente mediante tarjetas separadas de volumen absoluto y cobertura.
3. **Dependencia de contenedores Docker activos para validaciones de API**:  
   Los scripts de validación `validate_sql_results.py` y `validate_metabase_dashboard.py` requieren que los contenedores `prueba-tecnica-postgres` (puerto 5433) y `prueba-tecnica-metabase` (puerto 3000) se encuentren en estado *healthy* y en ejecución.

---

## 4. Observaciones Menores

1. **Registros con contenido vacío (3,23%)**:  
   Existen `119` registros en `messages_clean.csv` cuyo campo `content` está vacío o contiene solo espacios en blanco. La auditoría confirmó que corresponden a eventos operativos de sistema o notificaciones sin cuerpo de texto, por lo que no representan corrupción de datos y su presencia no altera el funnel ni el SLA.
2. **Estructura monolítica en script de perfilado**:  
   En [src/profile_dataset.py](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/src/profile_dataset.py), la función `build_profile` realiza todo el cálculo descriptivo en un solo bloque extenso (~170 líneas) y computa algunas columnas intermedias exploratorias (como `next_event_diff_minutes`) que no se consumen posteriormente. Funciona de manera óptima y precisa, pero modularizarla facilitaría el mantenimiento a largo plazo.
3. **Nombre de tabla en base de datos**:  
   El enunciado preliminar de la prueba aludía a `messages`, mientras que el pipeline normalizado utiliza `messages_clean`. Esta decisión de diseño está claramente documentada en `sql/schema.sql`, `sql/golden_results_validation.md` y `docs/dashboard.md`.
4. **Mapeo de puertos en Docker**:  
   PostgreSQL se mapea al puerto de host `5433` (en lugar del estándar `5432`) para evitar conflictos con instancias locales preexistentes en la máquina del evaluador.

---

## 5. Validaciones Ejecutadas

### 5.1 Suite de pruebas automatizadas (Pytest)
Comando real ejecutado:
```bash
python -m pytest -q
```
Resultado obtenido en consola:
```text
...........                                                              [100%]
11 passed in 22.13s
```
**Estado: PASSED (11/11 tests exitosos)**.

### 5.2 Calidad del proceso ETL (`reports/etl_quality_report.json`)
- Filas fuente (`prueba.txt`): `3.687`
- Filas procesadas: `3.687`
- Filas exportadas (`messages_clean.csv`): `3.687`
- Diferencia de filas (pérdida): `0` (`0,00%`)
- Columnas originales conservadas: `24 de 24`
- Columnas adicionales derivadas: `13`
- IDs duplicados: `0`
- IDs vacíos: `0`
- `conversation_id` vacíos: `0`
- Fechas `created_at` inválidas: `0`
- Fechas `updated_at` inválidas: `0`
- Tipos de mensaje inesperados: `0`
- Estados inesperados: `0`
- Atributos JSON válidos: `3.687 / 3.687` (`100,0%`)
- Resultado de validación (`is_valid`): `true`

### 5.3 Validación PostgreSQL en Docker (`reports/sql_validation_report.json`)
- Base de datos: PostgreSQL 16-alpine (puerto 5433).
- Carga de datos: `COPY FROM STDIN` exitoso con `3.687` filas.
- Clave primaria validada: `id` (sin duplicados, sin nulos).
- Funnel de entrega: `PASSED` (0 diferencias con Python).
- SLA de respuesta: `PASSED` (0 diferencias en conteos; diferencias decimales en minutos < 0.004 debidas exclusivamente a redondeo a 2 decimales).
- Curva horaria: `PASSED` (24 horas devueltas, suma exacta de 430 mensajes entrantes).
- Tiempos de ejecución con `EXPLAIN (ANALYZE, BUFFERS)`:
  - `01_delivery_funnel.sql`: ~3.67 ms.
  - `02_response_sla.sql`: ~12.45 ms.
  - `03_hourly_incoming.sql`: ~1.52 ms.

### 5.4 Validación Dashboard en Metabase API (`reports/metabase_dashboard_validation.json`)
- URL: `http://localhost:3000`
- Dashboard: `Supervisor operativo - Mensajeria` (ID 2).
- Tarjetas verificadas: `22 tarjetas`.
- Parámetros nativos comprobados: `start_date`, `end_date`, `status`, `message_type`.
- KPI Outgoing: `2.507` (esperado: 2507) -> `PASSED`.
- KPI Read: `708` (esperado: 708) -> `PASSED`.
- KPI Delivered: `83` (esperado: 83) -> `PASSED`.
- KPI Fallidos: `1.396` (esperado: 1396) -> `PASSED`.
- KPI Sin template: `867` (esperado: 867) -> `PASSED`.
- KPI Cobertura template: `65,42%` (esperado: 65.42%) -> `PASSED`.
- KPI Incoming: `430` (esperado: 430) -> `PASSED`.
- KPI Respondidos: `369` (esperado: 369) -> `PASSED`.
- KPI Sin respuesta: `61` (esperado: 61) -> `PASSED`.
- KPI SLA promedio: `127,24 min` -> `PASSED`.
- KPI SLA mediana: `0,68 min` -> `PASSED`.
- KPI SLA P95: `1.152,68 min` -> `PASSED`.
- Curva horaria: 24 horas devueltas, suma `430` -> `PASSED`.
- Filtro `status = failed`: devuelve exactamente `1.396` registros -> `PASSED`.
- Filtro `status = read`: devuelve exactamente `708` registros -> `PASSED`.
- Filtro de rango de fecha: modifica dinámicamente los totales -> `PASSED`.

---

## 6. Reconciliación Global (Golden Results)

| Métrica / Indicador | Python (ETL / Profiling) | PostgreSQL 16 (Docker) | Metabase Dashboard | Business Analysis | Diferencia | Estado |
|---|---:|---:|---:|---:|---:|:---:|
| **Total registros** | 3.687 | 3.687 | 3.687 | 3.687 | 0 | Consistente |
| **Total Outgoing** | 2.507 | 2.507 | 2.507 | 2.507 | 0 | Consistente |
| **Outgoing Failed** | 1.396 | 1.396 | 1.396 | 1.396 | 0 | Consistente |
| **Outgoing Read** | 708 | 708 | 708 | 708 | 0 | Consistente |
| **Outgoing Delivered** | 83 | 83 | 83 | 83 | 0 | Consistente |
| **Outgoing Sent** | 320 | 320 | 320 | 320 | 0 | Consistente |
| **Outgoing Sin Template** | 867 | 867 | 867 | 867 | 0 | Consistente |
| **Cobertura Template (%)** | 65,42% | 65,42% | 65,42% | 65,42% | 0,00% | Consistente |
| **Total Incoming** | 430 | 430 | 430 | 430 | 0 | Consistente |
| **Incoming Respondidos** | 369 | 369 | 369 | 369 | 0 | Consistente |
| **Incoming Sin Respuesta** | 61 | 61 | 61 | 61 | 0 | Consistente |
| **SLA Promedio (min)** | 127,24 | 127,24 | 127,24 | 127,24 | 0,00 | Consistente |
| **SLA Mediana (min)** | 0,68 | 0,68 | 0,68 | 0,68 | 0,00 | Consistente |
| **SLA P95 (min)** | 1.152,68 | 1.152,68 | 1.152,68 | 1.152,68 | 0,00 | Consistente |
| **SLA Máximo (min)** | 2.695,82 | 2.695,82 | N/A (en tabla SQL) | 2.695,82 | 0,00 | Consistente |
| **Horas Curva Demanda** | 24 | 24 | 24 | 24 | 0 | Consistente |
| **Suma Incoming Horario** | 430 | 430 | 430 | 430 | 0 | Consistente |

---

## 7. Auditoría Detallada Del SLA

### 7.1 Lógica SQL ([sql/02_response_sla.sql](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/sql/02_response_sla.sql))
La consulta resuelve el tiempo de respuesta mediante Common Table Expressions (CTEs) y funciones de ventana:
1. `incoming_events`: Filtra estrictamente `message_type = 'incoming'`.
2. `candidate_actions`: Realiza un autofiltro/join con `messages_clean a` sobre el mismo `conversation_id`, exigiendo:
   - `a.message_type IN ('activity', 'outgoing')`: Define qué eventos constituyen una acción operativa válida.
   - Condición temporal estricta: `(a.created_at > i.created_at) OR (a.created_at = i.created_at AND a.id > i.id)`. Esto resuelve orden cronológico y desempate determinista sin perder eventos con idéntico timestamp.
   - Función de ventana: `ROW_NUMBER() OVER (PARTITION BY i.id ORDER BY a.created_at, a.id) AS response_rank`. Clasifica las acciones candidatas por orden de ocurrencia.
3. `first_actions`: Filtra `response_rank = 1` para seleccionar exclusivamente la primera acción posterior inmediata.
4. `response_detail`: Aplica `LEFT JOIN` desde `incoming_events` hacia `first_actions`. De este modo, los mensajes entrantes sin respuesta posterior se conservan con `response_id = NULL` y `response_minutes = NULL`.
5. Cálculo de métricas: Se calcula `EXTRACT(EPOCH FROM (fa.response_at - i.created_at)) / 60.0`. Las funciones de agregación (`AVG`, `PERCENTILE_CONT`, `MIN`, `MAX`) omiten de manera natural los valores `NULL`, calculando las estadísticas solo sobre los casos respondidos.

### 7.2 Por qué no utilizar `LEAD()`
La función de ventana `LEAD()` solo inspecciona la fila inmediatamente contigua. En secuencias habituales como `incoming -> incoming -> outgoing`, un `LEAD()` sobre el primer incoming apuntaría al segundo incoming (que no es una respuesta), clasificándolo erróneamente como no respondido. La solución implementada de join condicional con `ROW_NUMBER()` garantiza ubicar la primera acción válida sin importar cuántos mensajes incoming consecutivos envíe el usuario.

### 7.3 Casos de borde validados empíricamente
- **`incoming -> activity`**: Conversación `3.620` (incoming `49.097` seguido de activity `53.335`, response time = 1.947,65 min).
- **`incoming -> outgoing`**: Conversación `9.415` (incoming `51.449` seguido de outgoing `54.644`, response time = 2.695,82 min).
- **`incoming -> incoming -> outgoing`**: Conversación `6.972` (incoming `51.487` seguido de incoming `51.489` y luego outgoing `54.651`; el segundo incoming es ignorado como respuesta y el cálculo se efectúa hacia el outgoing en 2.684,18 min).
- **`incoming sin respuesta`**: Conversación `4.668` (incoming `50.070` sin acción posterior; `response_at` y minutos quedan en `NULL`).
- **`timestamps idénticos`**: Conversación `1.341` (timestamp `2023-07-30 16:24:41`; el orden se resuelve determinísticamente mediante `id` `50.122` < `50.123`).

---

## 8. Auditoría Del Dashboard Y Filtros

### 8.1 Arquitectura de tarjetas (22 Cards)
El dashboard se estructura en tres bloques operativos limpios:
1. **Bloque Campaña (11 tarjetas)**: Total outgoing, read, delivered, fallidos, tasa de fallo, distribución por estado, errores externos en tabla, volumen de fallos por plantilla, tasa de fallo por plantilla, outgoing sin plantilla (`867`) y cobertura de plantilla (`65,42%`).
2. **Bloque SLA (8 tarjetas)**: Incoming totales, respondidos, sin respuesta, tasa de respuesta (`85,81%`), SLA promedio, SLA mediana, SLA P95 y detalle de respuesta por categoría de mensaje.
3. **Bloque Demanda Horaria (3 tarjetas)**: Demanda horaria (24 horas continuas), demanda vs sin respuesta por hora, y distribución de incoming por categoría NLP.

### 8.2 Auditoría de filtros nativos
El requerimiento solicita:
> "al menos dos variables (Filtros SQL) para que el supervisor pueda filtrar la data por fecha y por estado sin modificar el código."

- Se implementaron 4 variables nativas mediante template tags de Metabase:
  - `{{start_date}}` y `{{end_date}}`: Filtros de tipo fecha.
  - `{{status}}`: Filtro categórico de estado (`sent`, `delivered`, `read`, `failed`).
  - `{{message_type}}`: Filtro categórico de tipo de mensaje.
- El supervisor interactúa mediante selectores visuales en la cabecera del dashboard sin tocar una sola línea de SQL.
- **Impacto en SLA**: Los filtros temporales y de estado en la consulta del SLA se aplican sobre la subconsulta de eventos incoming analizados (`WHERE ($1 IS NULL OR i.created_at >= $1) ...`), preservando la búsqueda de acciones posteriores en toda la historia de la conversación. Esto evita que una respuesta ocurrida un día después sea omitida artificialmente por un corte de fecha.
- **Validación automatizada por API**:
  - Filtro `status = failed` ejecutado vía API: devuelve `1.396` en 45,96 ms.
  - Filtro `status = read` ejecutado vía API: devuelve `708` en 55,30 ms.
  - Filtro de fecha ejecutado vía API: altera coherentemente los totales a nivel de día.

---

## 9. Auditoría De Negocio Y NLP

### 9.1 Rigor analítico en [reports/business_analysis.md](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/reports/business_analysis.md)
El informe cumple con los más altos estándares de consultoría analítica al separar taxativamente:
- **HECHO**: Cifras exactas comprobables.
- **INTERPRETACIÓN**: Significado operativo del dato.
- **HIPÓTESIS**: Posibles causas técnicas o de negocio que requieren validación empírica.
- **ACCIÓN A VALIDAR**: Recomendaciones concretas con métricas de seguimiento pre y post intervención.

Cifras clave auditadas:
- `55,68%` de mensajes salientes fallan (`1.396 / 2.507`).
- `98,42%` de los fallos corresponden al error `#132000` (desajuste en número de parámetros esperados).
- `1.352` fallos concentrados en la plantilla `lanzamiento_` (100% de tasa de fallo en esa plantilla).
- `85,81%` de tasa de respuesta sobre mensajes de clientes (`369 / 430`).
- `14,19%` de abandono o falta de respuesta (`61 / 430`).
- `27` casos sin respuesta concentrados en la hora `16:00` (44,26% de todos los casos no atendidos).
- `34,42%` de la demanda horaria entrante se concentra entre las `15:00` y las `16:00` (`148` mensajes).

### 9.2 Clasificación NLP de incoming
- Reglas aplicadas en [src/etl/transformer.py](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/src/etl/transformer.py#L78):
  - Normalización de acentos y minúsculas.
  - Precedencia estricta: `Queja` -> `Soporte` -> `Pedido` -> `Otros`.
- Distribución observada:
  - `Otros`: 375 (`87,21%`)
  - `Soporte`: 22 (`5,12%`)
  - `Pedido`: 21 (`4,88%`)
  - `Queja`: 12 (`2,79%`)
- **Interpretación crítica**: El informe documenta explícitamente que la concentración del `87,21%` en `Otros` se debe a la naturaleza conservadora y limitada de las reglas de expresiones regulares ante mensajes breves o no estructurados, y **no** debe presentarse como un rasgo de comportamiento del cliente.

---

## 10. Auditoría De Seguridad

1. **Gestión de variables de entorno**:
   - `.env` contiene credenciales locales (`etl_user`, `etl_local_password`, `supervisor@example.local`).
   - `.gitignore` incluye `.env`, `__pycache__/`, `.pytest_cache/` y `*.pyc`.
   - `.env.example` proporciona una plantilla segura con valores de desarrollo para que el evaluador pueda inicializar el proyecto sin fricción.
2. **Secretos e información sensible**:
   - No existen tokens reales de Meta Cloud API, WhatsApp Business API ni llaves privadas en ningún archivo del workspace.
   - Los scripts Python no tienen passwords de producción embebidos; leen del entorno y solo poseen fallbacks hacia las credenciales locales de prueba.
3. **Exposición de servicios**:
   - PostgreSQL expone el puerto `5433` y Metabase el `3000`, ambos vinculados a localhost.

---

## 11. Auditoría De Reproducibilidad

El proyecto es 100% reproducible en un entorno limpio siguiendo estos pasos:

1. **Clonar / descomprimir el proyecto**:
   ```bash
   cd "Prueba tecnica"
   ```
2. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configurar variables**:
   ```bash
   copy .env.example .env
   ```
4. **Ejecutar ETL y validación de calidad**:
   ```bash
   python src/run_etl.py
   ```
5. **Ejecutar suite de tests**:
   ```bash
   python -m pytest -q
   ```
6. **Ejecutar perfilado estadístico**:
   ```bash
   python src/profile_dataset.py
   ```
7. **Levantar base de datos y Metabase en Docker**:
   ```bash
   docker compose up -d --wait
   ```
8. **Cargar esquema, importar CSV y validar SQL**:
   ```bash
   python scripts/validate_sql_results.py
   ```
9. **Desplegar dashboard y preguntas en Metabase**:
   ```bash
   python scripts/setup_metabase.py
   ```
10. **Ejecutar validación de dashboard vía API**:
    ```bash
    python scripts/validate_metabase_dashboard.py
    ```
11. **Acceso al Dashboard**:
    Navegar a `http://localhost:3000` con `supervisor@example.local` / `Mbase_Local_2026_Dashboard!`.

---

## 12. Auditoría FinOps Y Escalabilidad

La propuesta documentada en [docs/scalability_finops.md](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/docs/scalability_finops.md) aborda el escenario solicitado de **50 supervisores consultando cada 5 minutos**:

$$\text{Carga nominal} = 50 \text{ usuarios} \times 12 \text{ actualizaciones/hora} = 600 \text{ consultas concurrentes/hora}$$

### Estrategia de bajo costo (Cero sobrecoste Cloud):
1. **Cache de resultados en Metabase (TTL = 5 minutos)**:
   Al fijar el TTL de cache en 300 segundos, los 50 usuarios consultando simultáneamente el dashboard leen el resultado cacheado en memoria. La base de datos solo ejecuta las consultas pesadas de SLA **12 veces por hora** en lugar de 600 veces, logrando una **reducción del 98% en la carga de cómputo del motor relacional**.
2. **Vistas Materializadas en PostgreSQL**:
   - `mv_response_sla`: Precalcula el primer evento posterior y los minutos de SLA por conversación.
   - Refresco programado vía `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_response_sla` cada 5 minutos mediante una tarea programada (cron / pg_cron).
   - Las consultas del dashboard consultan la vista precalculada con costo de lectura secuencial mínima indexada.
3. **Connection Pooling**:
   Configuración de límite de conexiones en PostgreSQL (máximo 15 conexiones activas en pool) para evitar overhead por conmutación de contexto.
4. **Indexación quirúrgica**:
   Uso exclusivo de los 3 índices ya validados en [sql/schema.sql](file:///c:/Users/santi/OneDrive/Escritorio/Prueba%20tecnica/sql/schema.sql#L49-L54):
   - `(conversation_id, created_at, id)`
   - `(message_type, status)`
   - `(created_at)`

---

## 13. Lista Priorizada De Correcciones Pre-Entrega

### CRÍTICO
- **Verificar exclusión de `.env` al comprimir el repositorio**: Asegurarse de que el archivo comprimido final contenga únicamente `.env.example`.

### IMPORTANTE
- **Incluir advertencia en `validate_sql_results.py`**: Añadir un comentario visible indicando que la instrucción `DROP TABLE IF EXISTS` está destinada exclusivamente a pruebas locales automatizadas.
- **Mantener destacada la cobertura de plantillas**: Asegurar que en la sustentación oral / video de 5 minutos se mencione que el 100% de fallo de `lanzamiento_` se circunscribe a los mensajes con plantilla informada (cobertura del 65,42%).

### MENOR
- **Limpieza de variables auxiliares en perfilado**: En futuras iteraciones, retirar las columnas intermedias `next_event_diff_minutes` en `src/profile_dataset.py` para aligerar la memoria en datasets de millones de filas.

---

## Conclusión

El proyecto cumple con la totalidad de los requisitos técnicos, de calidad de datos, algorítmicos, visuales, analíticos y de negocio exigidos. Todos los resultados son matemáticamente reproducibles y verificables de extremo a extremo. El proyecto se declara **READY** para su entrega final.
