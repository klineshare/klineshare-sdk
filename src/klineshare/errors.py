"""SDK exceptions."""

from __future__ import annotations

from typing import Any, Optional


class KlineShareError(Exception):
    """API or client error."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        http_status: Optional[int] = None,
        body: Any = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.body = body
        self.retry_after = retry_after

    def __str__(self) -> str:  # pragma: no cover - trivial
        parts = [self.message]
        if self.code is not None:
            parts.append(f'code={self.code}')
        if self.http_status is not None:
            parts.append(f'http={self.http_status}')
        return ' | '.join(parts)


class KlineShareAuthError(KlineShareError):
    """Missing or invalid API key / insufficient scope / wrong entry node.

    Wrong-node ``403`` responses may include ``api_base`` (assigned request root);
    the Client adopts it when ``follow_api_base=True``.
    """

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        http_status: Optional[int] = None,
        body: Any = None,
        retry_after: Optional[float] = None,
        api_base: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            http_status=http_status,
            body=body,
            retry_after=retry_after,
        )
        if api_base is not None:
            self.api_base = api_base
        elif isinstance(body, dict) and isinstance(body.get('api_base'), str):
            text = body['api_base'].strip().rstrip('/')
            self.api_base = text or None
        else:
            self.api_base = None


class KlineShareRateLimitError(KlineShareError):
    """HTTP 429 rate limited, or local RPM gate refused the call."""


class KlineShareQuotaError(KlineShareError):
    """Client-side quota / volume preflight failed (未向上游发请求)."""

    def __init__(
        self,
        message: str,
        *,
        limit_name: Optional[str] = None,
        limit_value: Any = None,
        got: Any = None,
        code: Optional[int] = None,
        http_status: Optional[int] = None,
        body: Any = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            http_status=http_status,
            body=body,
            retry_after=retry_after,
        )
        self.limit_name = limit_name
        self.limit_value = limit_value
        self.got = got

    def __str__(self) -> str:  # pragma: no cover - trivial
        parts = [self.message]
        if self.limit_name is not None:
            parts.append(f'limit={self.limit_name}')
        if self.limit_value is not None:
            parts.append(f'max={self.limit_value}')
        if self.got is not None:
            parts.append(f'got={self.got}')
        if self.code is not None:
            parts.append(f'code={self.code}')
        return ' | '.join(parts)
