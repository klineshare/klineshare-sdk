"""Level2 feed helpers used by ``Client.level2``."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from klineshare.errors import KlineShareError
from klineshare.symbols import normalize_symbol, normalize_symbols

_ENV_BIN = 'KLINESHARE_KS_LIVE'
_ENV_CACHE = 'KLINESHARE_KS_LIVE_DIR'
_ENV_URL = 'KLINESHARE_KS_LIVE_URL'

# Align with external_api.level2_normalize.CHANNELS / ks-live ChannelOrder.
LEVEL2_CHANNELS = ('depth', 'orders', 'trades', 'entrust')
_DEFAULT_CHANNELS = list(LEVEL2_CHANNELS)

_RESOLVE_PATH = '/public/v1/sdk/ks-live'


def _sdk_version() -> str:
    try:
        from klineshare import __version__

        return str(__version__)
    except Exception:
        return '0.0.0'


def _user_agent() -> str:
    return f'klineshare-sdk/{_sdk_version()}'


def _as_symbol_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = normalize_symbols(raw) if (',' in raw or ';' in raw) else normalize_symbol(raw)
        if isinstance(text, str) and ',' in text:
            return [p for p in text.split(',') if p]
        return [text] if text else []
    if isinstance(raw, (list, tuple)):
        out: List[str] = []
        for item in raw:
            out.extend(_as_symbol_list(item))
        return out
    return [normalize_symbol(str(raw))]


def _as_channel_list(raw: Any) -> List[str]:
    if raw is None:
        return list(_DEFAULT_CHANNELS)
    if isinstance(raw, str):
        return [c.strip() for c in raw.replace(';', ',').split(',') if c.strip()]
    return [str(c).strip() for c in raw if str(c).strip()]


def ks_live_platform(
    *,
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> Tuple[str, str]:
    """Return ``(os, arch)`` for the public ks-live resolve API."""
    sys_name = (system or platform.system()).lower()
    mach = (machine or platform.machine()).lower()

    if mach in ('x86_64', 'amd64'):
        arch = 'amd64'
    elif mach in ('arm64', 'aarch64'):
        arch = 'arm64'
    else:
        raise KlineShareError(
            f'当前架构暂不支持 Level2: {mach}',
            code=0,
        )

    if sys_name == 'darwin':
        return 'darwin', arch
    if sys_name == 'linux':
        return 'linux', arch
    if sys_name in ('windows', 'win32', 'cygwin'):
        return 'windows', arch
    raise KlineShareError(f'当前系统暂不支持 Level2: {sys_name}', code=0)


def ks_live_asset_name(
    *,
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> str:
    """Map current platform to published ``ks-live-*`` filename."""
    os_name, arch = ks_live_platform(system=system, machine=machine)
    if os_name == 'windows':
        return f'ks-live-windows-{arch}.exe'
    return f'ks-live-{os_name}-{arch}'


def default_ks_live_dir() -> Path:
    override = (os.getenv(_ENV_CACHE) or '').strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / '.cache' / 'klineshare' / 'ks-live'


def _meta_path(binary_path: Path) -> Path:
    return binary_path.with_suffix(binary_path.suffix + '.meta.json')


def _read_meta(binary_path: Path) -> Dict[str, Any]:
    meta = _meta_path(binary_path)
    if not meta.is_file():
        return {}
    try:
        raw = json.loads(meta.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_meta(binary_path: Path, *, url: str, sha256: Optional[str] = None) -> None:
    payload = {
        'url': url,
        'sha256': (sha256 or '').strip().lower() or None,
    }
    _meta_path(binary_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def _meta_matches(
    binary_path: Path,
    *,
    url: str,
    sha256: Optional[str] = None,
) -> bool:
    if not binary_path.is_file():
        return False
    meta = _read_meta(binary_path)
    if (meta.get('url') or '').strip() != url.strip():
        return False
    expect = (sha256 or '').strip().lower()
    if not expect:
        return True
    got = (meta.get('sha256') or '').strip().lower()
    if got and got == expect:
        return True
    # Re-hash file if sidecar missing sha but upstream now publishes one.
    digest = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    return digest == expect


def resolve_ks_live_binary(*, binary: Optional[str] = None) -> Optional[Path]:
    """Return a pinned binary path if found (explicit / env / PATH).

    Does **not** return the auto-download cache — that path needs upstream
    URL/meta validation via ``ensure_ks_live``.
    """
    if binary:
        p = Path(binary).expanduser()
        return p if p.is_file() else None
    env = (os.getenv(_ENV_BIN) or '').strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    which = shutil.which('ks-live')
    if which:
        return Path(which)
    return None


def resolve_ks_live_release(
    api_base: str,
    *,
    sdk_version: Optional[str] = None,
    os_name: Optional[str] = None,
    arch: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Fetch download metadata from ``GET /public/v1/sdk/ks-live``."""
    base = (api_base or '').rstrip('/')
    if not base:
        raise KlineShareError('解析 Level2 下载地址需要 api_base', code=0)
    if os_name is None or arch is None:
        os_name, arch = ks_live_platform()
    ver = (sdk_version or _sdk_version()).strip()
    params = urllib.parse.urlencode({
        'sdk_version': ver,
        'os': os_name,
        'arch': arch,
    })
    url = f'{base}{_RESOLVE_PATH}?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', errors='replace')[:300]
        except Exception:
            detail = str(exc)
        raise KlineShareError(
            f'解析 Level2 下载地址失败 HTTP {exc.code}: {detail or exc}',
            code=int(exc.code or 0),
        ) from exc
    except Exception as exc:
        raise KlineShareError(f'解析 Level2 下载地址失败（{exc}）', code=0) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise KlineShareError('解析 Level2 下载地址：响应非 JSON', code=0) from exc
    if not isinstance(payload, dict) or not payload.get('success'):
        msg = ''
        if isinstance(payload, dict):
            msg = str(payload.get('message') or '')
        raise KlineShareError(
            f'解析 Level2 下载地址失败: {msg or body[:200]}',
            code=int((payload or {}).get('code') or 0) if isinstance(payload, dict) else 0,
        )
    data = payload.get('data')
    if not isinstance(data, dict) or not str(data.get('url') or '').strip():
        raise KlineShareError('解析 Level2 下载地址：缺少 data.url', code=0)
    return data


def download_ks_live(
    *,
    url: str,
    dest_dir: Optional[Union[str, Path]] = None,
    name: Optional[str] = None,
    sha256: Optional[str] = None,
    force: bool = False,
    timeout: float = 120.0,
) -> Path:
    """
    Download ``ks-live`` from a full URL into the cache directory.

    Override cache with ``KLINESHARE_KS_LIVE_DIR``; pin a local binary with
    ``KLINESHARE_KS_LIVE``; skip resolve with ``KLINESHARE_KS_LIVE_URL``.
    """
    fetch_url = (url or '').strip()
    if not fetch_url:
        raise KlineShareError('下载 Level2 组件需要完整 url', code=0)
    asset = Path((name or '').strip() or ks_live_asset_name()).name
    if not asset or asset in ('.', '..'):
        asset = ks_live_asset_name()
    out_dir = Path(dest_dir).expanduser() if dest_dir else default_ks_live_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / asset
    expect_sha = (sha256 or '').strip().lower() or None
    if target.is_file() and not force and _meta_matches(target, url=fetch_url, sha256=expect_sha):
        return target

    tmp_fd, tmp_name = tempfile.mkstemp(prefix='ks-live-', dir=str(out_dir))
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        req = urllib.request.Request(fetch_url, headers={'User-Agent': _user_agent()})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = resp.read()
        if not data:
            raise KlineShareError(f'下载 Level2 组件为空: {asset}', code=0)
        if expect_sha:
            digest = hashlib.sha256(data).hexdigest()
            if digest != expect_sha:
                raise KlineShareError(
                    f'Level2 组件校验失败: sha256 不匹配（got {digest[:12]}…）',
                    code=0,
                )
        stored_sha = expect_sha or hashlib.sha256(data).hexdigest()
        tmp_path.write_bytes(data)
        mode = tmp_path.stat().st_mode
        tmp_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        tmp_path.replace(target)
        _write_meta(target, url=fetch_url, sha256=stored_sha)
    except KlineShareError:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise KlineShareError(f'下载 Level2 组件失败（{exc}）', code=0) from exc
    return target


def ensure_ks_live(
    *,
    binary: Optional[str] = None,
    download: bool = True,
    api_base: Optional[str] = None,
    force: bool = False,
) -> Path:
    """Locate the Level2 runtime binary, optionally resolving + downloading it."""
    found = resolve_ks_live_binary(binary=binary)
    if found is not None:
        return found

    url_override = (os.getenv(_ENV_URL) or '').strip()
    if url_override:
        return download_ks_live(url=url_override, force=force)

    if not download:
        cached = default_ks_live_dir() / ks_live_asset_name()
        if cached.is_file():
            return cached
        raise KlineShareError(
            '未找到 Level2 组件：请允许自动下载，或通过 binary= 指定路径',
            code=0,
        )

    base = (api_base or '').strip().rstrip('/')
    if not base:
        raise KlineShareError(
            '自动下载 Level2 需要 api_base（由上游 /public/v1/sdk/ks-live 下发链接）',
            code=0,
        )
    release = resolve_ks_live_release(base)
    return download_ks_live(
        url=str(release['url']),
        name=str(release.get('name') or '') or None,
        sha256=str(release.get('sha256') or '') or None,
        force=force,
    )


class Level2LiveFeed:
    """Level2 行情流：由 ``pro.level2(...)`` 创建，迭代得到报价 JSON。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        symbols: Sequence[str],
        channels: Sequence[str],
        binary: Optional[str] = None,
        bind: Optional[str] = None,
        dump: str = 'none',
        run_for: Optional[float] = None,
        download: bool = True,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        if not api_key:
            raise KlineShareError('Level2 需要 API Key', code=401)
        if not symbols:
            raise KlineShareError('Level2 需要至少一个 symbol', code=400)
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip('/')
        self.symbols = list(symbols)
        self.channels = list(channels) or list(_DEFAULT_CHANNELS)
        self.binary = binary
        self.bind = bind
        self.dump = dump
        self.run_for = run_for
        self.download = download
        self._extra_env = dict(env or {})
        self._proc: Optional[subprocess.Popen[str]] = None
        self._stderr_tail: List[str] = []
        self._stderr_thread: Optional[threading.Thread] = None

    def start(self) -> 'Level2LiveFeed':
        bin_path = ensure_ks_live(
            binary=self.binary,
            download=self.download,
            api_base=self.base_url,
        )
        cmd = [
            str(bin_path),
            '-symbols',
            ','.join(self.symbols),
            '-channels',
            ','.join(self.channels),
            '-out',
            'stdout',
            '-dump',
            self.dump or 'none',
        ]
        if self.run_for is not None and self.run_for > 0:
            cmd.extend(['-for', f'{self.run_for}s'])

        env = os.environ.copy()
        env['L2_API_KEY'] = self.api_key
        env['L2_API_BASE'] = self.base_url
        if self.bind:
            env['L2_BIND'] = self.bind
        env.update(self._extra_env)

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            raise KlineShareError(f'启动 Level2 失败: {exc}', code=0) from exc
        # Drain stderr so a full pipe cannot stall long-lived feeds.
        self._stderr_tail = []
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name='level2-stderr',
            daemon=True,
        )
        self._stderr_thread.start()
        return self

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                text = (line or '').rstrip()
                if not text:
                    continue
                self._stderr_tail.append(text)
                if len(self._stderr_tail) > 40:
                    self._stderr_tail = self._stderr_tail[-40:]
        except Exception:
            return

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        try:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
        except Exception:
            pass
        thr = self._stderr_thread
        if thr is not None and thr.is_alive():
            thr.join(timeout=1.0)
        self._stderr_thread = None

    def __enter__(self) -> 'Level2LiveFeed':
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise KlineShareError('Level2 未启动', code=0)
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                text = (line or '').strip()
                if not text:
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict):
                    yield msg
        except (ValueError, OSError):
            # stdout closed while we were reading (feed.close())
            return
        code = proc.poll()
        if code is None:
            try:
                code = proc.wait(timeout=1)
            except Exception:
                return
        err = '\n'.join(self._stderr_tail).strip()
        if code is not None and code < 0:
            # terminated by signal (often us)
            return
        if code is not None and code > 0:
            raise KlineShareError(
                f'Level2 退出码 {code}' + (f': {err[-500:]}' if err else ''),
                code=code,
            )
