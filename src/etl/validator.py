from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd


KNOWN_MESSAGE_TYPES = {'incoming', 'outgoing', 'activity'}
KNOWN_STATUSES = {'sent', 'delivered', 'read', 'failed'}


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ''


def _empty_count(series: pd.Series) -> int:
    return int(series.map(_is_empty).sum())


def _field_metric(count: int, total: int) -> Dict[str, float | int]:
    return {'count': int(count), 'percentage': round((count / total * 100) if total else 0, 2)}


def _distribution(series: pd.Series, total: int) -> Dict[str, Dict[str, float | int]]:
    counts = series.fillna('').astype(str).value_counts(dropna=False).to_dict()
    return {
        str(key) if str(key) else '(empty)': {
            'count': int(value),
            'percentage': round((int(value) / total * 100) if total else 0, 2),
        }
        for key, value in counts.items()
    }


def validate_processed_messages(
    df: pd.DataFrame,
    source_rows: int | None = None,
    exported_rows: int | None = None,
    original_columns: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Return an explicit, data-backed quality report for the processed dataset."""
    total = int(len(df))
    original_columns = list(original_columns or df.columns)
    unexpected_types = sorted(set(df['message_type'].dropna().astype(str)) - KNOWN_MESSAGE_TYPES)
    unexpected_statuses = sorted(set(df['status'].dropna().astype(str)) - KNOWN_STATUSES)
    created = pd.to_datetime(df['created_at'], errors='coerce')
    updated = pd.to_datetime(df['updated_at'], errors='coerce')
    duplicate_ids = int(df['id'].duplicated(keep=False).sum())
    empty_ids = _empty_count(df['id'])
    empty_conversations = _empty_count(df['conversation_id'])
    empty_content = _empty_count(df['content'])
    empty_status = _empty_count(df['status'])
    incoming = df['message_type'].eq('incoming')
    incoming_unclassified = int((incoming & df['message_category'].map(_is_empty)).sum())

    checks = {
        'duplicate_id_rows': _field_metric(duplicate_ids, total),
        'empty_id': _field_metric(empty_ids, total),
        'empty_conversation_id': _field_metric(empty_conversations, total),
        'empty_content': _field_metric(empty_content, total),
        'empty_status': _field_metric(empty_status, total),
        'invalid_created_at': _field_metric(int(created.isna().sum()), total),
        'invalid_updated_at': _field_metric(int(updated.isna().sum()), total),
        'unexpected_message_type': _field_metric(sum(int(df['message_type'].eq(value).sum()) for value in unexpected_types), total),
        'unexpected_status': _field_metric(sum(int(df['status'].eq(value).sum()) for value in unexpected_statuses), total),
        'incoming_unclassified': _field_metric(incoming_unclassified, int(incoming.sum())),
    }
    business_rule_violations = {
        'incoming_not_user_message': int((incoming & df['event_category'].ne('user_message')).sum()),
        'activity_not_system_activity': int((df['message_type'].eq('activity') & df['event_category'].ne('system_activity')).sum()),
        'failed_outgoing_not_delivery_error': int((df['message_type'].eq('outgoing') & df['status'].eq('failed') & df['event_category'].ne('delivery_error')).sum()),
    }
    columns = list(df.columns)
    discarded = [column for column in original_columns if column not in columns]
    is_valid = bool(
        total > 0
        and source_rows is not None
        and exported_rows is not None
        and source_rows == exported_rows == total
        and not any(checks[key]['count'] for key in ('duplicate_id_rows', 'empty_id', 'empty_conversation_id', 'invalid_created_at', 'invalid_updated_at'))
        and not any(business_rule_violations.values())
        and not unexpected_types
        and not unexpected_statuses
    )

    return {
        'total_rows': total,
        'source_rows': source_rows,
        'processed_rows': total,
        'exported_rows': exported_rows,
        'row_difference': None if source_rows is None or exported_rows is None else int(source_rows - exported_rows),
        'is_valid': is_valid,
        'columns': {
            'original': original_columns,
            'conserved': columns,
            'discarded': discarded,
            'discarded_justification': 'Ninguna columna fue descartada por el transformer.' if not discarded else 'Requiere justificación explícita.',
        },
        'checks': checks,
        'business_rule_violations': business_rule_violations,
        'unexpected_values': {
            'message_type': unexpected_types,
            'status': unexpected_statuses,
            'message_type_distribution': _distribution(df['message_type'], total),
            'status_distribution': _distribution(df['status'], total),
        },
        'json': {
            field: _distribution(df[field], total)
            for field in ('content_json_status', 'additional_json_status')
        },
        'derived_fields': {
            field: _field_metric(int(df[field].map(lambda value: not _is_empty(value)).sum()), total)
            for field in ('external_error', 'template_name', 'sistema_call_source', 'in_reply_to')
        },
        'distributions': {
            'message_category': _distribution(df['message_category'], total),
            'event_category': _distribution(df['event_category'], total),
        },
        'incoming': {
            'total': int(incoming.sum()),
            'classified': int(incoming.sum()) - incoming_unclassified,
            'unclassified': incoming_unclassified,
            'distribution': _distribution(df.loc[incoming, 'message_category'], int(incoming.sum())),
        },
        'date_range': {
            'created_at_min': created.min().isoformat() if created.notna().any() else None,
            'created_at_max': created.max().isoformat() if created.notna().any() else None,
            'updated_at_min': updated.min().isoformat() if updated.notna().any() else None,
            'updated_at_max': updated.max().isoformat() if updated.notna().any() else None,
        },
    }
