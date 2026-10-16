"""KlineShare API client."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterator, List, Optional, Union

import requests
from requests.adapters import HTTPAdapter

from klineshare._api_base import (
    extract_api_base as _extract_api_base,
    is_forbidden as _is_forbidden,
    is_wrong_entry_hint as _is_wrong_entry_hint,
)
from klineshare._result import maybe_frame
from klineshare._sse import iter_sse_from_response
from klineshare.compact import (
    expand_compact,
    expand_kline_matrix,
    expand_kline_raw,
    is_compact_payload,
    is_kline_matrix_payload,
    is_kline_raw_payload,
)
from klineshare.errors import (
    KlineShareAuthError,
    KlineShareError,
    KlineShareRateLimitError,
)
from klineshare.endpoints import (
    CatalogBondEndpoints,
    ExtendedEndpoints,
    IndexEtfEndpoints,
    MarketEndpoints,
    MetaEndpoints,
    TopicsEndpoints,
    WsEndpoints,
)
from klineshare.limits.quota import DEFAULT_KLINE_HEAVY_THRESHOLD, preflight
from klineshare.limits.rate import RateGate
from klineshare.limits.snapshot import LimitsSnapshot, parse_me_payload
from klineshare.limits.symbol_quota import SymbolMinuteGate
from klineshare.symbols import normalize_symbol, normalize_symbols

DEFAULT_BASE_URL = 'https://data.klineshare.cn'
DEFAULT_LIMITS_TTL = 600.0

_global_api_key: str = ''


def set_api_key(api_key: str) -> None:
    """Set the process-wide API Key (also read from env if unset)."""
    global _global_api_key
    _global_api_key = (api_key or '').strip()


def get_api_key() -> str:
    if _global_api_key:
        return _global_api_key
    return (os.getenv('KLINESHARE_API_KEY') or '').strip()


def pro_api(
    api_key: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
    timeout: float = 60.0,
    as_dataframe: Optional[bool] = None,
    limits: str = 'enforce',
    overflow: str = 'error',
    clamp_count: bool = True,
    on_rate_limit: str = 'wait',
    limits_ttl: float = DEFAULT_LIMITS_TTL,
    pool_connections: Optional[int] = None,
    pool_maxsize: Optional[int] = None,
    kline_batch: str = 'multi',
    kline_heavy_threshold: int = DEFAULT_KLINE_HEAVY_THRESHOLD,
    follow_api_base: bool = True,
) -> 'Client':
    """Create a KlineShare API client."""
    return Client(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        as_dataframe=as_dataframe,
        limits=limits,
        overflow=overflow,
        clamp_count=clamp_count,
        on_rate_limit=on_rate_limit,
        limits_ttl=limits_ttl,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        kline_batch=kline_batch,
        kline_heavy_threshold=kline_heavy_threshold,
        follow_api_base=follow_api_base,
    )


def _build_session(
    session: Optional[requests.Session],
    *,
    pool_connections: Optional[int],
    pool_maxsize: Optional[int],
) -> requests.Session:
    if session is not None:
        return session
    sess = requests.Session()
    # Keep requests' default Accept-Encoding (gzip/deflate/br); never wipe it.
    if not sess.headers.get('Accept-Encoding'):
        sess.headers['Accept-Encoding'] = 'gzip, deflate'
    if pool_connections is not None or pool_maxsize is not None:
        adapter = HTTPAdapter(
            pool_connections=pool_connections or 10,
            pool_maxsize=pool_maxsize or 10,
        )
        sess.mount('https://', adapter)
        sess.mount('http://', adapter)
    return sess


def _env_base_url() -> str:
    return (os.getenv('KLINESHARE_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')


def _clean_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not params:
        return out
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = 'true' if value else 'false'
        else:
            out[key] = value
    return out


def _pick_symbol(**kwargs: Any) -> Optional[Any]:
    if kwargs.get('symbol') is not None:
        return kwargs['symbol']
    if kwargs.get('ks_code') is not None:
        return kwargs['ks_code']
    return None


class Client(
    MarketEndpoints,
    IndexEtfEndpoints,
    ExtendedEndpoints,
    TopicsEndpoints,
    CatalogBondEndpoints,
    WsEndpoints,
    MetaEndpoints,
):
    """HTTP client for KlineShare External API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        as_dataframe: Optional[bool] = None,
        session: Optional[requests.Session] = None,
        limits: str = 'enforce',
        overflow: str = 'error',
        clamp_count: bool = True,
        on_rate_limit: str = 'wait',
        limits_ttl: float = DEFAULT_LIMITS_TTL,
        pool_connections: Optional[int] = None,
        pool_maxsize: Optional[int] = None,
        kline_batch: str = 'multi',
        kline_heavy_threshold: int = DEFAULT_KLINE_HEAVY_THRESHOLD,
        follow_api_base: bool = True,
    ) -> None:
        self.api_key = (api_key if api_key is not None else get_api_key()).strip()
        self.base_url = (base_url or _env_base_url()).rstrip('/')
        self.timeout = timeout
        self.as_dataframe = as_dataframe
        self.limits_mode = (limits or 'enforce').strip().lower()
        self.overflow = (overflow or 'error').strip().lower()
        self.clamp_count = bool(clamp_count)
        self.on_rate_limit = (on_rate_limit or 'wait').strip().lower()
        self.limits_ttl = float(limits_ttl)
        self.kline_batch = (kline_batch or 'multi').strip().lower()
        self.kline_heavy_threshold = int(kline_heavy_threshold)
        self.follow_api_base = bool(follow_api_base)
        self._session = _build_session(
            session,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
        )
        self._owns_session = session is None
        if self.api_key:
            self._session.headers['X-API-Key'] = self.api_key
        self._limits: Optional[LimitsSnapshot] = None
        self._api_base: Optional[str] = None
        self._rate_gate = RateGate()
        self._symbol_gate = SymbolMinuteGate()
        self._limit_advice: List[str] = []

    # --------------------------------------------------------------- limits
    @property
    def limits(self) -> Optional[LimitsSnapshot]:
        """Cached ``/v1/me`` snapshot (may be ``None`` until first refresh)."""
        return self._limits

    @property
    def api_base(self) -> Optional[str]:
        """Assigned request root from last ``/v1/me`` / auth hint (no trailing slash)."""
        return self._api_base

    def _adopt_api_base(self, api_base: Optional[str]) -> bool:
        """Switch ``base_url`` to ``api_base`` when following is enabled. Return True if changed."""
        if not api_base:
            return False
        new = api_base.strip().rstrip('/')
        if not new:
            return False
        self._api_base = new
        if not self.follow_api_base:
            return False
        if new == self.base_url:
            return False
        self.base_url = new
        return True

    def refresh_limits(self) -> LimitsSnapshot:
        """Force ``GET /v1/me`` and replace the cached snapshot."""
        body = self.request('/v1/me', raw=True, skip_limits=True)
        snap = parse_me_payload(body)
        self._limits = snap
        self._adopt_api_base(_extract_api_base(body) or _extract_api_base(snap.raw))
        return snap

    def _ensure_limits(self) -> LimitsSnapshot:
        if self._limits is None or self._limits.is_stale(self.limits_ttl):
            return self.refresh_limits()
        return self._limits

    def _should_enforce(self, path: str, *, auth: bool, skip_limits: bool) -> bool:
        if skip_limits or self.limits_mode == 'off' or not auth:
            return False
        if path in ('/v1/me', '/v1/health') or path.startswith('/public/'):
            return False
        return self.limits_mode in ('enforce', 'advise')

    def _apply_limits(
        self,
        path: str,
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        snap = self._ensure_limits()
        soft = self.limits_mode == 'advise'
        out, policy, n_sym, advice = preflight(
            path,
            params,
            snap,
            clamp_count=self.clamp_count,
            overflow=self.overflow,
            soft=soft,
        )
        if advice:
            self._limit_advice.extend(advice)
        if soft:
            return out

        on_lim = self.on_rate_limit if self.on_rate_limit in ('wait', 'error') else 'wait'
        if snap.global_rate:
            reqs, win = snap.global_rate
            self._rate_gate.acquire(
                'global', limit=reqs, window_secs=win, on_limit=on_lim,
            )
        scope = policy.scope
        if scope and scope in snap.scope_rates:
            reqs, win = snap.scope_rates[scope]
            self._rate_gate.acquire(
                f'scope:{scope}', limit=reqs, window_secs=win, on_limit=on_lim,
            )
        ep_rule = snap.endpoint_rates.get(policy.path)
        if ep_rule is None:
            for ep_path, rule in snap.endpoint_rates.items():
                if policy.path == ep_path or policy.path.startswith(ep_path + '/'):
                    ep_rule = rule
                    break
        if ep_rule:
            reqs, win = ep_rule
            self._rate_gate.acquire(
                f'endpoint:{policy.path}', limit=reqs, window_secs=win, on_limit=on_lim,
            )
        self._symbol_gate.acquire(n_sym, limit=snap.max_symbols_per_minute)
        return out

    @property
    def limit_advice(self) -> List[str]:
        """Advice messages collected in ``limits='advise'`` (and count clamps)."""
        return list(self._limit_advice)

    def clear_limit_advice(self) -> None:
        self._limit_advice.clear()

    def close(self) -> None:
        """Close the underlying Session when owned by this Client."""
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> 'Client':
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ HTTP
    def request(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        auth: bool = True,
        raw: bool = False,
        as_dataframe: Optional[bool] = None,
        expand_compact_rows: bool = True,
        skip_limits: bool = False,
        _api_base_retried: bool = False,
    ) -> Any:
        if auth and not self.api_key:
            raise KlineShareAuthError(
                '未配置 API Key：请 ks.set_api_key(...) 或设置环境变量 KLINESHARE_API_KEY',
                code=401,
                http_status=401,
            )

        req_params = params
        if self._should_enforce(path, auth=auth, skip_limits=skip_limits):
            req_params = self._apply_limits(path, params)

        url = f'{self.base_url}{path}'
        try:
            resp = self._session.get(
                url,
                params=_clean_params(req_params),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise KlineShareError(f'请求失败: {exc}', code=0) from exc

        try:
            body = resp.json()
        except ValueError:
            raise KlineShareError(
                resp.text[:500] or '非 JSON 响应',
                code=resp.status_code,
                http_status=resp.status_code,
            )

        if resp.status_code == 429 or (isinstance(body, dict) and body.get('code') == 429):
            retry_after = None
            ra = resp.headers.get('Retry-After')
            if ra:
                try:
                    retry_after = float(ra)
                except ValueError:
                    retry_after = None
            if isinstance(body, dict) and body.get('retry_after') is not None:
                try:
                    retry_after = float(body['retry_after'])
                except (TypeError, ValueError):
                    pass
            self._rate_gate.calibrate('global', retry_after=retry_after)
            raise KlineShareRateLimitError(
                body.get('message') if isinstance(body, dict) else 'rate limited',
                code=429,
                http_status=resp.status_code,
                body=body,
                retry_after=retry_after,
            )

        if resp.status_code in (401, 403) or (
            isinstance(body, dict) and body.get('success') is False and body.get('code') in (401, 403)
        ):
            self._limits = None
            hinted = _extract_api_base(body)
            # Wrong / stale entry node (incl. mid-session reassignment):
            # 403 + different api_base → switch base_url and retry once.
            if (
                not _api_base_retried
                and _is_forbidden(resp.status_code, body)
                and _is_wrong_entry_hint(body, hinted_base=hinted, current_base=self.base_url)
                and self._adopt_api_base(hinted)
            ):
                return self.request(
                    path,
                    params,
                    auth=auth,
                    raw=raw,
                    as_dataframe=as_dataframe,
                    expand_compact_rows=expand_compact_rows,
                    skip_limits=skip_limits,
                    _api_base_retried=True,
                )
            msg = body.get('message') if isinstance(body, dict) else 'unauthorized'
            raise KlineShareAuthError(
                str(msg),
                code=body.get('code') if isinstance(body, dict) else resp.status_code,
                http_status=resp.status_code,
                body=body,
                api_base=hinted,
            )

        if resp.status_code >= 400 or (isinstance(body, dict) and body.get('success') is False):
            msg = body.get('message') if isinstance(body, dict) else resp.text[:500]
            raise KlineShareError(
                str(msg or 'request failed'),
                code=body.get('code') if isinstance(body, dict) else resp.status_code,
                http_status=resp.status_code,
                body=body,
            )

        if path.rstrip('/') == '/v1/me' and isinstance(body, dict):
            self._adopt_api_base(_extract_api_base(body))

        if raw:
            return body

        return self._unwrap(body, as_dataframe=as_dataframe, expand_compact_rows=expand_compact_rows)

    def _unwrap(
        self,
        body: Any,
        *,
        as_dataframe: Optional[bool],
        expand_compact_rows: bool,
    ) -> Any:
        flag = self.as_dataframe if as_dataframe is None else as_dataframe
        if not isinstance(body, dict):
            return body

        data = body.get('data', body)

        if expand_compact_rows and is_kline_raw_payload(body):
            rows = expand_kline_raw(body)
            return maybe_frame(rows, as_dataframe=flag)

        if expand_compact_rows and isinstance(data, dict) and is_kline_raw_payload(data):
            rows = expand_kline_raw(data)
            return maybe_frame(rows, as_dataframe=flag)

        if expand_compact_rows and is_kline_matrix_payload(body):
            rows = expand_kline_matrix(body)
            return maybe_frame(rows, as_dataframe=flag)

        if expand_compact_rows and isinstance(data, dict) and is_kline_matrix_payload(data):
            rows = expand_kline_matrix(data)
            return maybe_frame(rows, as_dataframe=flag)

        if expand_compact_rows and is_compact_payload(body):
            rows = expand_compact(body)
            return maybe_frame(rows, as_dataframe=flag)

        if expand_compact_rows and isinstance(data, dict) and is_compact_payload(data):
            rows = expand_compact(data)
            return maybe_frame(rows, as_dataframe=flag)

        return maybe_frame(data, as_dataframe=flag)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, **opts: Any) -> Any:
        return self.request(path, params, **opts)

    def _with_symbol(self, params: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        out = dict(params)
        do_norm = kwargs.pop('normalize', True)
        one_fn = kwargs.pop('normalizer', None)
        sym = _pick_symbol(**kwargs)
        if sym is not None:
            if do_norm:
                fn = one_fn or normalize_symbol
                many = isinstance(sym, (list, tuple)) or (
                    isinstance(sym, str) and (',' in sym or ';' in sym)
                )
                if many:
                    if one_fn is not None:
                        if isinstance(sym, str):
                            parts = [p.strip() for p in sym.replace(';', ',').split(',') if p.strip()]
                        else:
                            parts = [str(p).strip() for p in sym if str(p).strip()]
                        out['symbol'] = ','.join(fn(p) for p in parts)
                    else:
                        out['symbol'] = normalize_symbols(sym)
                else:
                    out['symbol'] = fn(str(sym))
            else:
                if isinstance(sym, (list, tuple)):
                    out['symbol'] = ','.join(str(x).strip() for x in sym if str(x).strip())
                else:
                    text = str(sym).strip()
                    out['symbol'] = text.replace(';', ',')
        # drop aliases so they are not sent upstream
        out.pop('ks_code', None)
        return out

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, **opts: Any) -> Any:
        """Call any GET path (e.g. ``/v2/kline``)."""
        return self.request(path, params, **opts)

    def request_text(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        auth: bool = False,
    ) -> str:
        """GET a plain-text endpoint (docs / llms)."""
        if auth and not self.api_key:
            raise KlineShareAuthError(
                '未配置 API Key：请 ks.set_api_key(...) 或设置环境变量 KLINESHARE_API_KEY',
                code=401,
                http_status=401,
            )
        url = f'{self.base_url}{path}'
        try:
            resp = self._session.get(url, params=_clean_params(params), timeout=self.timeout)
        except requests.RequestException as exc:
            raise KlineShareError(f'请求失败: {exc}', code=0) from exc
        if resp.status_code >= 400:
            raise KlineShareError(
                resp.text[:500] or 'request failed',
                code=resp.status_code,
                http_status=resp.status_code,
            )
        return resp.text

    def stream(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        auth: bool = True,
        timeout: Optional[float] = None,
        _api_base_retried: bool = False,
    ) -> Iterator[Dict[str, Any]]:
        """
        Subscribe to an SSE endpoint; yield parsed JSON event dicts.

        Caller should iterate (or break) to keep / close the connection.
        """
        if auth and not self.api_key:
            raise KlineShareAuthError(
                '未配置 API Key：请 ks.set_api_key(...) 或设置环境变量 KLINESHARE_API_KEY',
                code=401,
                http_status=401,
            )
        # SSE also consumes RPM / trial quotas — run the same preflight + rate gate.
        req_params = params
        if self._should_enforce(path, auth=auth, skip_limits=False):
            req_params = self._apply_limits(path, params)

        url = f'{self.base_url}{path}'
        # (connect, read) — read None keeps long-lived SSE open
        to = timeout if timeout is not None else (self.timeout, None)
        try:
            resp = self._session.get(
                url,
                params=_clean_params(req_params),
                stream=True,
                timeout=to,
                headers={'Accept': 'text/event-stream'},
            )
        except requests.RequestException as exc:
            raise KlineShareError(f'请求失败: {exc}', code=0) from exc

        if resp.status_code == 429:
            raise KlineShareRateLimitError(
                'rate limited',
                code=429,
                http_status=429,
                retry_after=float(resp.headers['Retry-After'])
                if resp.headers.get('Retry-After')
                else None,
            )
        if resp.status_code in (401, 403):
            status = resp.status_code
            try:
                body = resp.json()
                msg = body.get('message', 'unauthorized')
            except ValueError:
                body, msg = None, resp.text[:500] or 'unauthorized'
            hinted = _extract_api_base(body)
            resp.close()
            if (
                not _api_base_retried
                and _is_forbidden(status, body)
                and _is_wrong_entry_hint(body, hinted_base=hinted, current_base=self.base_url)
                and self._adopt_api_base(hinted)
            ):
                yield from self.stream(
                    path,
                    params,
                    auth=auth,
                    timeout=timeout,
                    _api_base_retried=True,
                )
                return
            raise KlineShareAuthError(
                str(msg),
                code=status,
                http_status=status,
                body=body,
                api_base=hinted,
            )
        if resp.status_code >= 400:
            raise KlineShareError(
                resp.text[:500] or 'request failed',
                code=resp.status_code,
                http_status=resp.status_code,
            )

        try:
            yield from iter_sse_from_response(resp)
        finally:
            resp.close()
