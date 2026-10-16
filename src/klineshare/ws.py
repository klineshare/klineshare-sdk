"""WebSocket feed helpers (optional extra: ``pip install klineshare[ws]``)."""

from __future__ import annotations

import json
import threading
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Union
from urllib.parse import urlencode

from klineshare.errors import KlineShareAuthError, KlineShareError
from klineshare.symbols import normalize_symbol, normalize_symbols


def _require_websocket():
    try:
        import websocket  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            'WebSocket 支持需要安装可选依赖：pip install "klineshare[ws]" '
            '（或 pip install websocket-client）'
        ) from exc
    return websocket


def http_to_ws_base(base_url: str) -> str:
    base = (base_url or '').rstrip('/')
    if base.startswith('https://'):
        return 'wss://' + base[len('https://') :]
    if base.startswith('http://'):
        return 'ws://' + base[len('http://') :]
    if base.startswith('wss://') or base.startswith('ws://'):
        return base
    return 'wss://' + base.lstrip('/')


def build_ws_url(
    base_url: str,
    path: str,
    *,
    api_key: str = '',
    query: Optional[Dict[str, Any]] = None,
) -> str:
    root = http_to_ws_base(base_url)
    path = path if path.startswith('/') else '/' + path
    q = dict(query or {})
    if api_key and 'api_key' not in q:
        q['api_key'] = api_key
    # drop None
    q = {k: v for k, v in q.items() if v is not None and v != ''}
    qs = urlencode(q, doseq=True) if q else ''
    return f'{root}{path}' + (f'?{qs}' if qs else '')


def _as_symbol_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = normalize_symbols(raw) if (',' in raw or ';' in raw) else normalize_symbol(raw)
        if isinstance(text, str) and (',' in text):
            return [p for p in text.split(',') if p]
        return [text] if text else []
    if isinstance(raw, (list, tuple)):
        out: List[str] = []
        for item in raw:
            out.extend(_as_symbol_list(item))
        return out
    return [normalize_symbol(str(raw))]


class WebSocketFeed:
    """
    Thin sync WebSocket client for KlineShare stream endpoints.

    Usage::

        with pro.realtime_ws(symbol="600519.SS") as feed:
            for msg in feed:
                print(msg)
                if msg.get("type") == "tick":
                    break
    """

    def __init__(
        self,
        url: str,
        *,
        api_key: str = '',
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        auto_pong: bool = True,
        on_wrong_entry: Optional[Callable[[str, Dict[str, Any]], Optional[str]]] = None,
    ) -> None:
        self.url = url
        self.api_key = (api_key or '').strip()
        self.timeout = timeout
        self.auto_pong = auto_pong
        self._on_wrong_entry = on_wrong_entry
        self._headers = dict(headers or {})
        if self.api_key and 'X-API-Key' not in self._headers:
            self._headers['X-API-Key'] = self.api_key
        self._ws: Any = None
        self._closed = False
        self._lock = threading.Lock()
        self._pending: Optional[Dict[str, Any]] = None
        self._entry_retried = False

    def connect(self) -> 'WebSocketFeed':
        websocket = _require_websocket()
        header_list = [f'{k}: {v}' for k, v in self._headers.items()]
        try:
            self._ws = websocket.create_connection(
                self.url,
                header=header_list or None,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise KlineShareError(f'WebSocket 连接失败: {exc}', code=0) from exc
        self._closed = False
        self._peek_auth_error()
        return self

    def _peek_auth_error(self) -> None:
        """If the server immediately sends a wrong-node / auth error, handle it.

        Upstream WS auth failures arrive as a JSON frame then close(1008)::

            {"success": false, "type": "error", "code": 403,
             "message": "当前入口不可用… api_base=https://..."}
        """
        ws = self._ws
        if ws is None:
            return
        from klineshare._api_base import extract_api_base

        prev_timeout = None
        try:
            prev_timeout = ws.gettimeout()
        except Exception:
            prev_timeout = None
        peek_timeout = 2.0
        if self.timeout is not None:
            try:
                peek_timeout = min(2.0, float(self.timeout))
            except (TypeError, ValueError):
                peek_timeout = 2.0
        try:
            ws.settimeout(max(0.2, peek_timeout))
            data = ws.recv()
        except Exception:
            # no immediate frame (or timeout) — treat as normal stream
            try:
                if prev_timeout is not None:
                    ws.settimeout(prev_timeout)
                elif self.timeout is not None:
                    ws.settimeout(self.timeout)
            except Exception:
                pass
            return
        try:
            if prev_timeout is not None:
                ws.settimeout(prev_timeout)
            elif self.timeout is not None:
                ws.settimeout(self.timeout)
        except Exception:
            pass

        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='replace')
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            self._pending = {'type': 'text', 'data': data}
            return
        if not isinstance(msg, dict):
            self._pending = {'type': 'text', 'data': data}
            return

        code = msg.get('code')
        is_err = (
            msg.get('type') == 'error'
            or msg.get('success') is False
        ) and code in (401, 403)
        if not is_err:
            self._pending = msg
            return

        hinted = extract_api_base(msg)
        if (
            not self._entry_retried
            and code == 403
            and hinted
            and self._on_wrong_entry is not None
        ):
            new_url = self._on_wrong_entry(hinted, msg)
            if new_url and new_url != self.url:
                self._entry_retried = True
                self.close()
                self.url = new_url
                self.connect()
                return

        self.close()
        raise KlineShareAuthError(
            str(msg.get('message') or 'unauthorized'),
            code=int(code) if code is not None else 403,
            http_status=int(code) if code is not None else 403,
            body=msg,
            api_base=hinted,
        )

    def close(self) -> None:
        with self._lock:
            self._closed = True
            ws = self._ws
            self._ws = None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def __enter__(self) -> 'WebSocketFeed':
        return self.connect()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def send_json(self, payload: Dict[str, Any]) -> None:
        if self._ws is None:
            raise KlineShareError('WebSocket 未连接', code=0)
        self._ws.send(json.dumps(payload, ensure_ascii=False))

    def sub(
        self,
        symbols: Optional[Union[str, Iterable[str]]] = None,
        *,
        channels: Optional[Sequence[str]] = None,
        snapshot: Optional[bool] = None,
        **extra: Any,
    ) -> None:
        """Send ``{"op":"sub", ...}`` control frame."""
        body: Dict[str, Any] = {'op': 'sub', **extra}
        syms = _as_symbol_list(symbols)
        if syms:
            body['symbols'] = syms
        if channels is not None:
            body['channels'] = list(channels)
        if snapshot is not None:
            body['snapshot'] = bool(snapshot)
        self.send_json(body)

    def unsub(
        self,
        symbols: Optional[Union[str, Iterable[str]]] = None,
        *,
        channels: Optional[Sequence[str]] = None,
        **extra: Any,
    ) -> None:
        body: Dict[str, Any] = {'op': 'unsub', **extra}
        syms = _as_symbol_list(symbols)
        if syms:
            body['symbols'] = syms
        if channels is not None:
            body['channels'] = list(channels)
        self.send_json(body)

    def ping(self) -> None:
        self.send_json({'op': 'ping'})

    def recv(self, *, raw: bool = False) -> Any:
        """Receive one message; parse JSON unless ``raw=True``."""
        if self._pending is not None:
            msg = self._pending
            self._pending = None
            if raw:
                return json.dumps(msg, ensure_ascii=False)
            if self.auto_pong and isinstance(msg, dict) and msg.get('type') == 'ping':
                try:
                    self.ping()
                except Exception:
                    pass
            return msg
        if self._ws is None:
            raise KlineShareError('WebSocket 未连接', code=0)
        try:
            data = self._ws.recv()
        except Exception as exc:
            if self._closed:
                raise
            raise KlineShareError(f'WebSocket 接收失败: {exc}', code=0) from exc
        if raw:
            return data
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='replace')
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            return {'type': 'text', 'data': data}
        if self.auto_pong and isinstance(msg, dict) and msg.get('type') == 'ping':
            try:
                self.ping()
            except Exception:
                pass
        return msg

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        while not self._closed:
            msg = self.recv()
            if isinstance(msg, dict):
                yield msg
            else:
                yield {'type': 'text', 'data': msg}


def _count_symbols(symbol: Any) -> int:
    return len(_as_symbol_list(symbol))
