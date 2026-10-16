"""Parse KlineShare compact / kline matrix / kline raw payloads."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence


def _coerce_cell(value: str) -> Any:
    if value == '':
        return None
    # nested JSON (e.g. indicators) encoded into a raw cell
    if value[0] in '{[':
        try:
            return json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    # keep times / symbols as strings
    if any(c in value for c in (':', '/', '-')) and not value.replace('.', '', 1).replace('-', '', 1).isdigit():
        return value
    try:
        if '.' in value or 'e' in value.lower():
            num = float(value)
            if num == int(num) and abs(num) < 1e15:
                return int(num)
            return num
        return int(value)
    except ValueError:
        return value


def _decode_raw_rows(
    text: str,
    fields: Sequence[str],
    *,
    sep: str = '|',
    row_sep: str = ';',
    symbol: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not text:
        return []
    out: List[Dict[str, Any]] = []
    for chunk in str(text).split(row_sep):
        if not chunk:
            continue
        cols = chunk.split(sep)
        item: Dict[str, Any] = {}
        if symbol is not None:
            item['symbol'] = symbol
        for i, key in enumerate(fields):
            val = cols[i] if i < len(cols) else ''
            if key in ('symbol', 'name', 'trade_date', 'date', 'time', 'market'):
                item[key] = val if val != '' else None
            else:
                item[key] = _coerce_cell(val)
        out.append(item)
    return out


def decode_minutes_compact(
    raw: str,
    *,
    fields: Sequence[str] = ('time', 'price', 'volume', 'amount'),
    sep: str = ',',
    row_sep: str = ';',
) -> List[Dict[str, Any]]:
    text = (raw or '').strip()
    if not text:
        return []
    out: List[Dict[str, Any]] = []
    for chunk in text.split(row_sep):
        if not chunk:
            continue
        cols = chunk.split(sep)
        while len(cols) < len(fields):
            cols.append('')
        item: Dict[str, Any] = {}
        for i, key in enumerate(fields):
            val = cols[i] if i < len(cols) else ''
            item[key] = val if key == 'time' else _coerce_cell(val)
        out.append(item)
    return out


def expand_compact(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expand a compact response body (or its ``data`` wrapper) into row dicts.

    Expected keys: ``fields``, ``sep``, ``data`` (list of strings).
    Optional nested minutes: field ``minutes`` with ``minutes_sep`` / ``minutes_row_sep``
    and ``minutes_fields``.
    """
    if not isinstance(payload, dict):
        raise TypeError('compact payload must be a dict')

    # Allow passing the full API envelope
    body = payload
    if payload.get('format') != 'compact' and isinstance(payload.get('data'), dict):
        if payload['data'].get('format') == 'compact' or 'fields' in payload['data']:
            body = payload['data']

    fields = body.get('fields') or []
    sep = body.get('sep') or '|'
    rows = body.get('data') or []
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise ValueError('invalid compact payload: fields/data')

    minutes_fields = body.get('minutes_fields') or ('time', 'price', 'volume', 'amount')
    minutes_sep = body.get('minutes_sep') or ','
    minutes_row_sep = body.get('minutes_row_sep') or ';'

    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
            continue
        cols = str(row).split(sep)
        item: Dict[str, Any] = {}
        for i, key in enumerate(fields):
            val = cols[i] if i < len(cols) else ''
            if key == 'minutes':
                item[key] = decode_minutes_compact(
                    val,
                    fields=minutes_fields,
                    sep=minutes_sep,
                    row_sep=minutes_row_sep,
                )
            elif key in ('symbol', 'name', 'trade_date', 'date', 'time', 'market'):
                item[key] = val if val != '' else None
            else:
                item[key] = _coerce_cell(val)
        out.append(item)
    return out


def is_compact_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get('format') == 'compact':
        return True
    data = payload.get('data')
    return isinstance(data, dict) and (
        data.get('format') == 'compact' or ('fields' in data and 'sep' in data)
    )


def is_kline_raw_payload(payload: Any) -> bool:
    """
    Detect kline ``format=raw`` envelopes.

    Batch (v2): ``fields`` + ``symbols`` map of delimited strings.
    Single (v1-style): ``fields`` + ``data`` as one delimited string.
    """
    if not isinstance(payload, dict):
        return False

    body = payload
    if payload.get('format') != 'raw' and isinstance(payload.get('data'), dict):
        if payload['data'].get('format') == 'raw':
            body = payload['data']

    if body.get('format') == 'raw':
        return isinstance(body.get('fields'), list)

    # Infer without format tag: string cells + fields
    fields = body.get('fields')
    if not isinstance(fields, list) or not fields:
        return False
    symbols = body.get('symbols')
    if isinstance(symbols, dict) and symbols and any(isinstance(v, str) for v in symbols.values()):
        return True
    data = body.get('data')
    return isinstance(data, str) and ('sep' in body or 'row_sep' in body)


def is_kline_matrix_payload(payload: Any) -> bool:
    """Detect v2 kline columnar envelope: ``fields`` + ``symbols`` map of row arrays."""
    if not isinstance(payload, dict):
        return False
    if is_kline_raw_payload(payload):
        return False
    body = payload
    if 'symbols' not in body and isinstance(body.get('data'), dict):
        body = body['data']
    return (
        isinstance(body.get('fields'), list)
        and isinstance(body.get('symbols'), dict)
        and body.get('format') not in ('compact', 'raw')
    )


def expand_kline_raw(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expand ``format=raw`` kline payload into list-of-dicts.

    Batch::

        {
          "format": "raw",
          "fields": [...],
          "sep": "|",
          "row_sep": ";",
          "symbols": {"600519.SS": "date|ts|...;..."}
        }

    Single (v1-style)::

        {"format": "raw", "fields": [...], "data": "date|ts|...;...", "meta": {...}}
    """
    if not isinstance(payload, dict):
        raise TypeError('kline raw payload must be a dict')

    body = payload
    if payload.get('format') != 'raw' and isinstance(payload.get('data'), dict):
        if payload['data'].get('format') == 'raw' or is_kline_raw_payload(payload['data']):
            body = payload['data']

    fields = body.get('fields') or []
    sep = body.get('sep') or '|'
    row_sep = body.get('row_sep') or ';'
    if not isinstance(fields, list):
        raise ValueError('invalid kline raw: fields')

    symbols = body.get('symbols')
    if isinstance(symbols, dict):
        out: List[Dict[str, Any]] = []
        for sym, blob in symbols.items():
            if isinstance(blob, str):
                out.extend(
                    _decode_raw_rows(blob, fields, sep=sep, row_sep=row_sep, symbol=sym)
                )
            elif isinstance(blob, list):
                # defensive: treat as matrix rows if server mixed modes
                for row in blob:
                    item: Dict[str, Any] = {'symbol': sym}
                    if isinstance(row, dict):
                        item.update(row)
                    elif isinstance(row, (list, tuple)):
                        for i, key in enumerate(fields):
                            item[key] = row[i] if i < len(row) else None
                    else:
                        continue
                    out.append(item)
        return out

    data = body.get('data')
    if isinstance(data, str):
        meta = body.get('meta') if isinstance(body.get('meta'), dict) else {}
        sym = meta.get('symbol')
        return _decode_raw_rows(data, fields, sep=sep, row_sep=row_sep, symbol=sym)

    raise ValueError('invalid kline raw: expected symbols map or data string')


def expand_kline_matrix(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expand columnar kline payload into list-of-dicts (one bar per row).

    Shape::

        {
          "fields": ["date", "timestamp", "open", ...],
          "symbols": {"600519.SS": [[...], ...], ...},
          "meta": {...}
        }

    Each output row includes ``symbol``. Multi-symbol responses are flattened
    in iteration order of ``symbols``.
    """
    if not isinstance(payload, dict):
        raise TypeError('kline matrix payload must be a dict')

    body = payload
    if 'symbols' not in body and isinstance(body.get('data'), dict):
        if is_kline_matrix_payload(body['data']):
            body = body['data']

    fields = body.get('fields') or []
    symbols = body.get('symbols') or {}
    if not isinstance(fields, list) or not isinstance(symbols, dict):
        raise ValueError('invalid kline matrix: fields/symbols')

    out: List[Dict[str, Any]] = []
    for sym, rows in symbols.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            item: Dict[str, Any] = {'symbol': sym}
            if isinstance(row, dict):
                item.update(row)
                out.append(item)
                continue
            if not isinstance(row, (list, tuple)):
                continue
            for i, key in enumerate(fields):
                item[key] = row[i] if i < len(row) else None
            out.append(item)
    return out
