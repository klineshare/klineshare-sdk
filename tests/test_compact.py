from __future__ import annotations

from klineshare.compact import (
    expand_compact,
    expand_kline_matrix,
    expand_kline_raw,
    is_compact_payload,
    is_kline_matrix_payload,
    is_kline_raw_payload,
)


def test_expand_compact_rows() -> None:
    payload = {
        'success': True,
        'format': 'compact',
        'fields': ['symbol', 'name', 'price', 'volume'],
        'sep': '|',
        'data': ['600519.SS|贵州茅台|1294.88|1000', '000001.SZ|平安银行|10.5|200'],
    }
    rows = expand_compact(payload)
    assert len(rows) == 2
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['price'] == 1294.88
    assert rows[1]['volume'] == 200


def test_expand_nested_minutes() -> None:
    payload = {
        'format': 'compact',
        'fields': ['symbol', 'minutes'],
        'sep': '|',
        'minutes_fields': ['time', 'price', 'volume', 'amount'],
        'minutes_sep': ',',
        'minutes_row_sep': ';',
        'data': ['600519.SS|09:15,100,0,0;09:25,101,10,1000'],
    }
    rows = expand_compact(payload)
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['minutes'][0]['time'] == '09:15'
    assert rows[0]['minutes'][1]['price'] == 101


def test_is_compact_payload() -> None:
    assert is_compact_payload({'format': 'compact', 'fields': [], 'data': []})
    assert is_compact_payload({'data': {'format': 'compact', 'fields': [], 'sep': '|', 'data': []}})
    assert not is_compact_payload({'data': [{'a': 1}]})


def test_expand_kline_matrix_single() -> None:
    payload = {
        'success': True,
        'fields': ['date', 'timestamp', 'open', 'close'],
        'meta': {'symbol_count': 1},
        'symbols': {
            '600519.SS': [
                ['20250102', 1_735_776_000_000, 100.0, 101.0],
                ['20250103', 1_735_862_400_000, 101.0, 102.5],
            ],
        },
    }
    assert is_kline_matrix_payload(payload)
    rows = expand_kline_matrix(payload)
    assert len(rows) == 2
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['date'] == '20250102'
    assert rows[0]['close'] == 101.0
    assert rows[1]['timestamp'] == 1_735_862_400_000
    assert rows[1]['close'] == 102.5


def test_expand_kline_matrix_multi() -> None:
    payload = {
        'fields': ['date', 'close'],
        'symbols': {
            '000001.SZ': [['20250102', 10.5]],
            '600519.SS': [['20250102', 100.0]],
        },
    }
    rows = expand_kline_matrix(payload)
    assert len(rows) == 2
    assert {r['symbol'] for r in rows} == {'000001.SZ', '600519.SS'}


def test_kline_matrix_not_confused_with_compact() -> None:
    compact = {
        'format': 'compact',
        'fields': ['symbol', 'price'],
        'sep': '|',
        'data': ['600519.SS|1'],
        'symbols': {},  # should not win over format=compact
    }
    assert is_compact_payload(compact)
    assert not is_kline_matrix_payload(compact)


def test_expand_kline_raw_batch() -> None:
    payload = {
        'success': True,
        'format': 'raw',
        'fields': ['date', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'amount'],
        'sep': '|',
        'row_sep': ';',
        'symbols': {
            '600519.SS': (
                '20231115|1700000000|100.5|101|99|100|1|1'
                ';20231116|1700086400||11.2|10|11|2|0'
            ),
            '000001.SZ': '20231115|1700000000|11|12|10|11.2|2|3',
        },
    }
    assert is_kline_raw_payload(payload)
    assert not is_kline_matrix_payload(payload)
    rows = expand_kline_raw(payload)
    assert len(rows) == 3
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['date'] == '20231115'
    assert rows[0]['open'] == 100.5
    assert rows[0]['close'] == 100
    assert rows[1]['open'] is None
    assert rows[1]['close'] == 11
    assert rows[2]['symbol'] == '000001.SZ'
    assert rows[2]['close'] == 11.2


def test_expand_kline_raw_single() -> None:
    payload = {
        'success': True,
        'format': 'raw',
        'fields': ['date', 'timestamp', 'open', 'close'],
        'sep': '|',
        'row_sep': ';',
        'data': '20231115|1700000000|100|101',
        'meta': {'symbol': '600519.SS'},
    }
    assert is_kline_raw_payload(payload)
    rows = expand_kline_raw(payload)
    assert len(rows) == 1
    assert rows[0]['symbol'] == '600519.SS'
    assert rows[0]['close'] == 101


def test_expand_kline_raw_indicators_json_cell() -> None:
    payload = {
        'format': 'raw',
        'fields': ['date', 'close', 'indicators'],
        'sep': '|',
        'row_sep': ';',
        'symbols': {
            '600519.SS': '20250620|105.2|{"rsi:14":{"14":55.3}}',
        },
    }
    rows = expand_kline_raw(payload)
    assert rows[0]['indicators']['rsi:14']['14'] == 55.3

