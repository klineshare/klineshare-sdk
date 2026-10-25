# KlineShare Python SDK — 开发依据

**读者：** SDK 维护者（非终端用户文档）。只约定客户端行为与公开契约；**不**描述服务端内部实现、模块名或未公开算法。

实现、评审、加接口时以本文为准；与线上 API 冲突时，以 `GET /public/v1/docs.md` / `llms-full.txt` 及 `GET /v1/me` 实测为准，并回写本文。

| 项 | 值 |
|----|-----|
| 包名 | `klineshare` |
| 当前版本 | 以 `pyproject.toml` / `__version__` 与发版 tag 为准 |
| 运行时 | Python ≥ 3.9 |
| HTTP | `requests`（同步）；`AsyncClient` 为 to_thread 封装 |
| 官方数据域 | `https://klineshare.cn` |

跨仓 HEAD 对照（本地）：`docs/VERSION_BASELINE.local.md`（已 gitignore，勿提交）。

---

## 1. 产品定位

### 1.1 要做

薄、稳的**官方 HTTP / SSE 客户端**：

- 方法名贴近 REST 路径（如 `realtime` → `/v1/realtime`）
- 鉴权、错误映射、标的规范化、compact 展开、可选 DataFrame
- **在客户端遵循服务端限流 / 限量**，避免多余请求与超套餐的「量」打到上游
- **传输层提效**：Session 连接复用、gzip 协商、优先 compact / 合规批量（见 §5）

### 1.2 不做

- 本地复权、指标二次计算、回测、本地行情库
- 把业务策略写进 SDK（打板逻辑、选股等）
- 跨进程 / 跨机器共享限流状态（仅进程内尽力；最终以服务端为准）

需要工具链时另开仓库（如 `klineshare-tools`），不膨胀本包。

---

## 2. 现状快照（基线）

```
src/klineshare/
  __init__.py      # 公共导出
  client.py        # Client + 几乎全部 endpoint 封装（待拆分）
  symbols.py       # 标的规范化（.SH→.SS 等）
  compact.py       # v2 compact → 行列表
  errors.py        # Auth / 通用 / RateLimit
  _result.py       # 可选 pandas
  _sse.py          # SSE 解析
tests/             # 以 mock 单测为主；尚无 CI
```

已具备：`set_api_key` / `pro_api` / `Client.request` / `stream`、符号规范化、429 解析、`raw` / `as_dataframe`、翻页 `timestamp` 毫秒→秒。

缺口（按优先级见 §9）：限额门闩、`client.py` 拆分、类型与 docstring、CI、试用 remaining、品种分钟配额、连接池可配置等。

---

## 3. 对外 API 约定

保持现有风格，新增能力不得破坏下列语义。

```python
import klineshare as ks

ks.set_api_key("tg_...")          # 或环境变量 KLINESHARE_API_KEY
pro = ks.pro_api()                # 也可 Client(api_key=..., base_url=...)

pro.kline(...)                    # 默认解包 data；列表尽量 DataFrame
pro.kline(..., raw=True)          # 完整 JSON 信封
pro.kline(..., as_dataframe=False)
pro.get("/v1/...")                # 逃生舱
pro.stream("/v1/...")             # SSE
pro.me()                          # 当前 Key 权限与限额
```

| 约定 | 说明 |
|------|------|
| 环境变量 | `KLINESHARE_API_KEY`、`KLINESHARE_BASE_URL`（入口；`/v1/me` 的 `api_base` 优先） |
| `api_base` | 默认 `follow_api_base=True`：`me` / `refresh_limits` 采纳分配入口；HTTP/SSE/WS **建连**遇错节点 `403`+`api_base` 时切换并重试一次；Level2 新建前同步 `api_base`。已建立的长连接不会热迁移，需重开 |
| SSE/WS/L2 | **会受节点迁移影响**：建连阶段可自愈；推流中途换节点不会自动迁连接 |
| 标的 | 输入容忍 `.SH` / `sh600519` 等；发出请求时为 `.SS` / `.SZ` / `.BJ` / `.US` 等标准码 |
| `symbol` / `ks_code` | 等价；只发 `symbol`，不把别名参数打上游 |
| K 线翻页 | 请求参数 `timestamp` 为**秒**；条内字段为毫秒；SDK 检测毫秒则自动除以 1000 |
| 资产路径 | 个股 / 指数 / ETF / 北交所 / 债券等走对应方法，禁止混用路径 |

破坏性变更须升次版本号（见 §10），并在 CHANGELOG 写明。

---

## 4. 限流与限量（核心原则）

公开契约有两类独立约束。SDK **应在发请求前尽量遵守**，减少无效调用与 429；最终仍以线上响应为准。

### 4.1 定义

| 类型 | 含义 | 公开契约表现 | 客户端职责 |
|------|------|--------------|------------|
| **限流** | 单位时间内的**请求次数** | 文档与 `me` 中的每分钟上限；全局 + 分 scope；超限常见 `429` + `retry_after` / `Retry-After` | 本地计数；将满则等待或失败，**禁止**无脑重试打满 |
| **限量** | 单次或单位时间的**业务量** | 如单次 symbol 数、`count`、周期/复权、试用次数、每分钟品种数（以 `me` / 文档为准） | 发前裁切 / 拒绝 /（仅显式 API）分批；**禁止**把超套餐的量原样打上去 |

权威数据源：

1. **`GET /v1/me`**（按 Key）— 实现时的主数据源  
2. **`GET /public/v1/catalog`** — 档位说明、`scope_rows` 的 path↔scope；无 Key 或文档用途  
3. 公开文档中的接口硬规则（如分时每次 1 只、K 线 v2 单次最多 5 标的）

**禁止**在代码里写死各套餐数字；一律从 `me`（及必要时 catalog）解析。

### 4.2 `/v1/me` 中与客户端相关的字段

实现解析时至少覆盖（字段名以线上为准，缺省则该规则不启用）：

| 字段 | 用途 |
|------|------|
| `rate_limit` | 全局限流（次/分） |
| `scopes[]` | 每项含 `scope`、`name`、`rate_limit` |
| `kline` | `max_count`、可用 `period`、`adjust_types`、指标种类与单次上限等 |
| `max_realtime_symbols` | `/v1/realtime`、`/v1/etf/realtime` 单次 symbol 上限 |
| `max_symbols_per_minute` | 品种分钟配额（若 me 提供；否则可对照 catalog 档位，仍优先 me） |
| `endpoint_access_status` | 试用等：`access_mode`、`max_uses`、`remaining` |
| 各类 `max_*_subscriptions` / `max_*_symbols` / `max_*_slots` | 推送连接与订阅槽（WS/SSE 实现时遵守） |

`path → scope`：优先用 `catalog.scope_rows`（或 me 内等价结构）建立映射；未知 path 只受全局限流约束。

### 4.3 客户端行为矩阵

| 场景 | 默认行为（`enforce`） | 说明 |
|------|----------------------|------|
| `count` > `kline.max_count` | **裁切**为上限后再请求 | 减少「超量」；不增加请求次数 |
| 非法 `period` / `adjust_type` / 无 scope | **本地失败**（配额/权限类错误） | 不发无效请求 |
| `realtime` symbol 数 > `max_realtime_symbols` | **本地失败** | 见 §4.4；不自动拆成 N 次请求 |
| `trend` 多标的 | **本地失败**（或文档明确只允许 1 只） | 符合接口契约 |
| K 线单次 > 5 标的 | **本地失败** | 与 `/v2/kline` 文档一致 |
| 试用 `remaining == 0` | **本地失败** | 不消耗上游、不误导用户 |
| 本窗请求数将超 RPM | **等待至窗口边界**或严格模式下失败 | 由 `on_rate_limit` 控制 |
| 本窗品种数将超 `max_symbols_per_minute` | **本地失败**或排队（实现阶段选定，默认失败） | 避免隐性多请求 |
| 服务端仍返回 429 | 抛 `KlineShareRateLimitError`，并用 `retry_after` **校准**本地窗口 | 不默认连环重试 |

### 4.4 超额策略（已定）

原则：**不要向上游打多余请求，也不要打不符合套餐的量。**

| 模式 | 行为 | 适用 |
|------|------|------|
| **默认 `overflow="error"`** | 单次参数超限量 → 抛 `KlineShareQuotaError`，**零上游调用** | 库默认；脚本可预期 |
| **`overflow="clamp"`** | 仅对可安全缩小的量裁切（如 `count`）；不可缩小的（过多 symbol）仍报错 | 与默认组合：count 用 clamp，symbol 用 error |
| **显式分批 API** | 如 `realtime_batched(...)` / 文档示例循环 | 用户知情地增加请求次数，并仍走 RateGate |

**禁止**在默认的 `realtime()` / `kline()` 内静默拆成多次 HTTP——那会制造「多余请求」且占用限流额度。

`count` 裁切属于「把量改到合规」，默认启用；可在 opts 中提供 `clamp_count=False` 改为超限报错（实现时二选一写清）。

### 4.5 限额模式开关

```text
limits = "enforce" | "off" | "advise"
```

| 值 | 含义 |
|----|------|
| `enforce`（默认） | preflight + RateGate；违规按 §4.3 |
| `off` | 不拦截（调试；仅依赖线上 429 / 错误响应） |
| `advise` | 不拦截，但可记录 warning / 返回 hint（若实现成本低再做；可二期） |

```python
pro = ks.pro_api(limits="enforce")
pro.refresh_limits()     # 强制重新 GET /v1/me
pro.limits.snapshot()    # 只读缓存，便于调试
```

缓存 TTL 建议 5–15 分钟；401/403 时清空；进程内单例挂在 `Client` 上。

### 4.6 请求管线（实现必须挂在统一入口）

所有鉴权 GET（含 `get` / 各业务方法）走同一管线；`health`、纯 `/public/*` 可跳过 auth 与限额。

```text
request(path, params)
  → 确保 LimitsSnapshot（懒加载 me）
  → Policy.resolve(path)           # scope + 限量规则
  → Quota.preflight(path, params)  # 裁切 / 拒绝
  → RateGate.acquire(global, scope)
  → HTTP
  → 成功：记账（次数、symbol 数）
  → 429：校准窗口后抛错
```

`stream` / 未来 WS：在建立连接前检查订阅槽与并发上限；事件流本身不按「每条消息」计 HTTP RPM（除非文档另有规定）。

---

## 5. 传输与请求效率

在遵守 §4 限额的前提下，用传输层与载荷形态降低延迟与带宽。**提效不得绕过限流/限量。**

### 5.1 HTTP 连接复用（Keep-Alive / Session）

| 项 | 约定 |
|----|------|
| 机制 | 使用 `requests.Session()`，复用 TCP/TLS，避免每请求握手 |
| 现状 | `Client` 已创建并持有 `_session`；可注入外部 `session=` |
| 连接池 | 默认 urllib3 池通常够用；高并发时通过 `HTTPAdapter(pool_connections=..., pool_maxsize=...)` mount 到 session |
| 生命周期 | 一个 `Client` 实例长期复用；短生命周期反复 `Client()` 会削弱复用收益 |
| 关闭 | 可选 `close()` / context manager 释放连接（实现时补齐，不破坏现有用法） |

禁止在业务方法里改用裸 `requests.get`，以免丢掉 Session 与统一管线。

### 5.2 gzip（及 deflate / br）响应压缩

| 项 | 约定 |
|----|------|
| 客户端 | 保留 `requests` 默认 `Accept-Encoding`（含 `gzip`、`deflate`，以及环境支持的 `br` 等）；**不要**清掉该头 |
| 解压 | 由 `requests`/urllib3 自动处理；业务层只消费已解压 body |
| 服务端 | 若响应无 `Content-Encoding`，压缩未生效——属网关/API 配置，SDK 无法单方面完成 |
| 自测 | 对大包路径（如 docs、compact 全市场）检查是否出现 `Content-Encoding: gzip`（或 br） |

SDK 侧工程项：初始化 Session 时**显式断言/设置**不得覆盖掉 `Accept-Encoding`；若自定义默认 headers，必须合并而非替换。文档/README 可一句说明「客户端已声明支持 gzip，需服务端开启」。

### 5.3 载荷与往返（与限额配合）

| 手段 | 作用 | 注意 |
|------|------|------|
| compact / v2（如 `realtime_v2`） | 同样数据更小、解析更快 | 权限 scope 可能独立；大包靠 `Accept-Encoding: gzip` |
| v2 kline columnar（`fields` + `symbols`） | SDK 默认展开为行列表 / DataFrame；`raw=True` 保留信封 | 多标的会扁平化并带 `symbol` 列 |
| kline `format="raw"`（SDK 默认） | 极限体积分隔串（`sep`/`row_sep`）；仍展开为行 | 与 SDK `raw=True`（整包信封）无关；`format=None` 可改回服务端列式 |
| 合规范围内的批量 `symbol` | 减少往返 | 不得超过 `max_realtime_symbols` 等；超限按 §4.4 报错，不静默拆批 |
| 避免多余字段 | 不传未开通的 `include_*` | 减少无权限重试与无效负载 |

### 5.4 效率手段一览

| 手段 | 作用 | 状态 |
|------|------|------|
| Session / Keep-Alive | 省 TCP+TLS 握手 | 已有；池参数可配置为增强项 |
| gzip 等 Content-Encoding | 省带宽与传输时间 | 客户端默认支持；服务端需开启 |
| 客户端限流/限量 | 少打无效/超量请求 | Phase B |
| compact / v2 | 更小载荷 | 已封装部分接口 |
| kline `format=raw` | 比列式二维数组更小 | **SDK 对覆盖路径默认开启**；贵金属/期货/美股/板块等未改 |
| 合规批量 symbol | 少往返 | 受 §4 约束 |

### 5.5 实现要点（Checklist）

- [ ] Session 初始化：保留/合并 `Accept-Encoding`，不覆盖 `requests` 默认压缩协商  
- [ ] 可选构造参数：`pool_connections` / `pool_maxsize`（或文档说明如何注入自定义 `session`）  
- [ ] `Client.close()` 或上下文管理器（可选，推荐）  
- [ ] 单测：自定义 headers 时仍包含 gzip 相关 Accept-Encoding  
- [ ] 服务端开启 gzip 后，用 live/手工测大包路径验证 `Content-Encoding`  

---

## 6. 模块与代码结构（目标）

```
src/klineshare/
  __init__.py
  client.py              # 门面：session / request / limits；组合 endpoints mixins
  _params.py             # kline_page_timestamp 等
  endpoints/             # 按域拆分方法（mixin），对外仍是一个 Client
    market.py            # realtime / trend / kline / iter_kline / stock…
    index_etf.py
    topics.py            # limit_up / lhb / moneyflow / streams...
    catalog_bond.py
    meta.py              # health / me / public_*
  limits/
    snapshot.py          # 解析 me / 可选 catalog
    policy.py            # path → 规则
    quota.py             # preflight
    rate.py              # 固定 60s 窗口门闩
    symbol_quota.py      # max_symbols_per_minute
  symbols.py
  compact.py
  errors.py
  _result.py
  _sse.py
```

约束：

- 业务方法只组 params，**不**各自实现限流逻辑  
- 限额逻辑只进 `limits/` 与 `Client.request` / `stream`  
- 纯函数（symbols / compact）保持无 IO，便于单测  

---

## 7. 错误模型

| 类型 | 何时 | 备注 |
|------|------|------|
| `KlineShareError` | 通用失败 | 含 `code` / `http_status` / `body` |
| `KlineShareAuthError` | 缺 Key、401/403 | 已有 |
| `KlineShareRateLimitError` | 429 或本地 RPM 门闩拒绝 | 含 `retry_after` |
| `KlineShareQuotaError`（新增） | 限量 preflight 失败 | 含 `limit_name`、`limit_value`、`got` 等，便于排错 |

消息应可读（中文可接受），并带上限与实际值，避免只写「参数错误」。

---

## 8. 工程与质量

### 8.1 测试

| 层级 | 内容 |
|------|------|
| 单测 | symbols、compact、SSE 解析、unwrap、timestamp 换算、**limits preflight / RateGate**、Session Accept-Encoding（全 mock） |
| 契约（可选） | `@pytest.mark.live` + 真实 Key；默认 CI 不跑 |
| 覆盖检查（二期） | 对照 `llms-full` / `scope_rows`，报告 SDK 未封装 path |

### 8.2 CI

- GitHub Actions：`pytest`，矩阵 Python 3.9–3.12  
- 可选：`ruff` / `mypy`（引入时再写入本文）  

### 8.3 依赖

- 运行时：仅 `requests`  
- 可选：`pandas` extra  
- 不把 `httpx` / 异步客户端塞进默认依赖，除非单独立项  

### 8.4 本地命令

```bash
pip install -e ".[dev]"
pytest
python scripts/check_endpoint_coverage.py --check-gzip
python scripts/gen_api_usage_doc.py            # 在线拉样例并刷新 docs/API_USAGE.md
python scripts/gen_api_usage_doc.py --offline  # 仅用缓存样例
python scripts/gen_api_usage_doc.py --strict
# 真实 Key 冒烟（KLINESHARE_API_KEY）
python scripts/live_smoke.py --quick
python scripts/live_smoke.py --ws --sse --level2
```

用户向 README 只保留安装与用法；本仓开发步骤写在本节与 [RELEASE.md](RELEASE.md)。

---

## 9. 开发阶段（实施顺序）

### Phase A — 开发依据与基线（本文）

- [x] 本文档  
- [x] README 面向用户；开发步骤见本文 §8.4 / RELEASE.md  

### Phase B — 限额骨架（优先）

- [x] `errors.KlineShareQuotaError`  
- [x] `limits.snapshot`：解析 `me`，TTL 缓存，`refresh_limits()`  
- [x] `path → scope` 映射（catalog 或静态表 + me 校验）  
- [x] `Quota.preflight`：`count` 裁切、realtime/kline/trend 标的数量校验、试用 remaining  
- [x] `RateGate`：全局 + scope，固定 60s 窗；429 校准  
- [x] 挂到 `Client.request`；`limits=` / `overflow=` 配置  
- [x] 单测覆盖裁切、拒绝、门闩、校准  
- [x] Session：保留 Accept-Encoding；可选连接池 / `close()`（部分提前完成）  

### Phase C — 结构、传输与 DX

- [x] 拆分 `client.py` → `endpoints/*`  
- [x] 高频方法类型注解 + docstring（参数、限额相关说明）  
- [x] `iter_kline` 等翻页助手（内部走同一管线，占用 RPM）  
- [x] README 补充限额用法说明  

### Phase D — 发布与同步

- [x] CI  
- [x] CHANGELOG、版本策略执行  
- [x] PyPI 发布清单（`docs/RELEASE.md`）  
- [x] SDK 方法与 `scope_rows` 覆盖率检查（`scripts/check_endpoint_coverage.py`）  
- [x] 确认生产网关对大包开启 gzip（脚本 `--check-gzip`；当前若未压缩属服务端项）  

### Phase E — 按需

- [x] `limits="advise"`
- [x] 异步客户端（`AsyncClient` / `asyncio.to_thread`；原生 httpx 另议）
- [x] WS 封装与订阅槽限额（`WebSocketFeed`；可选依赖 `websocket-client`）
- [x] Level2 经 `ks-live` 二进制，通道含 `entrust`；下载 URL 由公开接口 ``GET /public/v1/sdk/ks-live``（带 `sdk_version` / `os` / `arch`）下发
- [x] 日线多标的重负载 `batch="auto"` 拆分
- [x] SSE 走限额管线

- [ ] 显式 `*_batched` 助手 / 原生 async HTTP
- [x] 将 CI coverage `--fail-under` 调高到约定阈值（排除已下线的东财资金流路径后，脚本可达 100% catalog HTTP 面）

---

## 10. 版本与发布

| 级别 | 何时 |
|------|------|
| patch `0.1.x` | 修复、限额收紧、文档、测试 |
| minor `0.2.0` | 默认行为变更（如默认开启 enforce）、新增稳定公开 API |
| major | 删除/重命名公共 API |

发布前：`pytest` 绿、README 示例可运行、`me` 字段解析兼容至少当前生产响应。逐步清单见 [RELEASE.md](RELEASE.md)。

---

## 11. 文档与同步

| 资源 | 用途 |
|------|------|
| 本文 `docs/DEVELOPMENT.md` | SDK 实现依据 |
| `docs/RELEASE.md` | PyPI 发布清单 |
| `CHANGELOG.md` | 用户可见变更 |
| README | 用户向快速开始 |
| `https://data.klineshare.cn/public/v1/docs.md` | 接口契约 |
| `GET /v1/me` | Key 级限额真相 |
| `GET /public/v1/catalog` | 档位与 scope 矩阵 |
| `scripts/check_endpoint_coverage.py` | SDK vs catalog 覆盖率（含 `EXCLUDED_PATHS` 有意不封装路径） |

服务端新增限流维度或 `me` 字段时：**先扩 snapshot 解析与 preflight，再补业务方法**。

### 有意不封装的路径

下列路径仍可能出现在 `GET /public/v1/catalog` 的 `scope_rows` 中，但 **SDK 不提供专用方法**（与 `scripts/check_endpoint_coverage.py` 的 `EXCLUDED_PATHS` 一致）：

| 路径 | 说明 |
|------|------|
| `/v2/moneyflow` / `/v2/moneyflow/em` | 东财资金流 compact（已下线维护） |
| `/v1/moneyflow/ranking/em/stocks` | 东财个股资金流排名 |
| `/v1/moneyflow/ranking/em/snapshot` | 东财资金流排名快照 |
| `/public/v1/moneyflow/ranking/em/catalog` | 东财排名目录（公开元数据） |

替代：实时个股资金流用 `moneyflow_live`（含 `all=True` 全市场）；历史/专题榜用新浪路径 `moneyflow_ranking_*` / `moneyflow_ranking_live_*`。确需调用已下线 HTTP 路径时可用 `pro.get(path, params)`，但不作 SDK 承诺。

---

## 12. 决策记录（ADR 摘要）

| ID | 决策 | 理由 |
|----|------|------|
| D1 | SDK 定位为薄客户端，不含策略/回测 | 与官方 API 同步成本最低 |
| D2 | 限额以 `me` 为准，禁止写死套餐数字 | 套餐动态配置 |
| D3 | 默认 `overflow=error`，不静默多分批 | 避免多余请求与隐性耗尽 RPM |
| D4 | `count` 默认裁切到 `max_count` | 「超量」无收益，本地裁切避免浪费请求 |
| D5 | 限流用固定 60s 窗 | 与公开文档「每分钟」限额表述一致 |
| D6 | 限额逻辑只进统一 `request` 管线 | 防止各 endpoint 行为不一致 |
| D7 | 进程内门闩即可，不承诺分布式限流 | SDK 边界清晰 |
| D8 | 一律经 `Session` 发请求，禁止裸 `requests.get` | Keep-Alive / 连接池 / 统一 headers |
| D9 | 保留默认 `Accept-Encoding`（gzip 等）；压缩开在服务端 | 客户端零成本协商；大包收益高 |
| D10 | 东财资金流（`/v2/moneyflow*`、`/v1/moneyflow/ranking/em/*`）不封装 | 上游不再维护；实时面用 `moneyflow_live` |

变更上述决策时，更新本表并 bump 文档日期。

---

## 13. 文档维护

- 负责人：KlineShare SDK 维护者  
- 更新日期：2026-10-25  
- 修订方式：行为变更先改本文与测试，再改代码；PR 需注明是否触及 §4 / §5 / §12；跨仓 HEAD 只写本地 `VERSION_BASELINE.local.md`  
