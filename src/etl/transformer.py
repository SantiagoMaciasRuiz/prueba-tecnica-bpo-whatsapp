from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List

import pandas as pd


def parse_json_safe(value: Any) -> tuple[Dict[str, Any], str]:
    """Parse a JSON object and return its payload plus valid/empty/invalid status."""
    if value is None or value == '':
        return {}, 'empty'
    if isinstance(value, dict):
        return value, 'valid'
    text = str(value).strip()
    if not text:
        return {}, 'empty'
    try:
        data = json.loads(text)
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, dict):
            return data, 'valid'
        return {}, 'invalid'
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, 'invalid'


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_template_name(additional_attributes: Dict[str, Any]) -> str:
    payload = additional_attributes.get('template_params', {})
    if isinstance(payload, dict):
        template_name = payload.get('name')
        if template_name:
            return str(template_name)
    return ""


def _derive_event_category(message_type: str, status: str, external_error: str) -> str:
    mt = (message_type or '').strip().lower()
    st = (status or '').strip().lower()

    if mt == 'activity':
        return 'system_activity'
    if mt == 'incoming':
        return 'user_message'
    if mt == 'outgoing' and (st == 'failed' or external_error):
        return 'delivery_error'
    if mt == 'outgoing':
        return 'bot_message'
    return 'unknown'


def _normalize_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}


def _normalize_text_for_rules(message: Any) -> str:
    text = str(message or '').lower()
    text = ''.join(
        char for char in unicodedata.normalize('NFD', text)
        if unicodedata.category(char) != 'Mn'
    )
    return re.sub(r'\s+', ' ', text).strip()


def classify_incoming_message(message: str) -> str:
    """Classify incoming messages conservatively into the required categories."""
    text = _normalize_text_for_rules(message)
    if not text:
        return 'Otros'
    if re.search(r'no (me )?(llego|llegaron)|no sum|cobro|cobrado|rechaz|inconforme|problema|fall[oa]|queja|error|faltante|no aparece', text):
        return 'Queja'
    if re.search(r'ayuda|asesor|servicio al cliente|inquietud|consulta|informacion|como puedo', text):
        return 'Soporte'
    if re.search(r'catalogo|pasar pedido|hacer (un )?pedido|montar pedido|ingresar.*pedido|pedido.*(si|no|cuando)|comprar', text):
        return 'Pedido'
    return 'Otros'


def normalize_messages(raw_rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Convert raw rows into a clean, validated dataframe for downstream analysis."""
    rows = list(raw_rows)
    if not rows:
        return pd.DataFrame()

    records: List[Dict[str, Any]] = []
    for row in rows:
        content_attributes, content_json_status = parse_json_safe(row.get('content_attributes'))
        additional_attributes, additional_json_status = parse_json_safe(row.get('additional_attributes'))

        content = _normalize_text(row.get('content'))
        message_type = _normalize_text(row.get('message_type'))
        status = _normalize_text(row.get('status'))

        created_at = pd.to_datetime(row.get('created_at', ''), errors='coerce')
        updated_at = pd.to_datetime(row.get('updated_at', ''), errors='coerce')
        record = dict(row)
        record.update({
            'message_type': message_type,
            'created_at': created_at,
            'updated_at': updated_at,
            'private': _normalize_boolean(row.get('private')),
            'status': status,
            'content': content,
            'content_attributes': content_attributes,
            'additional_attributes': additional_attributes,
            'external_error': content_attributes.get('external_error', ''),
            'template_name': _extract_template_name(additional_attributes),
            'sistema_call_source': content_attributes.get('sistema_call_source', ''),
            'sistema_management_answers': content_attributes.get('sistema_management_answers', []),
            'in_reply_to': content_attributes.get('in_reply_to', ''),
            'in_reply_to_external_id': content_attributes.get('in_reply_to_external_id', ''),
            'content_json_status': content_json_status,
            'additional_json_status': additional_json_status,
            'event_category': _derive_event_category(
                message_type,
                status,
                str(content_attributes.get('external_error', '')),
            ),
            'message_category': classify_incoming_message(content) if message_type.lower() == 'incoming' else '',
            'date': created_at.date().isoformat() if not pd.isna(created_at) else '',
            'hour': int(created_at.hour) if not pd.isna(created_at) else pd.NA,
            'day_of_week': created_at.day_name() if not pd.isna(created_at) else '',
        })
        records.append(record)

    df = pd.DataFrame.from_records(records)
    return df
