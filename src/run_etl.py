from __future__ import annotations

import json
from pathlib import Path

from etl.loader import load_raw_messages
from etl.transformer import normalize_messages
from etl.validator import validate_processed_messages


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / 'data' / 'raw' / 'prueba.txt'
PROCESSED_PATH = ROOT / 'data' / 'processed' / 'messages_clean.csv'
REPORT_PATH = ROOT / 'reports' / 'etl_quality_report.json'


def main() -> None:
    raw_rows = load_raw_messages(RAW_PATH)
    processed = normalize_messages(raw_rows)

    if processed.empty:
        raise ValueError('No data was produced from the raw source file.')

    processed.to_csv(PROCESSED_PATH, index=False)
    quality = validate_processed_messages(
        processed,
        source_rows=len(raw_rows),
        exported_rows=len(processed),
        original_columns=list(raw_rows[0].keys()) if raw_rows else [],
    )
    REPORT_PATH.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Rows processed: {len(processed)}')
    print(f'Valid: {quality["is_valid"]}')
    print(f'Quality report: {REPORT_PATH}')
    print(f'Clean file: {PROCESSED_PATH}')


if __name__ == '__main__':
    main()
