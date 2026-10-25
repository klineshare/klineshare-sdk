#!/usr/bin/env python3
"""Live smoke driven by ``tests/api_matrix.py`` (requires API Key).

Usage::

    python scripts/live_smoke.py                 # full matrix (HTTP direct cases)
    python scripts/live_smoke.py --quick         # meta + market + index_etf only
    python scripts/live_smoke.py --group topics
    python scripts/live_smoke.py --ws --sse --level2
    python scripts/live_smoke.py --strict-optional

Env: ``KLINESHARE_API_KEY`` / ``L2_API_KEY``, optional ``KLINESHARE_BASE_URL`` / ``L2_API_BASE``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))


def _load_dotenv() -> None:
    for path in (ROOT / '.env',):
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            k, v = k.strip(), v.strip().strip("'").strip('"')
            if k and k not in os.environ:
                os.environ[k] = v


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ''
    optional: bool = False
    elapsed: float = 0.0


@dataclass
class Report:
    results: List[Result] = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)
        flag = 'OK ' if r.ok else 'FAIL'
        opt = ' (optional)' if r.optional else ''
        print(f'[{flag}]{opt} {r.name} ({r.elapsed:.2f}s) {r.detail}'[:220])


def _redact_url(url: str) -> str:
    return re.sub(r'(api_key=)[^&]+', r'\1***', url, flags=re.I)


def _brief(out: Any) -> str:
    try:
        import pandas as pd

        if isinstance(out, pd.DataFrame):
            return f'DataFrame shape={out.shape}'
    except ImportError:
        pass
    if isinstance(out, list):
        return f'list len={len(out)}'
    if isinstance(out, dict):
        return f'dict keys={list(out.keys())[:8]}'
    if isinstance(out, str):
        text = _redact_url(out) if 'api_key=' in out.lower() else out
        if len(text) > 60:
            return f'str len={len(out)} head={text[:40]!r}'
        return text
    return type(out).__name__


def build_client():
    from klineshare import Client

    key = (os.getenv('KLINESHARE_API_KEY') or os.getenv('L2_API_KEY') or '').strip()
    if not key:
        raise SystemExit('缺少 API Key：设置 KLINESHARE_API_KEY 或 L2_API_KEY')
    base = (os.getenv('KLINESHARE_BASE_URL') or os.getenv('L2_API_BASE') or '').strip()
    kwargs: dict = dict(
        api_key=key, as_dataframe=False, limits='enforce', on_rate_limit='wait',
    )
    if base:
        kwargs['base_url'] = base
    return Client(**kwargs)


def smoke_matrix(
    pro,
    report: Report,
    *,
    group: str,
    include_ws: bool,
    include_sse: bool,
    include_l2: bool,
) -> None:
    from api_matrix import live_cases

    for entry, case in live_cases():
        if group != 'all' and entry.group != group:
            continue
        if entry.kind == 'sse' and not include_sse:
            continue
        if entry.kind == 'local' and not include_l2:
            continue
        if entry.kind == 'ws':
            if entry.name.endswith('_ws_url'):
                pass  # always run URL builders
            elif not include_ws:
                continue

        optional = bool(case.optional_live) or entry.kind in ('sse', 'local')
        if entry.kind == 'ws' and not entry.name.endswith('_ws_url'):
            optional = True

        name = f'{entry.group}/{entry.name}'
        t0 = time.time()
        try:
            out = case.call(pro)
            report.add(
                Result(name, True, _brief(out), optional=optional, elapsed=time.time() - t0)
            )
        except Exception as exc:  # noqa: BLE001
            msg = f'{type(exc).__name__}: {exc}'
            soft = optional or any(
                x in msg
                for x in ('403', '401', '503', '权限', 'Quota', '不是已收录', '不支持', '暂不可用')
            )
            report.add(
                Result(name, False, msg, optional=soft, elapsed=time.time() - t0)
            )


def main() -> int:
    parser = argparse.ArgumentParser(description='KlineShare SDK live smoke')
    parser.add_argument(
        '--group',
        default='all',
        help='all|meta|market|index_etf|topics|catalog|bond|extended|ws|core',
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Only meta + market + index_etf + core',
    )
    parser.add_argument('--ws', action='store_true', help='Include WS connect')
    parser.add_argument('--sse', action='store_true', help='Include SSE')
    parser.add_argument('--level2', action='store_true', help='Include Level2')
    parser.add_argument('--strict-optional', action='store_true')
    args = parser.parse_args()

    _load_dotenv()
    report = Report()
    try:
        pro = build_client()
    except SystemExit as e:
        print(e)
        return 2

    print(f'base_url={pro.base_url} limits={pro.limits_mode}')
    if args.quick:
        for g in ('meta', 'market', 'index_etf', 'core'):
            smoke_matrix(
                pro, report, group=g,
                include_ws=args.ws, include_sse=args.sse, include_l2=args.level2,
            )
    else:
        smoke_matrix(
            pro, report, group=args.group,
            include_ws=args.ws, include_sse=args.sse, include_l2=args.level2,
        )

    try:
        pro.close()
    except Exception:
        pass

    req = [r for r in report.results if not r.ok and not r.optional]
    opt = [r for r in report.results if not r.ok and r.optional]
    ok_n = sum(1 for r in report.results if r.ok)
    print(
        f'\nSummary: {ok_n}/{len(report.results)} ok; '
        f'required_fail={len(req)}; optional_fail={len(opt)}'
    )
    for r in req:
        print(f'  - {r.name}: {r.detail}'[:200])
    if args.strict_optional:
        for r in opt:
            print(f'  - [opt] {r.name}: {r.detail}'[:200])

    if req:
        return 1
    if args.strict_optional and opt:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
