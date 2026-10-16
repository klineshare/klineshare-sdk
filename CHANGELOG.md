# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [docs/DEVELOPMENT.md §10](docs/DEVELOPMENT.md).

## [0.2.6] - 2026-10-16

### Added

- `moneyflow_live` 支持 ``all=True``（沪深全市场，不含北交）与批量 ``symbol``（最多 200 只）

### Changed

- ``realtime`` 文档标明沪深京同路径（北交所 ``*.BJ`` 与沪深共用 ``/v1/realtime``）
- 限流路径映射：``/v1/moneyflow/ranking/live/stocks`` 独立 RPM bucket

### Removed

- 东财资金流相关封装（后续不再维护）：``moneyflow_em``、``moneyflow_ranking_em_catalog``、``moneyflow_ranking_em_stocks``、``moneyflow_ranking_em_snapshot``

## [0.2.5] - 2026-10-03

### Added

- 港股：`hkstock_realtime` / `hkstock_trend` / `hkstock_kline`（`.HK` / `HK00700` / 裸码）
- `normalize_hk_symbol` / `normalize_hk_symbols`（裸码按港股补齐，不误判深市）
- `moneyflow_live` — 实时个股资金流向（按码）``GET /v1/moneyflow/live``
- `moneyflow_live_catalog` / `plate_moneyflow_schema` — 公开字段目录
- 公开清单：`public_metals` / `public_futures` / `public_futures_v2` / `public_global_indices` / `public_global_bonds` / `public_usstocks`
- `bond_schema` — 债券字段说明 ``GET /public/v1/bond/schema``
- 美股 / 港股分时支持 ``day=1|5``

## [0.2.4] - 2026-09-30

### Changed

- Level2 ``ks-live`` 下载改为请求公开接口 ``GET /public/v1/sdk/ks-live``（携带 SDK 版本与平台），不再本地拼接 OSS 路径；缓存旁路 ``*.meta.json`` 按上游 ``url`` / ``sha256`` 失效重下

## [0.2.3] - 2026-09-29

### Fixed

- 重新打包发布（TestPyPI / 正式站均不可复用已上传的 `0.2.2` 文件名）

## [0.2.2] - 2026-09-29

### Added

- Level2 ``entrust``（逐笔委托）通道；导出 `LEVEL2_CHANNELS`
- `moneyflow_ranking_live_stocks` — 实时个股资金流排名（分页）``GET /v1/moneyflow/ranking/live/stocks``
- `moneyflow_ranking_live_catalog` / `moneyflow_ranking_em_catalog` — 公开排行目录
- 跟随 ``GET /v1/me`` 的 ``api_base``：默认 `follow_api_base=True`；HTTP/SSE/WS **建连**遇错节点会切入口并重试一次；Level2 新建前同步 `api_base`；可读 `pro.api_base`（已建立的长连接不热迁移）

### Changed

- `adjust_params` 文档标明为**推荐**自行复权；`adjust_factors` 标明**不建议**（兼容保留）

## [0.2.1] - 2026-09-23

### Added

- `exrights` — 除权除息 ``GET /v1/exrights``（需 `kline`）
- `adjust_params` — 复权参数 ``GET /v1/adjust-params``（affine 换算；需 `kline`）
- K 线默认 ``format=raw``（极限体积分隔串并展开为行）：``kline`` / ``etf_kline`` / ``index_kline`` / ``convertible_kline`` / ``bj_kline`` / 国债企债等；``format=None`` 可改回服务端列式；与 SDK ``raw=True``（完整信封）无关
- `moneyflow_em` — 东财资金流全市场 compact ``GET /v2/moneyflow/em``

## [0.2.0] - 2026-09-23

Beta: production-ready HTTP surface with heavier client safeguards.

### Added

- `kline(..., batch="multi"|"single"|"auto")` — daily+ multi-symbol auto-split when `n×count > kline_heavy_threshold` (default 3000)
- `limits="advise"` — soft quota advice via `pro.limit_advice` (still clamps `count`)
- SSE `stream()` goes through the same preflight + RPM gate as HTTP
- `AsyncClient` / `async_pro_api` — asyncio wrapper over sync Client (`asyncio.to_thread`)
- Deep usage matrix (`docs/API_USAGE.md`, `tests/api_matrix.py`), live smoke, period/count/batch live tests
- Plan-permission mock matrix + optional dual-key live (`KLINESHARE_API_KEY_FREE` / `_PRO`)

### Fixed

- Expand v2 kline columnar envelope (`fields` + `symbols`) into list/DataFrame
- Metal / futures / global-index / global-bond symbols no longer force `.US`
- Futures WS stream symbol quota; path policy for bond kline / plate moneyflow ranking

### Planned

- Native async HTTP (httpx) and async WebSocket client

## [0.1.0] - 2026-09-22

First Alpha release of the official Python SDK.

### Added

- Sync `Client` / `pro_api` with Session keep-alive and optional connection pool
- Full REST surface for market, index/ETF, topics, catalog, bond; SSE `stream`
- Symbol normalization (`.SH` → `.SS`, sina prefixes, etc.)
- Compact v2 expand + optional pandas DataFrame returns
- Client-side **limits** (`limits="enforce"` by default)
- `KlineShareQuotaError` for local quota failures
- `iter_kline` backward pagination helper
- Endpoint mixins under `src/klineshare/endpoints/`
