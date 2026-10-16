from __future__ import annotations

import pytest

from klineshare.symbols import (
    normalize_hk_symbol,
    normalize_hk_symbols,
    normalize_symbol,
    normalize_symbols,
)


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('600519.SH', '600519.SS'),
        ('600519.sh', '600519.SS'),
        ('600519.SS', '600519.SS'),
        ('000001.SZ', '000001.SZ'),
        ('920000.BJ', '920000.BJ'),
        ('sh600519', '600519.SS'),
        ('sz000001', '000001.SZ'),
        ('bj920000', '920000.BJ'),
        ('600519', '600519.SS'),
        ('000001', '000001.SZ'),
        ('300750', '300750.SZ'),
        ('920000', '920000.BJ'),
        ('AAPL.US', 'AAPL.US'),
        ('aapl', 'AAPL.US'),
        ('00700.HK', '00700.HK'),
        ('700.HK', '00700.HK'),
        ('hk00700', '00700.HK'),
    ],
)
def test_normalize_symbol(raw: str, expected: str) -> None:
    assert normalize_symbol(raw) == expected


def test_normalize_symbols_csv() -> None:
    assert normalize_symbols('600519.SH,000001.SZ') == '600519.SS,000001.SZ'


def test_normalize_symbols_list() -> None:
    assert normalize_symbols(['600519.SH', '000001.SZ']) == '600519.SS,000001.SZ'


def test_normalize_empty() -> None:
    with pytest.raises(ValueError):
        normalize_symbol('')
    assert normalize_symbols(None) is None


def test_unknown_suffix() -> None:
    with pytest.raises(ValueError):
        normalize_symbol('600519.XX')


def test_normalize_hk_symbol() -> None:
    assert normalize_hk_symbol('00700') == '00700.HK'
    assert normalize_hk_symbol('700') == '00700.HK'
    assert normalize_hk_symbol('HK00700') == '00700.HK'
    assert normalize_hk_symbol('09988.HK') == '09988.HK'
    assert normalize_hk_symbols(['700', '9988.HK']) == '00700.HK,09988.HK'
    with pytest.raises(ValueError):
        normalize_symbol('00700')  # 5 位裸码不是 A 股；港股请用 normalize_hk_symbol
