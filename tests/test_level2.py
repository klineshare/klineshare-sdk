"""Tests for Level2 via ks-live (URL resolved from upstream)."""

from __future__ import annotations

import hashlib
import json
import stat
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from klineshare import Client, KlineShareQuotaError
from klineshare.client import set_api_key
from klineshare.errors import KlineShareError
from klineshare.level2 import (
    Level2LiveFeed,
    download_ks_live,
    ensure_ks_live,
    ks_live_asset_name,
    resolve_ks_live_release,
)
from klineshare.limits.snapshot import parse_me_payload


def test_ks_live_asset_name_platforms():
    assert ks_live_asset_name(system='Darwin', machine='arm64') == 'ks-live-darwin-arm64'
    assert ks_live_asset_name(system='Linux', machine='x86_64') == 'ks-live-linux-amd64'
    assert (
        ks_live_asset_name(system='Windows', machine='AMD64')
        == 'ks-live-windows-amd64.exe'
    )


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_resolve_ks_live_release_parses_data(monkeypatch):
    name = ks_live_asset_name()
    payload = {
        'success': True,
        'data': {
            'url': f'https://cdn.example/{name}',
            'name': name,
            'os': 'darwin',
            'arch': 'arm64',
            'sdk_version': '0.2.4',
            'matched': '*',
            'sha256': None,
        },
    }

    def fake_urlopen(req, timeout=0):
        assert '/public/v1/sdk/ks-live?' in req.full_url
        assert 'sdk_version=' in req.full_url
        return _FakeResp(json.dumps(payload).encode('utf-8'))

    monkeypatch.setattr('klineshare.level2.urllib.request.urlopen', fake_urlopen)
    data = resolve_ks_live_release('https://data.example')
    assert data['url'].endswith(name)
    assert data['name'] == name


def test_download_ks_live_writes_executable_and_meta(tmp_path, monkeypatch):
    name = ks_live_asset_name()
    payload = b'\x7fELF-fake-binary'
    url = f'https://cdn.example/{name}'
    digest = hashlib.sha256(payload).hexdigest()

    monkeypatch.setenv('KLINESHARE_KS_LIVE_DIR', str(tmp_path))
    with patch(
        'klineshare.level2.urllib.request.urlopen',
        return_value=_FakeResp(payload),
    ):
        path = download_ks_live(url=url, dest_dir=tmp_path, sha256=digest, force=True)
    assert path.name == name
    assert path.read_bytes() == payload
    assert path.stat().st_mode & stat.S_IXUSR
    meta = json.loads(path.with_suffix(path.suffix + '.meta.json').read_text())
    assert meta['url'] == url
    assert meta['sha256'] == digest


def test_download_rejects_missing_url(tmp_path):
    with pytest.raises(KlineShareError, match='完整 url'):
        download_ks_live(url='', dest_dir=tmp_path)


def test_ensure_reuses_cache_when_meta_matches(tmp_path, monkeypatch):
    name = ks_live_asset_name()
    url = f'https://cdn.example/{name}'
    binary = tmp_path / name
    binary.write_bytes(b'cached')
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    (tmp_path / f'{name}.meta.json').write_text(
        json.dumps({'url': url, 'sha256': None}),
        encoding='utf-8',
    )
    monkeypatch.setenv('KLINESHARE_KS_LIVE_DIR', str(tmp_path))
    monkeypatch.delenv('KLINESHARE_KS_LIVE', raising=False)
    monkeypatch.delenv('KLINESHARE_KS_LIVE_URL', raising=False)

    resolve_calls = {'n': 0}

    def fake_resolve(api_base, **kwargs):
        resolve_calls['n'] += 1
        return {'url': url, 'name': name, 'sha256': None}

    def boom(*_a, **_k):
        raise AssertionError('should not re-download')

    monkeypatch.setattr('klineshare.level2.resolve_ks_live_release', fake_resolve)
    monkeypatch.setattr('klineshare.level2.urllib.request.urlopen', boom)
    monkeypatch.setattr('klineshare.level2.shutil.which', lambda *_a, **_k: None)

    path = ensure_ks_live(download=True, api_base='https://data.example')
    assert path == binary
    assert path.read_bytes() == b'cached'
    assert resolve_calls['n'] == 1


def test_ensure_redownloads_when_url_changes(tmp_path, monkeypatch):
    name = ks_live_asset_name()
    old_url = f'https://cdn.example/old/{name}'
    new_url = f'https://cdn.example/new/{name}'
    binary = tmp_path / name
    binary.write_bytes(b'old')
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    (tmp_path / f'{name}.meta.json').write_text(
        json.dumps({'url': old_url, 'sha256': None}),
        encoding='utf-8',
    )
    monkeypatch.setenv('KLINESHARE_KS_LIVE_DIR', str(tmp_path))
    monkeypatch.delenv('KLINESHARE_KS_LIVE', raising=False)
    monkeypatch.delenv('KLINESHARE_KS_LIVE_URL', raising=False)
    monkeypatch.setattr('klineshare.level2.shutil.which', lambda *_a, **_k: None)

    def fake_resolve(api_base, **kwargs):
        return {'url': new_url, 'name': name, 'sha256': None}

    seen = {}

    def fake_urlopen(req, timeout=0):
        seen['url'] = req.full_url
        return _FakeResp(b'new-bytes')

    monkeypatch.setattr('klineshare.level2.resolve_ks_live_release', fake_resolve)
    monkeypatch.setattr('klineshare.level2.urllib.request.urlopen', fake_urlopen)

    path = ensure_ks_live(download=True, api_base='https://data.example')
    assert path.read_bytes() == b'new-bytes'
    assert seen['url'] == new_url
    meta = json.loads(path.with_suffix(path.suffix + '.meta.json').read_text())
    assert meta['url'] == new_url


def test_ensure_redownloads_when_sha256_changes(tmp_path, monkeypatch):
    name = 'ks-live-darwin-amd64-0.1.0'
    url = f'https://cdn.example/{name}'
    old_bytes = b'old-bin'
    new_bytes = b'new-bin'
    old_sha = hashlib.sha256(old_bytes).hexdigest()
    new_sha = hashlib.sha256(new_bytes).hexdigest()
    binary = tmp_path / name
    binary.write_bytes(old_bytes)
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    (tmp_path / f'{name}.meta.json').write_text(
        json.dumps({'url': url, 'sha256': old_sha}),
        encoding='utf-8',
    )
    monkeypatch.setenv('KLINESHARE_KS_LIVE_DIR', str(tmp_path))
    monkeypatch.delenv('KLINESHARE_KS_LIVE', raising=False)
    monkeypatch.delenv('KLINESHARE_KS_LIVE_URL', raising=False)
    monkeypatch.setattr('klineshare.level2.shutil.which', lambda *_a, **_k: None)

    def fake_resolve(api_base, **kwargs):
        return {'url': url, 'name': name, 'sha256': new_sha}

    def fake_urlopen(req, timeout=0):
        return _FakeResp(new_bytes)

    monkeypatch.setattr('klineshare.level2.resolve_ks_live_release', fake_resolve)
    monkeypatch.setattr('klineshare.level2.urllib.request.urlopen', fake_urlopen)

    path = ensure_ks_live(download=True, api_base='https://data.example')
    assert path.name == name
    assert path.read_bytes() == new_bytes
    meta = json.loads(path.with_suffix(path.suffix + '.meta.json').read_text())
    assert meta['sha256'] == new_sha


def test_ensure_ks_live_uses_env(tmp_path, monkeypatch):
    fake = tmp_path / 'ks-live-custom'
    fake.write_bytes(b'x')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv('KLINESHARE_KS_LIVE', str(fake))
    assert ensure_ks_live(download=False) == fake


def test_ensure_requires_api_base_for_download(monkeypatch):
    monkeypatch.delenv('KLINESHARE_KS_LIVE', raising=False)
    monkeypatch.delenv('KLINESHARE_KS_LIVE_URL', raising=False)
    monkeypatch.setattr('klineshare.level2.shutil.which', lambda *_a, **_k: None)
    monkeypatch.setattr(
        'klineshare.level2.default_ks_live_dir',
        lambda: Path('/tmp/klineshare-ks-live-missing-dir-xyz'),
    )
    with pytest.raises(KlineShareError, match='api_base'):
        ensure_ks_live(download=True, api_base=None)


def test_level2_quota_slots():
    set_api_key('tg_test')
    pro = Client(api_key='tg_test', limits='enforce')
    pro._limits = parse_me_payload({
        'success': True,
        'scopes': [],
        'kline': {},
        'max_level2_slots': 2,
        'level2_channels': ['depth', 'orders', 'trades', 'entrust'],
    })
    with pytest.raises(KlineShareQuotaError):
        pro.level2(symbol='a.SS,b.SS', channels='depth,orders', download=False)


def test_level2_skips_channel_not_currently_available():
    set_api_key('tg_test')
    pro = Client(api_key='tg_test', limits='enforce')
    pro._limits = parse_me_payload({
        'success': True,
        'scopes': [],
        'kline': {},
        'max_level2_slots': 1280,
        'level2_channels': ['depth', 'orders', 'trades'],
    })
    feed = pro.level2(
        symbol='600519.SS',
        channels='depth,entrust',
        download=False,
    )
    assert feed.channels == ['depth']


def test_level2_rejects_when_no_requested_channel_available():
    set_api_key('tg_test')
    pro = Client(api_key='tg_test', limits='enforce')
    pro._limits = parse_me_payload({
        'success': True,
        'scopes': [],
        'kline': {},
        'max_level2_slots': 1280,
        'level2_channels': ['depth', 'orders', 'trades'],
    })
    with pytest.raises(KlineShareQuotaError) as ei:
        pro.level2(symbol='600519.SS', channels='entrust', download=False)
    assert ei.value.limit_name == 'level2_channels'
    assert 'entrust' in ei.value.got


def test_level2_feed_reads_jsonl(tmp_path):
    script = tmp_path / 'fake-ks-live'
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json, os, sys
            assert os.environ.get("L2_API_KEY") == "tg_test"
            assert os.environ.get("L2_API_BASE")
            print(json.dumps({"type": "depth", "symbol": "600519.SS"}))
            print(json.dumps({"type": "trade", "symbol": "600519.SS"}))
            sys.exit(0)
            """
        ),
        encoding='utf-8',
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    set_api_key('tg_test')
    feed = Level2LiveFeed(
        api_key='tg_test',
        base_url='https://data.klineshare.cn',
        symbols=['600519.SS'],
        channels=['depth', 'trades'],
        binary=str(script),
        download=False,
    )
    with feed:
        msgs = list(feed)
    assert [m['type'] for m in msgs] == ['depth', 'trade']


def test_client_level2_spawns_binary(tmp_path):
    script = tmp_path / 'fake-ks-live'
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json, sys
            print(json.dumps({"ok": True}))
            """
        ),
        encoding='utf-8',
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    set_api_key('tg_test')
    pro = Client(api_key='tg_test', limits='off')
    with pro.level2(symbol='600519.SH', channels='depth', binary=str(script), download=False) as feed:
        msgs = list(feed)
    assert msgs == [{'ok': True}]
