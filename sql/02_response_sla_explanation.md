# Lógica Del SLA

## Definición

Para cada mensaje `incoming`, se busca la primera acción posterior del mismo `conversation_id` cuyo `message_type` sea `activity` u `outgoing`. El intervalo se calcula en minutos. Si no existe una acción válida, `response_at` y `response_minutes` permanecen `NULL`.

## Orden determinista

La secuencia lógica usa `ORDER BY created_at, id`. Cuando dos eventos comparten timestamp, el `id` define el desempate sin modificar el timestamp original.

## Pasos SQL

1. Seleccionar los `incoming`.
2. Cruzarlos con eventos de la misma conversación.
3. Conservar solo acciones `activity` u `outgoing` posteriores:
   - `action.created_at > incoming.created_at`, o
   - timestamps iguales y `action.id > incoming.id`.
4. Aplicar `ROW_NUMBER() OVER (PARTITION BY incoming_id ORDER BY created_at, id)`.
5. Conservar `response_rank = 1`.
6. Hacer `LEFT JOIN` contra todos los incoming, preservando los que no tienen respuesta.
7. Calcular la diferencia mediante `EXTRACT(EPOCH) / 60.0`.
8. Calcular promedio y percentiles sobre `response_minutes`; los `NULL` quedan fuera de esas estadísticas.

## Por qué no basta con LEAD()

`LEAD(message_type)` solo encuentra el registro inmediatamente siguiente. En una secuencia `incoming -> incoming -> activity`, el primer incoming tendría como siguiente evento otro incoming, aunque sí existe una acción válida después. La estrategia de candidatos más `ROW_NUMBER()` busca la primera acción válida, no solo el siguiente registro.

## Filtros

Los eventos se ordenan y se buscan sobre el conjunto completo. El filtro de fecha se aplica después a los incoming que se quieren medir. Esto evita perder una respuesta válida ubicada después del límite temporal. El filtro de status también se aplica al conjunto de incoming analizados, no a las acciones, para no alterar la definición de respuesta.

## Casos límite

- Un incoming aislado: sin respuesta, `NULL`.
- Incoming seguido de incoming: el primero continúa buscando una acción válida posterior.
- Activity u outgoing inmediato: respuesta válida.
- Varios eventos válidos: se toma el primero por `created_at, id`.
- Timestamp igual: solo un `id` posterior cuenta como evento posterior.
- `created_at` nulo: no puede establecerse orden temporal ni respuesta válida.
- `conversation_id` nulo: no se mezcla con otras conversaciones y no encuentra acciones por igualdad.
