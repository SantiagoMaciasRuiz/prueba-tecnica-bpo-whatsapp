from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / 'data' / 'processed' / 'messages_clean.csv'
REPORT_DIR = ROOT / 'reports'
REPORT_PATH = REPORT_DIR / 'pre_sql_analysis.json'


def metric(count: int, denominator: int) -> Dict[str, float | int]:
    return {
        'count': int(count),
        'percentage': round((count / denominator * 100) if denominator else 0, 2),
    }


def distribution(series: pd.Series, denominator: int | None = None) -> pd.DataFrame:
    denominator = int(len(series) if denominator is None else denominator)
    result = series.fillna('(empty)').astype(str).value_counts().rename_axis('value').reset_index(name='count')
    result['percentage'] = (result['count'] / denominator * 100).round(2) if denominator else 0
    return result


def records(frame: pd.DataFrame) -> list[Dict[str, Any]]:
    return json.loads(frame.to_json(orient='records', date_format='iso'))


def build_profile(data: pd.DataFrame) -> Dict[str, Any]:
    df = data.copy()
    df['_source_position'] = range(len(df))
    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
    df['updated_at'] = pd.to_datetime(df['updated_at'], errors='coerce')
    df['id_key'] = df['id'].fillna('').astype(str)
    df['conversation_key'] = df['conversation_id'].fillna('').astype(str)
    df['external_error'] = df['external_error'].fillna('').astype(str)
    df['template_name'] = df['template_name'].fillna('').astype(str)
    df['message_category'] = df['message_category'].fillna('').astype(str)

    total = len(df)
    type_table = distribution(df['message_type'], total).rename(columns={'value': 'message_type'})
    status_table = distribution(df['status'], total).rename(columns={'value': 'status'})
    cross_table = (
        df.groupby(['message_type', 'status'], dropna=False).size().reset_index(name='count')
    )
    cross_table['percentage'] = (cross_table['count'] / total * 100).round(2)

    outgoing = df[df['message_type'].eq('outgoing')]
    outgoing_funnel = pd.DataFrame([
        {'state': 'read', **metric(int(outgoing['status'].eq('read').sum()), len(outgoing))},
        {'state': 'delivered', **metric(int(outgoing['status'].eq('delivered').sum()), len(outgoing))},
        {'state': 'failed', **metric(int(outgoing['status'].eq('failed').sum()), len(outgoing))},
    ])

    errors = df[df['external_error'].ne('')]
    error_table = distribution(errors['external_error'], len(errors)).rename(columns={'value': 'external_error'})
    error_status = (
        errors.groupby(['external_error', 'status']).size().reset_index(name='count')
    )
    error_type = (
        errors.groupby(['external_error', 'message_type']).size().reset_index(name='count')
    )

    templates = df[df['template_name'].ne('')]
    template_table = distribution(templates['template_name'], len(templates)).rename(columns={'value': 'template_name'})
    template_status = (
        templates.groupby(['template_name', 'status']).size().reset_index(name='count')
    )
    template_status['percentage'] = (template_status['count'] / len(templates) * 100).round(2) if len(templates) else 0

    ordered = df.sort_values(
        ['conversation_key', 'created_at', 'id_key'],
        kind='mergesort',
        na_position='last',
    ).copy()
    ordered['sequence_in_conversation'] = ordered.groupby('conversation_key', dropna=False).cumcount() + 1
    ordered['next_event_type'] = ordered.groupby('conversation_key', dropna=False)['message_type'].shift(-1)
    ordered['next_event_created_at'] = ordered.groupby('conversation_key', dropna=False)['created_at'].shift(-1)
    ordered['next_event_diff_minutes'] = (
        ordered['next_event_created_at'] - ordered['created_at']
    ).dt.total_seconds().div(60)

    sla_rows = []
    sequence_counts = {'incoming_activity': 0, 'incoming_outgoing': 0, 'incoming_activity_outgoing': 0, 'incoming_incoming': 0, 'incoming_end': 0}
    for conversation_id, group in ordered.groupby('conversation_key', dropna=False, sort=False):
        group = group.reset_index(drop=False)
        for position, row in group.iterrows():
            if row['message_type'] != 'incoming':
                continue
            following = group.iloc[position + 1:]
            immediate = following.iloc[0] if not following.empty else None
            actions = following[following['message_type'].isin(['activity', 'outgoing'])]
            action = actions.iloc[0] if not actions.empty else None
            if immediate is None:
                sequence_counts['incoming_end'] += 1
            elif immediate['message_type'] == 'incoming':
                sequence_counts['incoming_incoming'] += 1
            elif immediate['message_type'] == 'activity':
                if len(following) > 1 and following.iloc[1]['message_type'] == 'outgoing':
                    sequence_counts['incoming_activity_outgoing'] += 1
                else:
                    sequence_counts['incoming_activity'] += 1
            elif immediate['message_type'] == 'outgoing':
                sequence_counts['incoming_outgoing'] += 1

            sla_rows.append({
                'conversation_id': conversation_id,
                'incoming_id': row['id'],
                'incoming_created_at': row['created_at'],
                'immediate_next_event_type': immediate['message_type'] if immediate is not None else None,
                'immediate_next_event_created_at': immediate['created_at'] if immediate is not None else None,
                'next_action_type': action['message_type'] if action is not None else None,
                'next_action_created_at': action['created_at'] if action is not None else None,
                'response_minutes': (
                    (action['created_at'] - row['created_at']).total_seconds() / 60
                    if action is not None and pd.notna(action['created_at']) and pd.notna(row['created_at'])
                    else None
                ),
            })

    sla_table = pd.DataFrame(sla_rows)
    sla_table['has_response'] = sla_table['next_action_type'].notna()
    response_times = sla_table.loc[sla_table['has_response'], 'response_minutes'].dropna()
    response_stats = {
        'min': float(response_times.min()) if not response_times.empty else None,
        'mean': float(response_times.mean()) if not response_times.empty else None,
        'median': float(response_times.median()) if not response_times.empty else None,
        'max': float(response_times.max()) if not response_times.empty else None,
        'p90': float(response_times.quantile(0.90)) if not response_times.empty else None,
        'p95': float(response_times.quantile(0.95)) if not response_times.empty else None,
    }

    conversation_profile = (
        df.groupby('conversation_key', dropna=False)
        .agg(
            total_messages=('id', 'size'),
            incoming_count=('message_type', lambda values: int((values == 'incoming').sum())),
            outgoing_count=('message_type', lambda values: int((values == 'outgoing').sum())),
            activity_count=('message_type', lambda values: int((values == 'activity').sum())),
            first_created_at=('created_at', 'min'),
            last_created_at=('created_at', 'max'),
        )
        .reset_index()
        .rename(columns={'conversation_key': 'conversation_id'})
    )
    conversation_profile['duration_minutes'] = (
        conversation_profile['last_created_at'] - conversation_profile['first_created_at']
    ).dt.total_seconds().div(60)

    timestamp_counts = df.groupby(['conversation_key', 'created_at'], dropna=False).size().reset_index(name='count')
    repeated_timestamps = timestamp_counts[timestamp_counts['count'] > 1]
    tie_rows = int(repeated_timestamps['count'].sum())
    out_of_order_conversations = 0
    out_of_order_examples = []
    for conversation_id, group in df.groupby('conversation_key', dropna=False, sort=False):
        expected = group.sort_values(['created_at', 'id_key'], kind='mergesort', na_position='last')['id_key'].tolist()
        actual = group['id_key'].tolist()
        if actual != expected:
            out_of_order_conversations += 1
            if len(out_of_order_examples) < 10:
                out_of_order_examples.append({'conversation_id': conversation_id, 'source_order_ids': actual[:10], 'sorted_order_ids': expected[:10]})

    hourly = df[df['message_type'].eq('incoming')].assign(hour=df.loc[df['message_type'].eq('incoming'), 'created_at'].dt.hour)
    hourly_table = distribution(hourly['hour'], len(hourly)).rename(columns={'value': 'hour'})
    hourly_table['hour'] = hourly_table['hour'].astype(int)
    hourly_table = hourly_table.sort_values('hour')

    category_table = distribution(df.loc[df['message_type'].eq('incoming'), 'message_category'], int((df['message_type'] == 'incoming').sum())).rename(columns={'value': 'message_category'})
    sla_table['message_category'] = sla_table['incoming_id'].map(df.set_index('id_key')['message_category'])
    category_response = sla_table.assign(has_response_label=sla_table['has_response'].map({True: 'yes', False: 'no'})).groupby(['message_category', 'has_response_label']).size().reset_index(name='count')

    return {
        'integrity': {
            'total_records': total,
            'total_ids': int(df['id_key'].nunique()),
            'unique_ids': int(df['id_key'].nunique()),
            'duplicate_id_rows': int(df['id_key'].duplicated(keep=False).sum()),
            'total_conversation_ids': int(df['conversation_key'].nunique()),
            'unique_conversation_ids': int(df['conversation_key'].nunique()),
            'created_at_min': df['created_at'].min().isoformat(),
            'created_at_max': df['created_at'].max().isoformat(),
        },
        'message_type_distribution': records(type_table),
        'status_distribution': records(status_table),
        'message_type_status': records(cross_table),
        'outgoing_funnel': {'denominator': len(outgoing), 'denominator_definition': 'total outgoing', 'rows': records(outgoing_funnel)},
        'external_error': {'with_error': metric(len(errors), total), 'without_error': metric(total - len(errors), total), 'top': records(error_table.head(20)), 'by_status': records(error_status), 'by_message_type': records(error_type)},
        'templates': {'distinct_count': int(templates['template_name'].nunique()), 'distribution': records(template_table), 'by_status': records(template_status), 'failed_count': int(templates['status'].eq('failed').sum()), 'with_external_error_count': int(templates['external_error'].ne('').sum())},
        'conversations': {'distinct_count': len(conversation_profile), 'average_messages': float(conversation_profile['total_messages'].mean()), 'median_messages': float(conversation_profile['total_messages'].median()), 'min_messages': int(conversation_profile['total_messages'].min()), 'max_messages': int(conversation_profile['total_messages'].max()), 'p90_messages': float(conversation_profile['total_messages'].quantile(0.90))},
        'temporal_order': {'repeated_timestamp_groups': len(repeated_timestamps), 'rows_in_repeated_timestamp_groups': tie_rows, 'conversations_out_of_source_order': out_of_order_conversations, 'out_of_order_examples': out_of_order_examples, 'sort_rule': ['conversation_id', 'created_at', 'id']},
        'sla': {'definition': 'For each incoming, first later activity or outgoing in the same conversation; incoming followed by incoming is not a response.', 'incoming_total': int(len(sla_table)), 'incoming_with_response': int(sla_table['has_response'].sum()), 'incoming_without_response': int((~sla_table['has_response']).sum()), 'response_stats_minutes': response_stats, 'sequence_patterns': sequence_counts, 'extreme_examples': records(sla_table.nlargest(10, 'response_minutes').drop(columns=['has_response']).head(10))},
        'timezone': {'format': 'YYYY-MM-DD HH:MM:SS', 'offset_present': False, 'timezone_present': False, 'implication': 'Las horas se analizan tal como vienen en el archivo; no se aplica conversión de zona horaria.'},
        'hourly_incoming': records(hourly_table),
        'message_category': {'distribution': records(category_table), 'unexpected_categories': sorted(set(category_table['message_category']) - {'Soporte', 'Queja', 'Pedido', 'Otros'})},
        'category_response': records(category_response),
        'golden_results': {'total_rows': total, 'total_outgoing': len(outgoing), 'outgoing_read': int(outgoing['status'].eq('read').sum()), 'outgoing_delivered': int(outgoing['status'].eq('delivered').sum()), 'outgoing_failed': int(outgoing['status'].eq('failed').sum()), 'total_incoming': int((df['message_type'] == 'incoming').sum()), 'conversations': len(conversation_profile), 'incoming_with_response': int(sla_table['has_response'].sum()), 'incoming_without_response': int((~sla_table['has_response']).sum()), 'sla_mean_minutes': response_stats['mean'], 'sla_median_minutes': response_stats['median']},
    }, {
        'type_distribution': type_table,
        'status_distribution': status_table,
        'message_type_status': cross_table,
        'outgoing_funnel': outgoing_funnel,
        'external_errors': error_table,
        'external_errors_by_status': error_status,
        'external_errors_by_type': error_type,
        'template_distribution': template_table,
        'template_status': template_status,
        'conversation_profile': conversation_profile,
        'sla_reference': sla_table,
        'hourly_incoming': hourly_table,
        'message_category_distribution': category_table,
        'category_response': category_response,
    }


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INPUT_PATH, dtype={'id': 'string', 'conversation_id': 'string'}, low_memory=False)
    report, tables = build_profile(df)
    for name, table in tables.items():
        table.to_csv(REPORT_DIR / f'{name}.csv', index=False)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['golden_results'], ensure_ascii=False, indent=2))
    print(f'Report: {REPORT_PATH}')


if __name__ == '__main__':
    main()
