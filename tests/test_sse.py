from __future__ import annotations

from klineshare._sse import iter_sse_json


def test_iter_sse_json() -> None:
    lines = iter([
        ': comment',
        'event: ping',
        'data: {"type":"ready"}',
        '',
        'data: {"type":"event","data":{"x":1}}',
        '',
        'data: not-json',
        '',
    ])
    events = list(iter_sse_json(lines))
    assert events[0] == {'type': 'ready'}
    assert events[1]['type'] == 'event'
    assert events[2] == {'raw': 'not-json'}
