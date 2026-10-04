-- Esquema PostgreSQL para messages_clean.csv.
-- Los identificadores se mantienen como text para preservar exactamente el valor de origen.

CREATE TABLE IF NOT EXISTS messages_clean (
    id text PRIMARY KEY,
    content text,
    account_id text,
    inbox_id text,
    conversation_id text,
    message_type text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    private boolean,
    status text,
    source_id text,
    content_type text,
    content_attributes text,
    sender_type text,
    sender_id text,
    additional_attributes text,
    processed_message_content text,
    sentiment text,
    contact_id text,
    sistema_lead_id text,
    conversation_display_id text,
    id_sistema text,
    id_db_externa text,
    id_leads_db_externa text,
    external_error text,
    template_name text,
    sistema_call_source text,
    sistema_management_answers text,
    in_reply_to text,
    in_reply_to_external_id text,
    content_json_status text,
    additional_json_status text,
    event_category text,
    message_category text,
    date date,
    hour integer,
    day_of_week text
);

-- Carga exacta del CSV; COPY no transforma los valores.
-- Ejecutar desde psql después de crear la tabla:
-- \copy messages_clean FROM 'data/processed/messages_clean.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

-- Índices justificados por las consultas de esta etapa:
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_id
    ON messages_clean (conversation_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_type_status
    ON messages_clean (message_type, status);
CREATE INDEX IF NOT EXISTS idx_messages_created_at
    ON messages_clean (created_at);
