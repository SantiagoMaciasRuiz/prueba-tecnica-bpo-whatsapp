from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from etl.loader import load_raw_messages
from etl.transformer import normalize_messages, parse_json_safe, classify_incoming_message
from etl.validator import validate_processed_messages


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'raw' / 'prueba.txt'


def _real_rows():
    return load_raw_messages(SOURCE)


def _minimal_row(**overrides):
    row = {
        'id': '1',
        'content': 'Hola',
        'account_id': '37',
        'inbox_id': '78',
        'conversation_id': '10',
        'message_type': 'incoming',
        'created_at': '2023-07-28 14:27:58.000',
        'updated_at': '2023-07-28 14:27:58.000',
        'private': 'false',
        'status': 'sent',
        'source_id': 'source',
        'content_type': 'text',
        'content_attributes': '"{}"',
        'additional_attributes': '"{}"',
    }
    row.update(overrides)
    return row


def test_loader_preserves_real_json_quotes_and_all_source_columns():
    rows = _real_rows()
    assert len(rows) == 3687
    assert len(rows[0]) == 24
    error_row = next(row for row in rows if 'external_error' in row['content_attributes'])
    assert '\\"external_error\\"' in error_row['content_attributes']
    payload, status = parse_json_safe(error_row['content_attributes'])
    assert status == 'valid'
    assert payload['external_error']


def test_real_json_attributes_are_extracted_from_their_actual_columns():
    processed = normalize_messages(_real_rows())
    assert processed['external_error'].ne('').sum() == 1396
    assert processed['template_name'].ne('').sum() == 1640
    assert processed['sistema_call_source'].ne('').sum() == 301
    assert processed['in_reply_to'].ne('').sum() == 19


def test_transformer_preserves_columns_and_converts_timestamps():
    rows = _real_rows()
    processed = normalize_messages(rows)
    assert set(rows[0]).issubset(processed.columns)
    assert pd.api.types.is_datetime64_ns_dtype(processed['created_at'])
    assert pd.api.types.is_datetime64_ns_dtype(processed['updated_at'])
    assert processed['created_at'].notna().all()
    assert processed['updated_at'].notna().all()
    assert processed['date'].notna().all()
    assert processed['hour'].notna().all()
    assert processed['day_of_week'].ne('').all()


def test_event_categories_follow_business_rules():
    processed = normalize_messages(_real_rows())
    assert (processed.loc[processed.message_type == 'incoming', 'event_category'] == 'user_message').all()
    assert (processed.loc[processed.message_type == 'activity', 'event_category'] == 'system_activity').all()
    failed = processed[(processed.message_type == 'outgoing') & (processed.status == 'failed')]
    assert not failed.empty
    assert (failed.event_category == 'delivery_error').all()


def test_message_category_uses_required_conservative_labels():
    assert classify_incoming_message('Necesito ayuda con mi factura') == 'Soporte'
    assert classify_incoming_message('No me llegó el pedido') == 'Queja'
    assert classify_incoming_message('Quiero hacer un pedido') == 'Pedido'
    assert classify_incoming_message('Mi Pedido') == 'Otros'
    assert classify_incoming_message('En pdf') == 'Otros'


def test_all_incoming_messages_have_a_category():
    processed = normalize_messages(_real_rows())
    incoming = processed[processed.message_type == 'incoming']
    assert len(incoming) == 430
    assert incoming.message_category.notna().all()
    assert incoming.message_category.ne('').all()


def test_validator_reconciles_real_dataset_and_reports_quality():
    rows = _real_rows()
    processed = normalize_messages(rows)
    report = validate_processed_messages(
        processed,
        source_rows=len(rows),
        exported_rows=len(processed),
        original_columns=list(rows[0]),
    )
    assert report['is_valid'] is True
    assert report['source_rows'] == report['processed_rows'] == report['exported_rows'] == 3687
    assert report['row_difference'] == 0
    assert report['columns']['discarded'] == []
    assert report['derived_fields']['external_error']['count'] == 1396
    assert report['derived_fields']['template_name']['count'] == 1640


def test_validator_detects_duplicate_and_empty_identifiers():
    processed = normalize_messages([
        _minimal_row(id='1'),
        _minimal_row(id='1', conversation_id=''),
    ])
    report = validate_processed_messages(processed, source_rows=2, exported_rows=2)
    assert report['checks']['duplicate_id_rows']['count'] == 2
    assert report['checks']['empty_conversation_id']['count'] == 1
    assert report['is_valid'] is False


def test_validator_detects_invalid_dates_and_unexpected_values():
    processed = normalize_messages([_minimal_row(
        created_at='not-a-date',
        updated_at='not-a-date',
        message_type='new_type',
        status='queued',
    )])
    report = validate_processed_messages(processed, source_rows=1, exported_rows=1)
    assert report['checks']['invalid_created_at']['count'] == 1
    assert report['checks']['invalid_updated_at']['count'] == 1
    assert report['checks']['unexpected_message_type']['count'] == 1
    assert report['checks']['unexpected_status']['count'] == 1
    assert report['is_valid'] is False


def test_validator_detects_empty_strings_and_invalid_json():
    processed = normalize_messages([_minimal_row(
        content='   ',
        content_attributes='{"broken":',
    )])
    report = validate_processed_messages(processed, source_rows=1, exported_rows=1)
    assert processed.loc[0, 'content_json_status'] == 'invalid'
    assert report['checks']['empty_content']['count'] == 1


def test_parse_json_safe_distinguishes_empty_valid_and_invalid():
    assert parse_json_safe(None)[1] == 'empty'
    assert parse_json_safe('   ')[1] == 'empty'
    assert parse_json_safe('"{}"')[1] == 'valid'
    assert parse_json_safe('{invalid')[1] == 'invalid'
