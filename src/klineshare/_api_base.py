"""Helpers for following server-assigned ``api_base`` (home-node entry)."""

from __future__ import annotations

import re
from typing import Any, Optional

_API_BASE_IN_MSG = re.compile(r'api_base=(https?://[^\s\'"，,;]+)')


def extract_api_base(payload: Any) -> Optional[str]:
    """Pull assigned request root from ``/v1/me`` or auth error body.

    HTTP errors expose ``api_base`` as a field; WS errors embed
    ``api_base=https://...`` inside ``message``.
    """
    if isinstance(payload, str):
        m = _API_BASE_IN_MSG.search(payload)
        if m:
            return m.group(1).rstrip('/').rstrip('。').rstrip('.')
        return None
    if not isinstance(payload, dict):
        return None
    for candidate in (payload, payload.get('data') if isinstance(payload.get('data'), dict) else None):
        if not isinstance(candidate, dict):
            continue
        raw = candidate.get('api_base')
        if isinstance(raw, str):
            text = raw.strip().rstrip('/')
            if text:
                return text
    msg = payload.get('message')
    if isinstance(msg, str):
        return extract_api_base(msg)
    return None


def is_forbidden(resp_status: int, body: Any) -> bool:
    if resp_status == 403:
        return True
    return isinstance(body, dict) and body.get('code') == 403


def is_wrong_entry_hint(body: Any, *, hinted_base: Optional[str], current_base: str) -> bool:
    """True when server signals the client is on the wrong home-node entry.

    Upstream shape (``check_account_home_node``)::

        {"success": false, "code": 403,
         "message": "当前入口不可用，请改用分配地址请求：https://...",
         "api_base": "https://..."}

    WS embeds ``api_base=`` inside ``message``. Scope-denied 403s omit ``api_base``.
    """
    if not hinted_base:
        return False
    return hinted_base.rstrip('/') != (current_base or '').rstrip('/')
