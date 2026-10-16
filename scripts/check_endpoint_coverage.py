#!/usr/bin/env python3
"""Compare SDK wrapped paths against public catalog ``scope_rows``.

Usage::

    python scripts/check_endpoint_coverage.py
    python scripts/check_endpoint_coverage.py --fail-under 50
    python scripts/check_endpoint_coverage.py --check-gzip

Exit code 1 if coverage percent is below ``--fail-under`` (when > 0).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.request import Request, urlopen

CATALOG_URL = "https://data.klineshare.cn/public/v1/catalog"
DEFAULT_BASE = "https://data.klineshare.cn"

# Endpoints intentionally not wrapped (deprecated / out of SDK scope).
EXCLUDED_PATHS = frozenset({
    '/v2/moneyflow',
    '/v2/moneyflow/em',
    '/public/v1/moneyflow/ranking/em/catalog',
    '/v1/moneyflow/ranking/em/stocks',
    '/v1/moneyflow/ranking/em/snapshot',
})
SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "klineshare"
ENDPOINTS_ROOT = SRC_ROOT / "endpoints"
PATH_LIT = re.compile(r"""['"](/[vV][12]/[^'"]+)['"]""")
PATH_FSTR = re.compile(r"""f['"](/[vV][12]/[^'"]+)['"]""")


def _fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "klineshare-sdk-coverage/0.1"})
    with urlopen(req, timeout=30) as resp:  # noqa: S310 — fixed public URL
        import json

        return json.load(resp)


def catalog_paths(payload: dict) -> List[Tuple[str, str, str]]:
    """Return list of (path, scope, name) from scope_rows."""
    data = payload.get("data", payload)
    rows = data.get("scope_rows") or []
    out: List[Tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        if not path or not isinstance(path, str):
            continue
        # strip query examples like /v1/realtime?include_valuation=true
        path = path.split("?", 1)[0]
        out.append((path, str(row.get("scope") or ""), str(row.get("name") or "")))
    return out


def _normalize_template(path: str) -> str:
    """Turn f-string templates into prefix markers: /v1/catalog/nodes/{node}."""
    # already may contain {var}
    return path


def sdk_paths() -> Set[str]:
    """Collect API paths from ``endpoints/`` only (not limits policy tables)."""
    found: Set[str] = set()
    roots = [ENDPOINTS_ROOT]
    # also scan client.py for stream/get escape docs? skip — endpoints only
    for root in roots:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            for m in PATH_LIT.finditer(text):
                found.add(m.group(1).split("?", 1)[0])
            for m in PATH_FSTR.finditer(text):
                found.add(_normalize_template(m.group(1).split("?", 1)[0]))
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value
                    if val.startswith(("/v1/", "/v2/", "/public/v1/")):
                        found.add(val.split("?", 1)[0])
    return found


def path_covered(catalog_path: str, sdk: Set[str]) -> bool:
    """Exact match, or SDK has a templated/prefix equivalent."""
    if catalog_path in sdk:
        return True
    # catalog may list representative path; SDK may have siblings under same prefix
    for sp in sdk:
        # template: /v1/catalog/nodes/{node} covers /v1/catalog/nodes/foo conceptually
        if "{" in sp:
            prefix = sp.split("{", 1)[0]
            if catalog_path.startswith(prefix):
                return True
        if catalog_path.startswith(sp.rstrip("/") + "/") or sp.startswith(
            catalog_path.rstrip("/") + "/"
        ):
            # e.g. catalog /v1/limit-up vs SDK /v1/limit-up/ladder
            # Only count if catalog path is a prefix of an SDK path (SDK more specific OK)
            if sp.startswith(catalog_path.rstrip("/") + "/") or sp == catalog_path:
                return True
    # reverse: catalog /v1/lhb/daily, SDK has /v1/lhb/daily
    for sp in sdk:
        if catalog_path.rstrip("/") == sp.rstrip("/"):
            return True
    return catalog_path in sdk


def check_gzip(base: str) -> None:
    """Probe whether large public docs response is compressed."""
    url = f"{base.rstrip('/')}/public/v1/docs.md"
    req = Request(
        url,
        headers={
            "User-Agent": "klineshare-sdk-coverage/0.1",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        encoding = resp.headers.get("Content-Encoding")
        length = resp.headers.get("Content-Length")
        # urlopen may auto-decompress; still report header if present
        print(f"gzip probe: GET {url}")
        print(f"  Content-Encoding: {encoding or '(none)'}")
        print(f"  Content-Length: {length or '(unknown)'}")
        if not encoding:
            print(
                "  note: server/CDN did not advertise compression; "
                "client already sends Accept-Encoding (see DEVELOPMENT.md §5)."
            )
        else:
            print(f"  ok: response compressed via {encoding}")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-url",
        default=CATALOG_URL,
        help="Public catalog JSON URL",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        help="Exit 1 if coverage %% is below this (0 disables)",
    )
    parser.add_argument(
        "--check-gzip",
        action="store_true",
        help="Also probe Content-Encoding on public docs",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE,
        help="API base for gzip probe",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    print(f"Fetching catalog: {args.catalog_url}")
    payload = _fetch_json(args.catalog_url)
    rows = catalog_paths(payload)
    # unique by path
    by_path: Dict[str, Tuple[str, str]] = {}
    for path, scope, name in rows:
        by_path.setdefault(path, (scope, name))

    sdk = sdk_paths()
    # ignore pure public metadata noise from comparison denominator? keep all scope_rows
    missing: List[Tuple[str, str, str]] = []
    excluded: List[Tuple[str, str, str]] = []
    covered_n = 0
    for path, (scope, name) in sorted(by_path.items()):
        if path in EXCLUDED_PATHS:
            excluded.append((path, scope, name))
            continue
        if path_covered(path, sdk):
            covered_n += 1
        else:
            missing.append((path, scope, name))

    total = len(by_path) - len(excluded)
    pct = (100.0 * covered_n / total) if total else 100.0
    print(f"SDK literal/f-string paths found: {len(sdk)}")
    print(f"Catalog scope_rows paths: {len(by_path)} (excluded {len(excluded)})")
    print(f"Covered: {covered_n}/{total} ({pct:.1f}%)")
    if excluded:
        print(f"\nExcluded (intentionally not in SDK): {len(excluded)}")
        for path, scope, name in excluded:
            print(f"  {path:40s}  scope={scope:24s}  {name}")

    if missing:
        print("\nMissing (not wrapped or not matched):")
        for path, scope, name in missing[:80]:
            print(f"  {path:40s}  scope={scope:24s}  {name}")
        if len(missing) > 80:
            print(f"  ... and {len(missing) - 80} more")

    if args.check_gzip:
        print()
        check_gzip(args.base_url)

    if args.fail_under > 0 and pct < args.fail_under:
        print(f"\nFAIL: coverage {pct:.1f}% < --fail-under {args.fail_under}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
