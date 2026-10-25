#!/usr/bin/env python3
"""Generate docs/API_USAGE.md: usage guide + per-API reference from api_matrix.

默认在线拉取数据样例并核对；可用 ``--offline`` 读缓存 / 跳过样例。

    python scripts/gen_api_usage_doc.py
    python scripts/gen_api_usage_doc.py --offline
    python scripts/gen_api_usage_doc.py --strict
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts'))

from api_doc_samples import (  # noqa: E402
    LiveSample,
    build_client,
    doc_sample_stub,
    fetch_samples,
    load_cache,
    _fields_of,
    render_data_table,
    render_field_table,
    save_cache,
)
from api_matrix import ApiEntry, build_matrix  # noqa: E402
from klineshare import Client  # noqa: E402

CACHE_PATH = ROOT / 'docs' / '_api_samples_cache.json'

GROUP_TITLE = {
    'meta': '元数据 / 公开文档',
    'market': '行情（个股 / 北交所 / 资料）',
    'index_etf': '指数 / ETF',
    'topics': '专题（涨停 / 龙虎榜 / 资金流 / 停复牌等）',
    'catalog': '目录',
    'bond': '债券族（bond / convertible / treasury / enterprise）',
    'extended': '扩展市场（贵金属 / 期货 / 全球 / 美股 / 港股 / 板块）',
    'ws': 'WebSocket / Level2',
    'core': 'Client 核心',
}

GROUP_ORDER = [
    'meta', 'market', 'index_etf', 'topics', 'catalog',
    'bond', 'extended', 'ws', 'core',
]

_CONST_EXPAND = {
    'S': "'600519.SS'",
    'SH': "'600519.SH'",
    'SZ': "'000001.SZ'",
    'IDX': "'000001.SH'",
    'ETF': "'510300.SS'",
    'BJ': "'920000.BJ'",
}

# Generic English matrix labels → drop; keep descriptive Chinese/custom labels.
_GENERIC_LABELS = {
    'conventional', 'alias/indirect', 'unconventional',
}

# Optional params → (literal, 说明) for synthesized 进阶用法
_PARAM_DEMO: Dict[str, Tuple[str, str]] = {
    'ks_code': ("'sh600519'", '用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）'),
    'include_valuation': ('True', '附带估值字段'),
    'include_depth': ('True', '附带盘口深度'),
    'include_minutes': ('True', '附带分时明细'),
    'all': ('True', '拉取全市场'),
    'market': ("'SS'", '指定市场（如 `SS` / `SZ`）'),
    'date': ("'20250102'", '指定交易日'),
    'tradedate': ("'20250102'", '交易日别名（与 `date` / `tradedate` 规则见方法签名）'),
    'trade_date': ("'20250102'", '指定交易日'),
    'adjust_type': ("'forward'", '复权类型'),
    'period': ('86400', '周期（秒）；日线为 `86400`'),
    'count': ('10', '返回条数'),
    'timestamp': ('1700000000', '翻页游标（请求参数为秒）'),
    'format': ('None', '不传 `format=raw`，改用服务端列式数组'),
    'batch': ("'auto'", '多标的批量策略：`multi` / `single` / `auto`'),
    'indicators': ("'ma'", '附加指标'),
    'source': ("'default'", '数据源'),
    'keyword': ("'茅台'", '关键词搜索'),
    'limit': ('20', '返回条数上限'),
    'page': ('1', '页码'),
    'offset': ('0', '偏移'),
    'start': ("'20240101'", '起始日期'),
    'end': ("'20241231'", '结束日期'),
    'bdate': ("'20240101'", '起始日'),
    'edate': ("'20241231'", '结束日'),
    'category': ("'industry'", '榜单分类（如 `industry` / `concept`）'),
    'sort': ("'net'", '排序维度'),
    'q': ("'章盟主'", '搜索词别名'),
    'listed': ('True', '仅已上市'),
    'max_pages': ('3', '最多翻页次数'),
    'with_details': ('True', '附带明细'),
    'channels': ("'depth,trades,entrust'", 'Level2 频道（含逐笔委托）'),
}


def _clean_sig(fn: Any) -> Optional[str]:
    """Readable signature without type annotations (names + defaults)."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    params: List[str] = []
    saw_kwonly = False
    for name, p in sig.parameters.items():
        if name == 'self':
            continue
        if p.kind == inspect.Parameter.KEYWORD_ONLY and not saw_kwonly:
            params.append('*')
            saw_kwonly = True
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            params.append(f'**{name}')
            continue
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            params.append(f'*{name}')
            continue
        if p.default is inspect.Parameter.empty:
            params.append(name)
        else:
            params.append(f'{name}={p.default!r}')
    return '(' + ', '.join(params) + ')'


def _method_meta(name: str) -> Tuple[Optional[str], Optional[str], Optional[inspect.Signature]]:
    fn = getattr(Client, name, None)
    if fn is None or not callable(fn):
        return None, None, None
    try:
        full_sig = inspect.signature(fn)
    except (TypeError, ValueError):
        full_sig = None
    doc = inspect.getdoc(fn)
    return _clean_sig(fn), doc, full_sig


def _lambda_body_from_source(raw: str) -> Optional[str]:
    idx = raw.find('lambda')
    if idx < 0:
        return None
    s = raw[idx:]
    depth = 0
    colon = -1
    i = len('lambda')
    while i < len(s):
        ch = s[i]
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ':' and depth == 0:
            colon = i
            break
        i += 1
    if colon < 0:
        return None
    depth = 0
    start = colon + 1
    end = len(s)
    i = start
    while i < len(s):
        ch = s[i]
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            if depth == 0:
                end = i
                break
            depth -= 1
        elif ch == ',' and depth == 0:
            end = i
            break
        i += 1
    return s[start:end].strip().rstrip(',')


def _normalize_call_code(code: str, method_name: str) -> str:
    """Rewrite matrix ``getattr(p, n)(...)`` factories to ``pro.<method>(...)``."""
    code = re.sub(
        r'getattr\(\s*p\s*,\s*[^)]+\)',
        f'pro.{method_name}',
        code,
    )
    return code


def _extract_call_body(call: Callable[..., Any], method_name: str = '') -> Optional[str]:
    try:
        raw = inspect.getsource(call)
    except OSError:
        return None
    body = _lambda_body_from_source(textwrap.dedent(raw))
    if not body:
        return None
    body = re.sub(r'(?<![.\w])p\.', 'pro.', body)
    for const, lit in _CONST_EXPAND.items():
        body = re.sub(rf'(?<![.\w]){const}(?![.\w])', lit, body)
    lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
    if len(lines) > 1:
        indents = [len(ln) - len(ln.lstrip()) for ln in lines[1:]]
        base = min(indents) if indents else 0
        fixed = [lines[0].lstrip()]
        for ln in lines[1:]:
            fixed.append(ln[base:] if len(ln) >= base else ln.lstrip())
        body = '\n'.join(fixed)
    else:
        body = lines[0].lstrip() if lines else body
    if method_name:
        body = _normalize_call_code(body, method_name)
    return body


def _code_kwargs(code: str) -> set:
    return set(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=', code))


def _append_kwargs(code: str, extras: Dict[str, str]) -> Optional[str]:
    """Insert keyword args before the final closing paren of the outermost call."""
    if not extras:
        return code
    # Find last ')' at depth 0 of the whole expression
    depth = 0
    last_close = -1
    for i, ch in enumerate(code):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                last_close = i
    if last_close < 0:
        return None
    head = code[:last_close].rstrip()
    tail = code[last_close:]
    parts = [f'{k}={v}' for k, v in extras.items()]
    if head.endswith('('):
        mid = ', '.join(parts)
    else:
        mid = ', ' + ', '.join(parts)
    return head + mid + tail


def _human_label(entry_name: str, style: str, label: str, code: str) -> str:
    """Explain what this example demonstrates."""
    fallback_labels = {'基本调用', '进阶参数', '参数别名'}
    if label and label not in fallback_labels:
        low = label.lower()
        generic = label in (
            f'{entry_name} conventional',
            f'{entry_name} alias/indirect',
            f'{entry_name} unconventional',
        ) or any(g == low.split()[-1] for g in _GENERIC_LABELS)
        if not generic:
            if label.startswith(entry_name + ' '):
                return label[len(entry_name) + 1:]
            return label

    keys = _code_kwargs(code)
    if 'ks_code' in keys or style == 'alias':
        return '参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）'
    if 'all' in keys:
        return '全市场拉取（`all=True`）'
    if 'raw' in keys:
        return '返回完整 JSON 信封（`raw=True`）'
    if 'as_dataframe' in keys:
        return '返回 list / dict（`as_dataframe=False`）'
    if 'include_valuation' in keys or 'include_depth' in keys:
        return '附带估值 / 盘口字段'
    if 'include_minutes' in keys:
        return '附带分时明细'
    if style == 'direct':
        return '基本调用'
    return '进阶参数组合'


def _bucket(style: str) -> str:
    """Map matrix style → 用法 | 进阶用法. Escape excluded upstream."""
    if style in ('direct', 'alias', 'factory'):
        return '用法'
    return '进阶用法'


def _synth_advanced(
    entry: ApiEntry,
    base_code: str,
    present_keys: set,
    full_sig: Optional[inspect.Signature],
) -> List[Tuple[str, str]]:
    """Synthesize exhaustive 进阶用法 from signature + common opts."""
    out: List[Tuple[str, str]] = []
    seen_codes = {base_code}

    def add(explain: str, code: Optional[str]) -> None:
        if not code or code in seen_codes:
            return
        seen_codes.add(code)
        out.append((explain, code))

    # Common **opts for HTTP-like methods
    if entry.kind in ('http', 'helper', 'text'):
        for key, lit, explain in (
            ('raw', 'True', '返回完整 JSON 信封（`raw=True`）'),
            ('as_dataframe', 'False', '返回 list / dict，不转 DataFrame'),
        ):
            if key in present_keys:
                continue
            add(explain, _append_kwargs(base_code, {key: lit}))

    if full_sig is None:
        return out

    skip = set(present_keys)
    # all=True 全市场调用上不再叠 symbol / ks_code
    if 'all' in present_keys:
        skip |= {'symbol', 'ks_code', 'all'}

    for name, p in full_sig.parameters.items():
        if name in ('self', 'opts') or name in skip:
            continue
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        demo = _PARAM_DEMO.get(name)
        if not demo:
            continue
        lit, explain = demo
        if name == 'ks_code' and 'symbol' in _code_kwargs(base_code):
            # 别名示例：用 ks_code 替换 symbol，避免两者同时出现
            alt = re.sub(
                r"symbol\s*=\s*(?:\[[^\]]*\]|'[^']*'|\"[^\"]*\"|[A-Za-z_][\w.]*)",
                f'ks_code={lit}',
                base_code,
                count=1,
            )
            if alt != base_code:
                add(explain, alt)
                continue
        add(explain, _append_kwargs(base_code, {name: lit}))

    # expand_compact_rows for known compact endpoints
    if entry.name in (
        'realtime_v2', 'auction_v2', 'market_kline_v2', 'convertible_auction_v2',
    ) and 'expand_compact_rows' not in present_keys:
        add(
            '保留紧凑格式原始结构（`expand_compact_rows=False`）',
            _append_kwargs(base_code, {'expand_compact_rows': 'False'}),
        )

    return out


def _collect_examples(entry: ApiEntry) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Return (用法 list, 进阶用法 list) of (explain, code)."""
    usage: List[Tuple[str, str]] = []
    advanced: List[Tuple[str, str]] = []
    present_keys: set = set()
    base_code: Optional[str] = None

    for c in entry.cases:
        if c.style == 'escape':
            continue
        code = _extract_call_body(c.call, entry.name)
        if not code:
            continue
        if code.count('lambda') >= 1:
            continue
        explain = _human_label(entry.name, c.style, c.label, code)
        bucket = _bucket(c.style)
        item = (explain, code)
        if bucket == '用法':
            usage.append(item)
        else:
            advanced.append(item)
        present_keys |= _code_kwargs(code)
        if base_code is None and c.style == 'direct':
            base_code = code

    if base_code is None and usage:
        base_code = usage[0][1]
    if base_code is None and advanced:
        base_code = advanced[0][1]

    _, _, full_sig = _method_meta(entry.name)
    if base_code:
        # Keys already covered by any example
        all_keys = set(present_keys)
        for _, code in usage + advanced:
            all_keys |= _code_kwargs(code)
        for explain, code in _synth_advanced(entry, base_code, all_keys, full_sig):
            advanced.append((explain, code))

    # Deduplicate by code
    def dedupe(items: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        seen = set()
        out = []
        for explain, code in items:
            if code in seen:
                continue
            seen.add(code)
            out.append((explain, code))
        return out

    return dedupe(usage), dedupe(advanced)


def _render_bucket(title: str, items: Sequence[Tuple[str, str]]) -> List[str]:
    if not items:
        return []
    lines = [f'**{title}**', '']
    for explain, code in items:
        lines.append(f'- {explain}')
        lines.append('')
        lines.append('```python')
        lines.append(code)
        lines.append('```')
        lines.append('')
    return lines


def _guide_section() -> List[str]:
    return [
        '# KlineShare SDK — 使用说明',
        '',
        '本文分两部分：**通用说明**，以及**全接口参考**（每个接口列出用法与进阶用法）。',
        '',
        '快速开始见 [README.md](../README.md)；维护者约定见 [DEVELOPMENT.md](DEVELOPMENT.md)（非终端用户文档）。',
        '',
        '---',
        '',
        '## 1. 这是什么',
        '',
        '官方 Python 客户端，调用 [KlineShare](https://klineshare.cn) 数据 API：',
        '实时 / 分时 / K线、涨停与资金流专题、债券与扩展市场、推流 / 行情订阅 / Level2。',
        '',
        '- 方法名贴近 REST 路径（如 `pro.kline` → `GET /v2/kline`）',
        '- 自动鉴权、标的规范化、紧凑格式展开、可选 DataFrame',
        '- 默认在客户端遵守套餐限额（count / 标的数 / RPM）',
        '',
        '---',
        '',
        '## 2. 安装与鉴权',
        '',
        '```bash',
        'pip install klineshare',
        'pip install "klineshare[pandas]"   # 结果转 DataFrame',
        'pip install "klineshare[ws]"       # WebSocket',
        '```',
        '',
        '在用户中心创建 API Key（`tg_...`），任选一种方式：',
        '',
        '```python',
        'import klineshare as ks',
        '',
        '# 方式 A：代码里设置 Key，再创建客户端',
        'ks.set_api_key("tg_your_key")',
        'pro = ks.pro_api()',
        '',
        '# 方式 B：事先 export KLINESHARE_API_KEY=tg_...（可选 KLINESHARE_BASE_URL）',
        '# 此时不用 set_api_key，pro_api() 会自动读环境变量',
        'pro = ks.pro_api()',
        '',
        '# 方式 C：构造时显式传入',
        'pro = ks.Client(api_key="tg_xxx", base_url="https://data.klineshare.cn")',
        '```',
        '',
        '查看当前 Key 权限与限额：',
        '',
        '```python',
        'print(pro.me())',
        'pro.refresh_limits()',
        'print(pro.limits.summary())',
        '```',
        '',
        '---',
        '',
        '## 3. 标的代码',
        '',
        '标准后缀：`600519.SS` / `000001.SZ` / `920000.BJ` / `AAPL.US`。',
        '',
        '| 输入 | 发出请求时 |',
        '|------|------------|',
        '| `600519.SH` | `600519.SS` |',
        '| `sh600519` | `600519.SS` |',
        '| `600519` | `600519.SS`（按首位推断） |',
        '| `ks_code=` | 与 `symbol=` 相同规则 |',
        '',
        '按资产选择对应方法：个股 `kline`，指数 `index_kline`，ETF `etf_kline`，'
        '北交所 `bj_kline`，可转债 `convertible_kline` 等。',
        '',
        '贵金属 / 期货 / 全球指数与债券一般不加 `.US` 后缀。',
        '',
        '---',
        '',
        '## 4. 返回值与通用参数',
        '',
        '几乎所有 HTTP 方法都接受 `**opts`：',
        '',
        '| 参数 | 含义 |',
        '|------|------|',
        '| `raw=True` | 返回完整 JSON 信封，不解包 `data` |',
        '| `as_dataframe=False` | 返回 list / dict，不转 DataFrame |',
        '| `expand_compact_rows=False` | 关闭 v2 紧凑格式自动展开 |',
        '| `auth=False` | 不带 Key（公开接口） |',
        '| `skip_limits=True` | 跳过客户端限额预检 |',
        '',
        '默认：解包接口里的 `data`；列表尽量转成 pandas DataFrame'
        '（需安装 `pandas` 或 `klineshare[pandas]`）。',
        '',
        '```python',
        'df = pro.kline(symbol="600519.SS", period=86400, count=10)',
        'rows = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)',
        'envelope = pro.kline(symbol="600519.SS", period=86400, count=10, raw=True)',
        '```',
        '',
        '`realtime_v2` / `auction_v2` / `market_kline_v2` 等紧凑格式接口默认展开为行；'
        '全市场写法见 §8。',
        '',
        '---',
        '',
        '## 5. K 线用法',
        '',
        '个股 / 指数 / ETF K 线走 v2 路径：`kline` / `index_kline` / `etf_kline`。',
        '',
        '```python',
        'bars = pro.kline(',
        '    symbol="600519.SH",          # 自动规范为 .SS',
        '    period=86400,                # 秒；日线=86400',
        '    adjust_type="forward",',
        '    count=100,',
        ')',
        '```',
        '',
        '要点：',
        '',
        '1. **`format`**：默认 `"raw"`（服务端极限体积分隔串；SDK 仍展开为行 / DataFrame）。'
        '传 `format=None` 使用服务端列式数组。与 `raw=True`（完整 JSON 信封）无关。',
        '2. **翻页**：请求参数 `timestamp` 为秒；条内字段 `timestamp` 是毫秒。'
        '传入毫秒时 SDK 会自动换成秒。',
        '3. **`iter_kline`**：自动向更早翻页，逐页 yield。',
        '4. **`batch`**：`multi`（默认）/ `single` / `auto`'
        '（日线及以上且标的数×count 过大时按标的拆分，默认阈值 3000）。',
        '',
        '```python',
        'bars = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)',
        'older = pro.kline(',
        '    symbol="600519.SS",',
        '    period=86400,',
        '    count=10,',
        '    timestamp=min(b["timestamp"] for b in bars) - 1,',
        ')',
        'for page in pro.iter_kline(symbol="600519.SS", period=86400, count=10, max_pages=5):',
        '    print(len(page))',
        '```',
        '',
        '---',
        '',
        '## 6. 限额与错误',
        '',
        '默认 `limits="enforce"`：按 `GET /v1/me` 缓存套餐上限，发请求前裁切 `count`、'
        '校验标的数 / 试用额度，并做本地 RPM 门闩。',
        '',
        '| 模式 | 行为 |',
        '|------|------|',
        '| `enforce`（默认） | 超额本地报错 / 裁切 |',
        '| `advise` | 裁切并写入 `pro.limit_advice`，仍尽量请求 |',
        '| `off` | 关闭客户端限额 |',
        '',
        '```python',
        'pro = ks.pro_api(limits="enforce", on_rate_limit="wait", kline_batch="auto")',
        '```',
        '',
        '| 异常 | 含义 |',
        '|------|------|',
        '| `KlineShareAuthError` | Key 缺失 / 无效 / 权限不足 |',
        '| `KlineShareRateLimitError` | HTTP 429 或本地 RPM 门闩 |',
        '| `KlineShareQuotaError` | 客户端量预检失败（未发请求） |',
        '| `KlineShareError` | 其他 API / 客户端错误 |',
        '',
        '---',
        '',
        '## 7. 实时流：推流 / 行情订阅 / Level2',
        '',
        '**服务端推流**',
        '',
        '```python',
        'for ev in pro.abnormal_events_stream():',
        '    print(ev)',
        '    break',
        '```',
        '',
        '**行情订阅**（需 `klineshare[ws]`）',
        '',
        '```python',
        'with pro.realtime_ws(symbol="600519.SS") as feed:',
        '    for msg in feed:',
        '        if msg.get("type") == "tick":',
        '            print(msg)',
        '            break',
        '```',
        '',
        '**Level2**',
        '',
        '```python',
        'with pro.level2(symbol="600519.SS", channels="depth,trades,entrust") as feed:',
        '    for msg in feed:',
        '        print(msg)',
        '        break',
        '```',
        '',
        '---',
        '',
        '## 8. 全市场紧凑格式（realtime_v2 / auction_v2 / market_kline_v2 等）',
        '',
        '下列接口支持一次拉取全市场紧凑快照：',
        '',
        '| 方法 | 路径 | 用法 |',
        '|------|------|------|',
        '| `realtime_v2` | `/v2/realtime` | `all=True, market="SS"` |',
        '| `auction_v2` | `/v2/auction` | `all=True`，可加 `market` / `include_minutes` |',
        '| `market_kline_v2` | `/v2/market-kline` | 仅 `all=True`；可加 `market` / `period=60` / `count` |',
        '| `convertible_auction_v2` | `/v2/convertible/auction` | `all=True` |',
        '| `moneyflow_live` | `/v1/moneyflow/live` | `all=True` 或批量 `symbol` |',
        '',
        '对照：',
        '',
        '| 场景 | 方法 |',
        '|------|------|',
        '| 个股实时 / 竞价分时 | `realtime` / `auction` |',
        '| 全市场快照 | `realtime_v2` / `auction_v2` |',
        '| 全市场近端分钟 K | `market_kline_v2` |',
        '',
        '`all=True` 时服务端返回紧凑格式；SDK 默认展开为行 / DataFrame。'
        '需要原始结构时传 `expand_compact_rows=False`。',
        '',
        '```python',
        '# 用法：全市场',
        'df = pro.realtime_v2(all=True, market="SS")',
        'df = pro.realtime_v2(',
        '    all=True, market="SZ",',
        '    include_valuation=True, include_depth=True,',
        ')',
        'auc = pro.auction_v2(all=True, market="SS")',
        'auc_m = pro.auction_v2(all=True, include_minutes=True)',
        'mk = pro.market_kline_v2(all=True, market="SS", period=60, count=2)',
        'mf = pro.moneyflow_live(all=True)',
        'cb = pro.convertible_auction_v2(all=True)',
        '```',
        '',
        '```python',
        '# 进阶用法：按标的过滤',
        'pro.realtime_v2(symbol="600519.SS")',
        'pro.realtime_v2(symbol=["600519.SS", "000001.SZ"])',
        'pro.auction_v2(symbol="600519.SS")',
        '```',
        '',
        '全市场包较大，对应独立 scope（如 `realtime_v2` / `auction_v2` / `market_kline_v2`），'
        '权限见 `pro.me()`。实时个股资金流全市场见 `moneyflow_live(all=True)`。',
        '',
        '---',
        '',
        '## 9. 专题提示',
        '',
        '- **资金流板块榜** `moneyflow_ranking_boards` 需传 `category`'
        '（如 `industry` / `concept` / `csrc_industry`），可先查 `moneyflow_ranking_catalog()`。',
        '- 龙虎榜 / 游资 / 涨停等方法名与路径一致，见下方「全接口参考」。',
        '',
        '---',
        '',
        '## 10. 通用请求',
        '',
        '```python',
        'pro.get("/v1/health")',
        'pro.get("/v2/kline", params={"symbol": "600519.SS", "period": 86400, "count": 5})',
        'pro.request_text("/public/v1/docs.md")',
        'for ev in pro.stream("/v1/abnormal-events/stream"):',
        '    ...',
        '```',
        '',
        '---',
        '',
        '## 11. 工厂与模块级 API',
        '',
        '```python',
        'import klineshare as ks',
        '',
        'ks.set_api_key("tg_...")',
        'pro = ks.pro_api()                    # 或 Client(...)',
        'ks.normalize_symbol("600519.SH")     # → 600519.SS',
        '```',
        '',
        '---',
        '',
        '## 全接口参考',
        '',
        '每个接口分两档，尽量穷尽可调用方式：',
        '',
        '| 档位 | 含义 |',
        '|------|------|',
        '| **用法** | 基本调用与常用参数别名（如 `symbol` / `ks_code`、`all=True`） |',
        '| **进阶用法** | 附加字段、返回形态（`raw` / DataFrame）、翻页、批量、紧凑格式展开等 |',
        '',
        '每个接口另附 **数据样例** 与 **字段说明**；列表与嵌套对象优先用表格展示。',
        '',
        '通用 `**opts`：`raw` / `as_dataframe` / `expand_compact_rows` / `auth` / `skip_limits`。',
        '',
    ]


def _render_sample(e: ApiEntry, live: Optional[LiveSample]) -> List[str]:
    stub = doc_sample_stub(e.name)
    if stub:
        lines = [
            '**数据样例**',
            '',
            stub,
            '',
        ]
        return lines

    if live is None or not live.ok or live.data is None:
        detail = (live.detail if live else '无样例')
        lines = [
            '**数据样例**',
            '',
            f'暂无可用样例：{detail}',
            '',
        ]
        return lines

    lines: List[str] = [
        '**数据样例**',
        '',
    ]
    lines.extend(render_data_table(live.data))
    lines.append('')
    # 始终按当前 data 推断字段（含 data.* 嵌套），不沿用旧缓存 fields
    fields = _fields_of(live.data) or live.fields or ()
    lines.extend(render_field_table(fields, live.data))
    return lines


def _render_entry(e: ApiEntry, samples: Dict[str, LiveSample]) -> List[str]:
    lines: List[str] = [
        f'### `{e.name}`',
        '',
        f'- **路径：** `{e.path}`',
        f'- **类型：** {e.kind}',
        f'- **说明：** {e.summary}',
    ]
    sig, doc, _ = _method_meta(e.name)
    if sig:
        lines.append(f'- **签名：** `pro.{e.name}{sig}`')
    if doc:
        first = doc.strip().split('\n\n')[0].strip().replace('\n', ' ')
        first = first.replace('``', '`')
        lines.append(f'- **介绍：** {first}')
    lines.append('')

    usage, advanced = _collect_examples(e)
    if usage or advanced:
        lines.extend(_render_bucket('用法', usage))
        lines.extend(_render_bucket('进阶用法', advanced))
    else:
        lines.append('**用法**')
        lines.append('')
        lines.append('```python')
        lines.append(f'pro.{e.name}(...)')
        lines.append('```')
        lines.append('')

    lines.extend(_render_sample(e, samples.get(e.name)))
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Generate docs/API_USAGE.md')
    parser.add_argument(
        '--offline', action='store_true',
        help='不请求线上，仅用 docs/_api_samples_cache.json 缓存样例',
    )
    parser.add_argument(
        '--strict', action='store_true',
        help='非可选接口样例失败则退出码非 0',
    )
    parser.add_argument(
        '--include-stream', action='store_true',
        help='同时拉取推流/订阅类接口（默认跳过）',
    )
    parser.add_argument(
        '--group', default='all',
        help='只生成某一矩阵分组（调试用）',
    )
    args = parser.parse_args(argv)

    matrix = build_matrix()
    if args.group != 'all':
        matrix = [e for e in matrix if e.group == args.group]

    samples: Dict[str, LiveSample] = {}
    if args.offline:
        samples = load_cache(CACHE_PATH)
        print(f'offline: loaded {len(samples)} cached samples from {CACHE_PATH}')
    else:
        print('live: fetching samples…')
        try:
            pro = build_client(ROOT)
        except Exception as exc:  # noqa: BLE001
            print(f'无法创建客户端：{exc}')
            print('提示：可先配置 KLINESHARE_API_KEY，或改用 --offline')
            return 2
        report = fetch_samples(pro, matrix, include_stream=args.include_stream)
        samples = report.samples
        save_cache(CACHE_PATH, report)
        for line in report.summary_lines():
            print(line)
        print(f'cache written: {CACHE_PATH}')
        if args.strict and report.failed:
            print(f'strict: {report.failed} required sample(s) failed')
            # still write doc below? User wants check - fail after write is ok
            # We'll write doc then return 1

    by_group: Dict[str, List[ApiEntry]] = defaultdict(list)
    for e in matrix:
        by_group[e.group].append(e)

    n_usage = n_adv = 0
    for e in matrix:
        u, a = _collect_examples(e)
        n_usage += len(u)
        n_adv += len(a)

    live_ok = sum(1 for s in samples.values() if s.ok and s.verified)

    lines = _guide_section()
    lines.append(
        f'**统计：** {len(matrix)} 个接口；用法示例 {n_usage} 段；进阶用法示例 {n_adv} 段；'
        f'数据样例 {live_ok} 个。'
    )
    lines.append('')

    for group in GROUP_ORDER:
        entries = by_group.get(group) or []
        if not entries:
            continue
        lines.append(f'## {GROUP_TITLE.get(group, group)}')
        lines.append('')
        for e in entries:
            lines.extend(_render_entry(e, samples))

    out = ROOT / 'docs' / 'API_USAGE.md'
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'wrote {out} ({len(matrix)} entries; usage={n_usage} advanced={n_adv}; samples={live_ok})')

    if not args.offline and args.strict:
        failed = sum(1 for s in samples.values() if not s.optional and (not s.ok or not s.verified))
        return 1 if failed else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())