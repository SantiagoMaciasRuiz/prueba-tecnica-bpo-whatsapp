from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_raw_messages(file_path: str | Path) -> List[Dict[str, str]]:
    """Load the raw pipe-delimited message dump and return normalized row dictionaries."""
    source = Path(file_path)
    lines = source.read_text(encoding='utf-8', errors='replace').splitlines()

    rows: List[Dict[str, str]] = []
    header: List[str] | None = None

    for row in lines:
        stripped = row.strip()
        if not stripped:
            continue
        if not stripped.startswith('|'):
            continue
        if '----' in stripped:
            continue

        cells = [cell.strip() for cell in stripped.strip('|').split('|')]
        if header is None:
            header = [cell.strip().strip('`') for cell in cells]
            continue

        if len(cells) < len(header):
            cells.extend([''] * (len(header) - len(cells)))
        elif len(cells) > len(header):
            raise ValueError(
                f'Row has {len(cells)} fields but the header has {len(header)} fields.'
            )

        row_dict = {header[idx]: _clean_cell(cells[idx]) for idx in range(len(header))}
        rows.append(row_dict)

    return rows
