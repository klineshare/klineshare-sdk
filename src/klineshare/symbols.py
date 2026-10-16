"""Normalize ticker symbols to KlineShare form (e.g. 600519.SS)."""

from __future__ import annotations

from typing import Iterable, List, Optional, Union

# Explicit exchange aliases → KlineShare suffix
_SUFFIX_MAP = {
    'SH': 'SS',
    'SS': 'SS',
    'SZ': 'SZ',
    'BJ': 'BJ',
    'US': 'US',
    'HK': 'HK',
}

_SINA_PREFIX = {
    'sh': 'SS',
    'sz': 'SZ',
    'bj': 'BJ',
    'hk': 'HK',
}


def _infer_cn_suffix(code: str) -> str:
    """Guess market from a 6-digit A-share / BJ code."""
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f'无法从纯数字推断市场，请带后缀: {code}')
    head = code[0]
    if head == '6':
        return 'SS'
    if head in ('0', '3'):
        return 'SZ'
    if head in ('4', '8', '9'):
        return 'BJ'
    raise ValueError(f'无法确定市场代码: {code}')


def normalize_symbol(raw: Union[str, None]) -> str:
    """
    Convert common ticker forms to KlineShare standard.

    Accepted examples:
      - ``600519.SH`` / ``600519.sh`` → ``600519.SS``
      - ``600519.SS`` → ``600519.SS``
      - ``000001.SZ`` → ``000001.SZ``
      - ``920000.BJ`` → ``920000.BJ``
      - ``sh600519`` / ``sz000001`` / ``bj920000``
      - ``600519`` (inferred) → ``600519.SS``
      - ``AAPL.US`` / ``AAPL`` → ``AAPL.US``
      - ``00700.HK`` / ``hk00700`` → ``00700.HK``
        （5 位裸码 ``00700`` 不是 A 股；港股请用 ``normalize_hk_symbol`` / ``hkstock_*``）
    """
    text = str(raw or '').strip()
    if not text:
        raise ValueError('symbol 不能为空')

    # Sina-style prefix: sh600519 / hk00700
    lower = text.lower()
    if lower[:2] in _SINA_PREFIX and text[2:].isdigit():
        code = text[2:]
        suffix = _SINA_PREFIX[lower[:2]]
        if suffix == 'HK':
            if not (1 <= len(code) <= 5):
                raise ValueError(f'港股代码无效: {text}')
            return f'{code.zfill(5)}.HK'
        if len(code) == 6:
            return f'{code}.{suffix}'

    if '.' in text:
        code, market = text.rsplit('.', 1)
        code = code.strip()
        market = market.strip().upper()
        if not code:
            raise ValueError(f'symbol 无效: {text}')
        mapped = _SUFFIX_MAP.get(market)
        if mapped is None:
            raise ValueError(f'未知市场后缀: {market}（symbol={text}）')
        # US tickers keep letter case of the code part uppercased for consistency
        if mapped == 'US':
            return f'{code.upper()}.{mapped}'
        if mapped == 'HK':
            if not code.isdigit():
                raise ValueError(f'港股代码无效: {text}')
            return f'{code.zfill(5)}.{mapped}'
        return f'{code}.{mapped}'

    # Bare 6-digit CN code
    if text.isdigit() and len(text) == 6:
        return f'{text}.{_infer_cn_suffix(text)}'

    # Bare US ticker (letters / digits / . and - already handled)
    if text.replace('-', '').replace('.', '').isalnum() and any(c.isalpha() for c in text):
        return f'{text.upper()}.US'

    raise ValueError(f'symbol 无效: {text}')


def normalize_symbols(
    raw: Optional[Union[str, Iterable[str]]],
    *,
    sep: str = ',',
) -> Optional[str]:
    """
    Normalize one or many symbols.

    ``raw`` may be a single string, a comma-separated string, or an iterable.
    Returns a comma-joined string, or ``None`` if ``raw`` is empty/None.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(';', sep).split(sep) if p.strip()]
    else:
        parts = [str(p).strip() for p in raw if str(p).strip()]
    if not parts:
        return None
    return sep.join(normalize_symbol(p) for p in parts)


def normalize_hk_symbol(raw: Union[str, None]) -> str:
    """港股代码 → ``00700.HK``。

    接受 ``00700.HK`` / ``700.HK`` / ``00700`` / ``HK00700``。
    裸数字会按港股补齐到 5 位，**不会**当成深市 A 股。
    """
    text = str(raw or '').strip()
    if not text:
        raise ValueError('symbol 不能为空')

    lower = text.lower()
    if lower.startswith('hk') and lower[2:].isdigit():
        return f'{lower[2:].zfill(5)}.HK'

    if '.' in text:
        code, market = text.rsplit('.', 1)
        code = code.strip()
        if market.strip().upper() != 'HK':
            raise ValueError(f'港股代码须为 .HK: {text}')
        if not code.isdigit():
            raise ValueError(f'港股代码无效: {text}')
        return f'{code.zfill(5)}.HK'

    if text.isdigit() and 1 <= len(text) <= 5:
        return f'{text.zfill(5)}.HK'

    raise ValueError(f'港股 symbol 无效: {text}')


def normalize_hk_symbols(
    raw: Optional[Union[str, Iterable[str]]],
    *,
    sep: str = ',',
) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(';', sep).split(sep) if p.strip()]
    else:
        parts = [str(p).strip() for p in raw if str(p).strip()]
    if not parts:
        return None
    return sep.join(normalize_hk_symbol(p) for p in parts)
