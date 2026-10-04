from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'reports'
SQL_DIR = ROOT / 'sql'
CSV_PATH = ROOT / 'data' / 'processed' / 'messages_clean.csv'
OUTPUT_PATH = REPORT_DIR / 'sql_validation_report.json'
TOLERANCE = 0.01


def load_env() -> dict[str, str]:
    values = {}
    env_path = ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
    values.update({key: value for key, value in os.environ.items() if key in {
        'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_PORT', 'PGHOST'
    }})
    return values


def clean_query(path: Path) -> str:
    query = path.read_text(encoding='utf-8')
    query = query.replace('$1::timestamp', 'NULL::timestamp')
    query = query.replace('$2::timestamp', 'NULL::timestamp')
    query = query.replace('$3::text', 'NULL::text')
    return query.strip().rstrip(';')


def run_query(connection, query: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def value_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(actual) - float(expected)) <= TOLERANCE
    return actual == expected


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    env = load_env()
    connection = psycopg2.connect(
        dbname=env.get('POSTGRES_DB', 'etl_db'),
        user=env.get('POSTGRES_USER', 'etl_user'),
        password=env.get('POSTGRES_PASSWORD', 'etl_local_password'),
        host=env.get('PGHOST', 'localhost'),
        port=int(env.get('POSTGRES_PORT', '5433')),
    )
    connection.autocommit = True

    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS messages_clean')
        schema_sql = (SQL_DIR / 'schema.sql').read_text(encoding='utf-8')
        schema_without_comments = re.sub(r'(?m)^\s*--.*$', '', schema_sql)
        statements = [part.strip() for part in schema_without_comments.split(';') if part.strip()]
        for statement in statements:
            cursor.execute(statement)
        with CSV_PATH.open('r', encoding='utf-8', newline='') as csv_file:
            cursor.copy_expert(
                "COPY messages_clean FROM STDIN WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')",
                csv_file,
            )

    python_report = json.loads((REPORT_DIR / 'pre_sql_analysis.json').read_text(encoding='utf-8'))
    golden = python_report['golden_results']

    row_count = run_query(connection, 'SELECT COUNT(*) AS count FROM messages_clean')[0]['count']
    identifier_check = run_query(connection, '''
        SELECT COUNT(*) AS total_rows,
               COUNT(id) AS non_null_ids,
               COUNT(DISTINCT id) AS unique_ids,
               COUNT(*) - COUNT(DISTINCT id) AS duplicate_ids,
               COUNT(*) FILTER (WHERE conversation_id IS NULL OR btrim(conversation_id) = '') AS empty_conversation_ids
        FROM messages_clean
    ''')[0]

    funnel_rows = run_query(connection, clean_query(SQL_DIR / '01_delivery_funnel.sql'))
    funnel_actual = {row['status']: int(row['message_count']) for row in funnel_rows}
    funnel_expected = {'read': golden['outgoing_read'], 'delivered': golden['outgoing_delivered'], 'failed': golden['outgoing_failed'], 'sent': golden['total_outgoing'] - golden['outgoing_read'] - golden['outgoing_delivered'] - golden['outgoing_failed']}
    funnel_difference = {key: funnel_actual.get(key, 0) - value for key, value in funnel_expected.items()}

    sla_row = run_query(connection, clean_query(SQL_DIR / '02_response_sla.sql'))[0]
    sla_actual = {
        'total_incoming': int(sla_row['total_incoming']),
        'responded': int(sla_row['responded']),
        'unanswered': int(sla_row['unanswered']),
        'average_minutes': float(sla_row['average_minutes']) if sla_row['average_minutes'] is not None else None,
        'median_minutes': float(sla_row['median_minutes']) if sla_row['median_minutes'] is not None else None,
        'p95_minutes': float(sla_row['p95_minutes']) if sla_row['p95_minutes'] is not None else None,
        'max_minutes': float(sla_row['max_minutes']) if sla_row['max_minutes'] is not None else None,
    }
    sla_expected = {
        'total_incoming': golden['total_incoming'],
        'responded': golden['incoming_with_response'],
        'unanswered': golden['incoming_without_response'],
        'average_minutes': golden['sla_mean_minutes'],
        'median_minutes': golden['sla_median_minutes'],
        'p95_minutes': 1152.6833333333334,
        'max_minutes': 2695.8166666666666,
    }
    sla_difference = {key: (None if sla_actual[key] is None else sla_actual[key] - value) for key, value in sla_expected.items()}

    hourly_rows = run_query(connection, clean_query(SQL_DIR / '03_hourly_incoming.sql'))
    hourly_actual_total = sum(int(row['incoming_count']) for row in hourly_rows)
    hourly_expected_total = golden['total_incoming']

    column_names = [row['column_name'] for row in run_query(connection, '''
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'messages_clean'
        ORDER BY ordinal_position
    ''')]
    with CSV_PATH.open('r', encoding='utf-8', newline='') as csv_file:
        csv_columns = next(csv.reader(csv_file))
    column_check = {'csv_only': sorted(set(csv_columns) - set(column_names)), 'database_only': sorted(set(column_names) - set(csv_columns))}
    database_types = run_query(connection, '''
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'messages_clean'
    ''')
    expected_types = {
        'id': ('text', 'text'),
        'conversation_id': ('text', 'text'),
        'created_at': ('timestamp without time zone', 'timestamp'),
        'updated_at': ('timestamp without time zone', 'timestamp'),
        'private': ('boolean', 'bool'),
        'hour': ('integer', 'int4'),
        'date': ('date', 'date'),
    }
    type_differences = {
        row['column_name']: {
            'expected': expected_types[row['column_name']],
            'actual': (row['data_type'], row['udt_name']),
        }
        for row in database_types
        if row['column_name'] in expected_types
        and (row['data_type'], row['udt_name']) != expected_types[row['column_name']]
    }
    primary_key_columns = [row['column_name'] for row in run_query(connection, '''
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = 'messages_clean'
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
    ''')]

    explain_results = {}
    for name in ('01_delivery_funnel.sql', '02_response_sla.sql', '03_hourly_incoming.sql'):
        explain_query = 'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + clean_query(SQL_DIR / name)
        explain_results[name] = run_query(connection, explain_query)[0]['QUERY PLAN'][0]

    edge_query = '''
    WITH ordered AS (
        SELECT m.*, ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY created_at, id) AS event_order,
               LEAD(message_type) OVER (PARTITION BY conversation_id ORDER BY created_at, id) AS immediate_next_type
        FROM messages_clean m
    ), incoming AS (
        SELECT o.*,
               a.id AS response_id, a.message_type AS response_type, a.created_at AS response_created_at,
               EXTRACT(EPOCH FROM (a.created_at - o.created_at)) / 60.0 AS response_minutes,
               ROW_NUMBER() OVER (PARTITION BY o.id ORDER BY a.created_at, a.id) AS response_rank
        FROM ordered o
        LEFT JOIN messages_clean a ON a.conversation_id = o.conversation_id
          AND a.message_type IN ('activity', 'outgoing')
          AND (a.created_at > o.created_at OR (a.created_at = o.created_at AND a.id > o.id))
        WHERE o.message_type = 'incoming'
    )
    SELECT conversation_id, id AS incoming_id, created_at AS incoming_created_at,
           response_id, response_type, response_created_at, response_minutes,
           immediate_next_type
    FROM incoming
    WHERE response_rank = 1 OR response_rank IS NULL
    ORDER BY response_minutes DESC NULLS LAST
    '''
    edge_rows = run_query(connection, edge_query)
    edge_cases = {
        'incoming_activity': next((row for row in edge_rows if row['immediate_next_type'] == 'activity'), None),
        'incoming_outgoing': next((row for row in edge_rows if row['immediate_next_type'] == 'outgoing'), None),
        'incoming_incoming_then_action': next((row for row in edge_rows if row['immediate_next_type'] == 'incoming' and row['response_type'] in {'activity', 'outgoing'}), None),
        'without_response': next((row for row in edge_rows if row['response_id'] is None), None),
    }
    tie_case = run_query(connection, '''
        SELECT conversation_id, created_at, array_agg(id ORDER BY id) AS ids
        FROM messages_clean
        GROUP BY conversation_id, created_at
        HAVING COUNT(*) > 1
        ORDER BY conversation_id, created_at
        LIMIT 1
    ''')

    result = {
        'connection': {'database': env.get('POSTGRES_DB', 'etl_db'), 'host': env.get('PGHOST', 'localhost'), 'port': int(env.get('POSTGRES_PORT', '5433'))},
        'row_count': {'expected': 3687, 'actual': int(row_count), 'difference': int(row_count) - 3687, 'passed': int(row_count) == 3687},
        'identifiers': {key: int(value) for key, value in identifier_check.items()},
        'columns': column_check | {
            'type_differences': type_differences,
            'primary_key_columns': primary_key_columns,
            'passed': not column_check['csv_only'] and not column_check['database_only'] and not type_differences and primary_key_columns == ['id'],
        },
        'funnel': {'expected': funnel_expected, 'actual': funnel_actual, 'difference': funnel_difference, 'passed': not any(funnel_difference.values())},
        'sla': {'expected': sla_expected, 'actual': sla_actual, 'difference': sla_difference, 'passed': all(value_equal(sla_actual[key], value) for key, value in sla_expected.items())},
        'hourly': {'expected_total': hourly_expected_total, 'actual_total': hourly_actual_total, 'difference': hourly_actual_total - hourly_expected_total, 'hours_returned': len(hourly_rows), 'passed': hourly_actual_total == hourly_expected_total and len(hourly_rows) == 24},
        'edge_cases': {'examples': edge_cases, 'equal_timestamp_example': tie_case[0] if tie_case else None},
        'performance': explain_results,
        'tolerance_minutes': TOLERANCE,
    }
    result['passed'] = all(result[key]['passed'] for key in ('row_count', 'columns', 'funnel', 'sla', 'hourly'))
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('row_count', 'columns', 'funnel', 'sla', 'hourly', 'passed')}, ensure_ascii=False, indent=2, default=str))
    connection.close()


if __name__ == '__main__':
    main()
