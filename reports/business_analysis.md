# Visión De Negocio Y Diagnóstico Operativo

## Alcance Y Fuentes

Este análisis utiliza únicamente datos ya validados:

- `data/processed/messages_clean.csv`
- `reports/pre_sql_analysis.json`
- `reports/sql_validation_report.json`
- Tablas auxiliares de `reports/`

No se modificaron el ETL, el esquema ni las consultas SQL. Las afirmaciones se separan entre **dato observado**, **interpretación**, **hipótesis** y **acción a validar**. No se infiere causalidad a partir de asociaciones descriptivas.

## Resumen Del Dataset

- Registros: `3.687`
- IDs únicos: `3.687`
- Conversaciones: `2.153`
- Periodo de `created_at`: `2023-07-25 00:39:08` a `2023-08-02 14:20:12`
- Incoming: `430`
- Outgoing: `2.507`
- Activity: `750`
- Timestamps sin zona horaria ni offset.

## A. Hallazgos De Campaña

### Distribución de outgoing

Denominador: `2.507` mensajes con `message_type = outgoing`. Los estados no se interpretan como acumulativos.

| Status | Count | Percentage |
|---|---:|---:|
| failed | 1.396 | 55,68% |
| read | 708 | 28,24% |
| sent | 320 | 12,76% |
| delivered | 83 | 3,31% |

**Dato observado:** `failed` es el estado individual más frecuente y representa más de la mitad de los outgoing.

**Interpretación:** la entrega efectiva no puede resumirse solamente con read/delivered; existen `320` outgoing en `sent` que deben permanecer visibles.

**Nivel de confianza:** alto para los conteos; descriptivo, no causal.

## B. Hallazgos De Entrega

### External errors

Denominador de porcentajes: `1.396` registros con `external_error`.

| External error | Count | Percentage of failed |
|---|---:|---:|
| `(#132000) Number of parameters does not match the expected number of params` | 1.374 | 98,42% |
| `131049: This message was not delivered to maintain healthy ecosystem engagement.` | 8 | 0,57% |
| `131026: Message undeliverable` | 8 | 0,57% |
| `130472: User's number is part of an experiment` | 5 | 0,36% |
| `Template not found or invalid template name` | 1 | 0,07% |

Todos los registros con `external_error` observados tienen `status = failed` y `message_type = outgoing`.

**Dato observado:** un único mensaje de error concentra `1.374` de los `1.396` fallos.

**Interpretación:** el volumen de fallos está altamente concentrado en un tipo de error de parámetros. Esto permite priorizar una revisión técnica específica.

**Hipótesis:** podría existir una incompatibilidad entre parámetros enviados y definición de una o más plantillas. El dataset no demuestra por sí solo dónde se origina el problema.

**Acción a validar:** revisar la construcción y validación de parámetros antes del envío, y medir nuevamente el porcentaje de `#132000` después de cualquier intervención.

### Cruce error × template

| External error | Template | Count |
|---|---|---:|
| `#132000` | `lanzamiento_` | 1.352 |
| `#132000` | `lanzamiento__inactivas` | 22 |
| `131026` | `ampliaciones_zafiro` | 6 |
| `131049` | `ampliaciones_zafiro` | 5 |
| `130472` | `lanzamiento__activas_v2` | 3 |
| `131049` | `lanzamiento__activas_v2` | 3 |
| `131026` | `lanzamiento__activas_v2` | 2 |
| `130472` | `saludo` | 2 |
| `Template not found or invalid template name` | sin template identificado | 1 |

**Dato observado:** `#132000` se concentra en `lanzamiento_` y `lanzamiento__inactivas`. El cruce muestra asociación de volumen, no causalidad.

## C. Hallazgos Sobre Templates

Hay `7` templates identificados.

| Template | Total | Failed | Failed % | Read | Delivered |
|---|---:|---:|---:|---:|---:|
| `lanzamiento_` | 1.352 | 1.352 | 100,00% | 0 | 0 |
| `lanzamiento__activas_v2` | 182 | 8 | 4,40% | 156 | 18 |
| `ampliaciones_zafiro` | 54 | 11 | 20,37% | 27 | 12 |
| `saludo` | 24 | 2 | 8,33% | 17 | 3 |
| `lanzamiento__inactivas` | 22 | 22 | 100,00% | 0 | 0 |
| `rechazos_zafiro` | 4 | 0 | 0,00% | 4 | 0 |
| `bienvenida` | 2 | 0 | 0,00% | 2 | 0 |

**Dato observado:** los templates `lanzamiento_` y `lanzamiento__inactivas` tienen todos sus registros en `failed`; además, `lanzamiento_` concentra `1.352` registros.

**Interpretación:** estos templates explican una parte dominante del volumen fallido observado.

**Limitación:** los templates con pocos registros no permiten conclusiones estables; por ejemplo, `bienvenida` tiene solo `2` observaciones.

## D. Demanda De Clientes

Denominador: `430` mensajes `incoming`.

| Categoría | Count | Percentage |
|---|---:|---:|
| Otros | 375 | 87,21% |
| Soporte | 22 | 5,12% |
| Pedido | 21 | 4,88% |
| Queja | 12 | 2,79% |

**Dato observado:** `Otros` concentra la mayoría de mensajes.

**Interpretación:** la clasificación actual identifica con claridad una fracción reducida; el volumen de `Otros` limita el detalle temático.

### Ejemplos reales anonimizados

- **Soporte:** “Necesito ayuda”; “tengo algunas inquietudes para consultar”.
- **Queja:** “En una factura me cobraron algo que no llegó”; “Estoy inconforme con un premio que pedí”.
- **Pedido:** “Quería saber si puedo pasar pedido”; “Catálogos”.

Las reglas parecen razonables para solicitudes explícitas de ayuda, inconformidad y pedido. Sin embargo, mensajes cortos como “Catálogos” pueden ser informativos sin implicar necesariamente una intención de compra, y `Otros` puede contener solicitudes que las keywords no distinguen.

**Posibles falsos positivos:** palabras como `pedido` pueden aparecer en una consulta informativa y llevarla a `Pedido`.

**Posibles falsos negativos:** mensajes breves, con errores ortográficos o lenguaje indirecto pueden quedar en `Otros` aunque requieran soporte, queja o pedido.

**Acción a validar:** revisar manualmente una muestra de `Otros`, registrar una etiqueta de referencia y medir precisión por categoría antes de ampliar reglas.

## E. SLA Y RESPUESTA

- Incoming total: `430`
- Incoming con respuesta: `369`
- Incoming sin respuesta: `61`
- Response rate: `85,81%` (`369 / 430`)
- No-response rate: `14,19%` (`61 / 430`)

| Métrica | Minutos |
|---|---:|
| Promedio | 127,24 |
| Mediana | 0,68 |
| P95 | 1.152,68 |
| Máximo | 2.695,82 |

La definición utilizada busca la primera acción posterior `activity` u `outgoing` dentro de la misma conversación. Los incoming sin acción posterior conservan ausencia de respuesta.

**Interpretación:** el promedio es mucho mayor que la mediana. Esto indica una distribución con cola derecha: muchas respuestas son muy rápidas, pero algunos tiempos extremadamente altos elevan el promedio.

**Dato observado:** el P95 equivale aproximadamente a `19,21` horas y el máximo a `44,93` horas.

No debe utilizarse únicamente el promedio para representar la experiencia típica; mediana y P95 aportan información complementaria.

## F. Outliers De SLA

| Conversation | Incoming | Response | Minutes | Type | Category |
|---|---|---|---:|---|---|
| `9.415` | `2023-07-30 22:31:12` | `2023-08-01 19:27:01` | 2.695,82 | outgoing | Otros |
| `6.972` | `2023-07-30 22:44:38` | `2023-08-01 19:28:49` | 2.684,18 | outgoing | Otros |
| `6.972` | `2023-07-30 22:45:05` | `2023-08-01 19:28:49` | 2.683,73 | outgoing | Soporte |
| `3.620` | `2023-07-30 15:13:39` | `2023-07-31 23:41:18` | 1.947,65 | activity | Otros |
| `8.435` | `2023-07-30 15:50:18` | `2023-07-31 23:54:16` | 1.923,97 | activity | Otros |

**Dato observado:** varios outliers abarcan más de un día calendario.

**Interpretación:** pueden corresponder a conversaciones prolongadas o a una acción operativa tardía. También requieren revisar si el sistema registra actividades con una semántica distinta de respuesta directa.

**No demostrado:** el dataset no permite determinar si estos tiempos representan falta de operación, una conversación reactivada o un problema temporal. No se afirma una causa.

## G. Mensajes Sin Respuesta

### Por categoría

Denominador: `61` incoming sin respuesta.

| Categoría | Unanswered | Percentage of unanswered |
|---|---:|---:|
| Otros | 53 | 86,89% |
| Soporte | 4 | 6,56% |
| Pedido | 3 | 4,92% |
| Queja | 1 | 1,64% |

Tasas descriptivas dentro de cada categoría:

- Otros: `53 / 375 = 14,13%` sin respuesta.
- Soporte: `4 / 22 = 18,18%`.
- Pedido: `3 / 21 = 14,29%`.
- Queja: `1 / 12 = 8,33%`.

Las categorías pequeñas deben interpretarse con cautela.

### Por hora

Los `61` casos sin respuesta se distribuyen así:

| Hora | Unanswered |
|---:|---:|
| 13 | 2 |
| 14 | 2 |
| 15 | 11 |
| 16 | 27 |
| 18 | 6 |
| 20 | 6 |
| 22 | 3 |
| 23 | 4 |

**Dato observado:** la hora `16` concentra `27` de los `61` casos sin respuesta (`44,26%`).

**Hipótesis:** puede existir una concentración temporal de demanda no atendida o una particularidad del registro operativo en esa franja. No hay información de capacidad, turnos ni asignación para demostrarlo.

## H. Curva Horaria

Denominador: `430` incoming.

| Hora | Incoming | Percentage |
|---:|---:|---:|
| 0 | 1 | 0,23% |
| 12 | 13 | 3,02% |
| 13 | 21 | 4,88% |
| 14 | 21 | 4,88% |
| 15 | 83 | 19,30% |
| 16 | 65 | 15,12% |
| 17 | 27 | 6,28% |
| 18 | 21 | 4,88% |
| 19 | 62 | 14,42% |
| 20 | 25 | 5,81% |
| 21 | 30 | 6,98% |
| 22 | 30 | 6,98% |
| 23 | 31 | 7,21% |

No se observaron incoming entre las horas `01` y `11`.

**Dato observado:** el máximo volumen ocurre a las `15:00` (`83`), seguido por `16:00` (`65`) y `19:00` (`62`). Las horas `15:00-16:00` concentran `148` incoming (`34,42%`).

**Interpretación:** esta distribución puede utilizarse como input para dimensionamiento de turnos.

**Limitación:** no permite afirmar por sí sola una necesidad exacta de staffing ni una causa de los picos.

## I. Cruces Operativos

### Categoría × respuesta

| Categoría | Con respuesta | Sin respuesta | Total | Response rate |
|---|---:|---:|---:|---:|
| Otros | 322 | 53 | 375 | 85,87% |
| Soporte | 18 | 4 | 22 | 81,82% |
| Pedido | 18 | 3 | 21 | 85,71% |
| Queja | 11 | 1 | 12 | 91,67% |

El grupo `Queja` tiene solo `12` casos, por lo que su tasa no debe extrapolarse.

### Template × delivery status

El cruce completo está disponible en [reports/template_status.csv](template_status.csv). Los patrones principales son:

- `lanzamiento_`: `1.352 failed` de `1.352`.
- `lanzamiento__inactivas`: `22 failed` de `22`.
- `lanzamiento__activas_v2`: `156 read`, `18 delivered`, `8 failed`.
- `ampliaciones_zafiro`: `27 read`, `12 delivered`, `11 failed`.

Estos patrones identifican concentraciones de incidencia, no prueban que el template sea la causa.

### Error × template

El cruce completo está disponible en [reports/external_errors.csv](external_errors.csv). La concentración principal es `#132000` con `lanzamiento_` (`1.352`) y `lanzamiento__inactivas` (`22`).

## J. Diagnóstico Estructurado

### A. Campaña

- **Evidencia:** `1.396 / 2.507` outgoing están en `failed` (`55,68%`).
- **Interpretación:** existe una incidencia de entrega de alto volumen en el extracto.
- **Hipótesis:** la concentración de errores de parámetros puede estar asociada a determinados envíos de plantillas.
- **Confianza:** alta en el dato; baja en la causa.

### B. Entrega

- **Evidencia:** `#132000` representa `98,42%` de los registros con error.
- **Interpretación:** la revisión técnica puede priorizar parámetros y plantillas asociadas.
- **Hipótesis:** podrían existir valores faltantes, extras o incompatibles en los parámetros.
- **Confianza:** alta en la concentración; no causal.

### C. Demanda

- **Evidencia:** `375 / 430` incoming están en `Otros`.
- **Interpretación:** el detalle temático actual es limitado.
- **Hipótesis:** las keywords no capturan completamente la variedad del lenguaje de clientes.
- **Confianza:** alta en la distribución; media en la explicación.

### D. SLA

- **Evidencia:** response rate `85,81%`, mediana `0,68` minutos, promedio `127,24`, P95 `1.152,68`.
- **Interpretación:** hay respuestas rápidas para una parte importante y una cola extensa de tiempos altos.
- **Hipótesis:** los outliers pueden mezclar conversaciones prolongadas y acciones tardías.
- **Confianza:** alta en las métricas; baja sobre las causas.

### E. Operación

- **Evidencia:** `27` no respondidos ocurrieron a las `16:00`; `179` conversaciones estaban fuera de orden en el archivo original.
- **Interpretación:** la lectura operativa requiere ordenamiento temporal y análisis por franja horaria.
- **Hipótesis:** la concentración de no respuesta podría relacionarse con cobertura operativa, aunque no hay capacidad de agentes para probarlo.
- **Confianza:** alta en el dato; baja en la causa.

### F. Limitaciones

- Timestamps sin timezone.
- Clasificación NLP basada en keywords.
- Dataset extracto, no necesariamente representativo de toda la operación.
- Sin información de agentes, turnos, capacidad, colas o reglas de asignación.
- No se puede inferir causalidad de los cruces.
- El significado exacto de `status` depende del sistema origen.
- `activity` se considera acción válida para SLA por definición de la prueba, pero no necesariamente equivale a una respuesta textual al cliente.

## K. Acciones Inmediatas A Validar

### Acción 1 — Sistema/campaña

- **Problema observado:** `1.374` fallos corresponden a `#132000`.
- **Evidencia:** `98,42%` de los errores; `lanzamiento_` concentra `1.352` de ellos.
- **Intervención:** revisar el contrato de parámetros de las plantillas afectadas y añadir validación previa al envío.
- **Métrica:** `#132000 / total outgoing` y `failed rate` por template antes y después.
- **Nota:** la intervención debe probarse; no se afirma que resolverá todos los fallos.

### Acción 2 — Operación

- **Problema observado:** `61` incoming no encuentran una actividad u outgoing posterior.
- **Evidencia:** `14,19%` de no respuesta; `27` casos a las `16:00`.
- **Intervención:** revisar la cola de casos sin respuesta por franja y categoría.
- **Métrica:** `unanswered rate`, response rate y P95 por hora/categoría.

### Acción 3 — Workforce

- **Problema observado:** el volumen máximo se concentra entre `15:00` y `16:00`.
- **Evidencia:** `148` incoming, `34,42%` del total, en esas dos horas.
- **Intervención:** utilizar la curva horaria como input para revisar cobertura de turnos.
- **Métrica:** response rate y mediana/P95 durante esas franjas, antes y después.
- **Nota:** no implica automáticamente aumentar personal.

### Acción 4 — Calidad de clasificación

- **Problema observado:** `87,21%` de incoming queda en `Otros`.
- **Evidencia:** `375` de `430` mensajes.
- **Intervención:** etiquetar manualmente una muestra y medir precisión/recall de las reglas antes de modificarlas.
- **Métrica:** porcentaje de `Otros`, precisión por categoría y tasa de revisión manual.

## L. KPIs Recomendados

| KPI | Definición | Denominador |
|---|---|---|
| Delivery failure rate | Outgoing en `failed` | Total outgoing |
| Read rate | Outgoing en `read` | Total outgoing |
| Delivered rate | Outgoing en `delivered` | Total outgoing |
| Response rate | Incoming con primera acción `activity/outgoing` | Total incoming |
| Unanswered rate | Incoming sin acción válida posterior | Total incoming |
| Average response time | Promedio de minutos de incoming respondidos | Incoming con respuesta |
| Median response time | Mediana de minutos de incoming respondidos | Incoming con respuesta |
| P95 response time | Percentil 95 de minutos de incoming respondidos | Incoming con respuesta |
| Incoming volume | Cantidad de incoming | Periodo/filtros seleccionados |
| Error volume | Registros con `external_error` | Total registros o total failed, siempre documentado |
| Top external errors | Frecuencia por mensaje de error | Total registros con error |
| Incoming by category | Cantidad de incoming por `message_category` | Total incoming |

## Conclusión

El extracto muestra una incidencia de entrega concentrada en errores de parámetros, una distribución temática de clientes todavía poco discriminante y un SLA con mediana rápida pero cola extrema. Los datos justifican priorizar la revisión de plantillas/parámetros, el seguimiento de no respuestas en la franja de las `16:00` y una evaluación controlada de la clasificación NLP. Estas son intervenciones a validar con métricas posteriores, no conclusiones causales definitivas.
