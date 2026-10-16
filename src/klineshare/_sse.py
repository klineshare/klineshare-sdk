"""Parse Server-Sent Events (text/event-stream)."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator


def iter_sse_json(lines: Iterator[str]) -> Iterator[Dict[str, Any]]:
    """
    Yield JSON objects from SSE ``data:`` lines.

    Ignores comments / event names; empty data lines flush a multi-line buffer.
    Non-JSON data payloads are yielded as ``{"raw": "..."}``.
    """
    buf: list[str] = []
    for raw in lines:
        if raw is None:
            continue
        line = raw.rstrip('\r')
        if line == '':
            if not buf:
                continue
            payload = '\n'.join(buf)
            buf = []
            yield _parse_data(payload)
            continue
        if line.startswith(':'):
            continue
        if line.startswith('data:'):
            buf.append(line[5:].lstrip())
            continue
        # ignore event:/id:/retry:
    if buf:
        yield _parse_data('\n'.join(buf))


def _parse_data(payload: str) -> Dict[str, Any]:
    text = payload.strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {'raw': text}
    if isinstance(obj, dict):
        return obj
    return {'data': obj}


def iter_sse_from_response(resp: Any) -> Iterator[Dict[str, Any]]:
    """Iterate JSON events from a streaming ``requests.Response``."""
    def _lines() -> Iterator[str]:
        for chunk in resp.iter_lines(decode_unicode=True):
            if chunk is None:
                continue
            yield chunk

    return iter_sse_json(_lines())
