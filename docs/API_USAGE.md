# KlineShare SDK — 使用说明

本文分两部分：**通用说明**，以及**全接口参考**（每个接口列出用法与进阶用法）。

快速开始见 [README.md](../README.md)；实现约定见 [DEVELOPMENT.md](DEVELOPMENT.md)。

---

## 1. 这是什么

官方 Python 客户端，调用 [KlineShare](https://klineshare.cn) 数据 API：
实时 / 分时 / K线、涨停与资金流专题、债券与扩展市场、推流 / 行情订阅 / Level2。

- 方法名贴近 REST 路径（如 `pro.kline` → `GET /v2/kline`）
- 自动鉴权、标的规范化、紧凑格式展开、可选 DataFrame
- 默认在客户端遵守套餐限额（count / 标的数 / RPM）

---

## 2. 安装与鉴权

```bash
pip install klineshare
pip install "klineshare[pandas]"   # 结果转 DataFrame
pip install "klineshare[ws]"       # WebSocket
```

在用户中心创建 API Key（`tg_...`），任选一种方式：

```python
import klineshare as ks

# 方式 A：代码里设置 Key，再创建客户端
ks.set_api_key("tg_your_key")
pro = ks.pro_api()

# 方式 B：事先 export KLINESHARE_API_KEY=tg_...（可选 KLINESHARE_BASE_URL）
# 此时不用 set_api_key，pro_api() 会自动读环境变量
pro = ks.pro_api()

# 方式 C：构造时显式传入
pro = ks.Client(api_key="tg_xxx", base_url="https://data.klineshare.cn")
```

查看当前 Key 权限与限额：

```python
print(pro.me())
pro.refresh_limits()
print(pro.limits.summary())
```

---

## 3. 标的代码

标准后缀：`600519.SS` / `000001.SZ` / `920000.BJ` / `AAPL.US`。

| 输入 | 发出请求时 |
|------|------------|
| `600519.SH` | `600519.SS` |
| `sh600519` | `600519.SS` |
| `600519` | `600519.SS`（按首位推断） |
| `ks_code=` | 与 `symbol=` 相同规则 |

按资产选择对应方法：个股 `kline`，指数 `index_kline`，ETF `etf_kline`，北交所 `bj_kline`，可转债 `convertible_kline` 等。

贵金属 / 期货 / 全球指数与债券一般不加 `.US` 后缀。

---

## 4. 返回值与通用参数

几乎所有 HTTP 方法都接受 `**opts`：

| 参数 | 含义 |
|------|------|
| `raw=True` | 返回完整 JSON 信封，不解包 `data` |
| `as_dataframe=False` | 返回 list / dict，不转 DataFrame |
| `expand_compact_rows=False` | 关闭 v2 紧凑格式自动展开 |
| `auth=False` | 不带 Key（公开接口） |
| `skip_limits=True` | 跳过客户端限额预检 |

默认：解包接口里的 `data`；列表尽量转成 pandas DataFrame（需安装 `pandas` 或 `klineshare[pandas]`）。

```python
df = pro.kline(symbol="600519.SS", period=86400, count=10)
rows = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)
envelope = pro.kline(symbol="600519.SS", period=86400, count=10, raw=True)
```

`realtime_v2` / `auction_v2` 等紧凑格式接口默认展开为行；全市场写法见 §8。

---

## 5. K 线用法

个股 / 指数 / ETF K 线走 v2 路径：`kline` / `index_kline` / `etf_kline`。

```python
bars = pro.kline(
    symbol="600519.SH",          # 自动规范为 .SS
    period=86400,                # 秒；日线=86400
    adjust_type="forward",
    count=100,
)
```

要点：

1. **`format`**：默认 `"raw"`（服务端极限体积分隔串；SDK 仍展开为行 / DataFrame）。传 `format=None` 使用服务端列式数组。与 `raw=True`（完整 JSON 信封）无关。
2. **翻页**：请求参数 `timestamp` 为秒；条内字段 `timestamp` 是毫秒。传入毫秒时 SDK 会自动换成秒。
3. **`iter_kline`**：自动向更早翻页，逐页 yield。
4. **`batch`**：`multi`（默认）/ `single` / `auto`（日线及以上且标的数×count 过大时按标的拆分，默认阈值 3000）。

```python
bars = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)
older = pro.kline(
    symbol="600519.SS",
    period=86400,
    count=10,
    timestamp=min(b["timestamp"] for b in bars) - 1,
)
for page in pro.iter_kline(symbol="600519.SS", period=86400, count=10, max_pages=5):
    print(len(page))
```

---

## 6. 限额与错误

默认 `limits="enforce"`：按 `GET /v1/me` 缓存套餐上限，发请求前裁切 `count`、校验标的数 / 试用额度，并做本地 RPM 门闩。

| 模式 | 行为 |
|------|------|
| `enforce`（默认） | 超额本地报错 / 裁切 |
| `advise` | 裁切并写入 `pro.limit_advice`，仍尽量请求 |
| `off` | 关闭客户端限额 |

```python
pro = ks.pro_api(limits="enforce", on_rate_limit="wait", kline_batch="auto")
```

| 异常 | 含义 |
|------|------|
| `KlineShareAuthError` | Key 缺失 / 无效 / 权限不足 |
| `KlineShareRateLimitError` | HTTP 429 或本地 RPM 门闩 |
| `KlineShareQuotaError` | 客户端量预检失败（未发请求） |
| `KlineShareError` | 其他 API / 客户端错误 |

---

## 7. 实时流：推流 / 行情订阅 / Level2

**服务端推流**

```python
for ev in pro.abnormal_events_stream():
    print(ev)
    break
```

**行情订阅**（需 `klineshare[ws]`）

```python
with pro.realtime_ws(symbol="600519.SS") as feed:
    for msg in feed:
        if msg.get("type") == "tick":
            print(msg)
            break
```

**Level2**

```python
with pro.level2(symbol="600519.SS", channels="depth,trades,entrust") as feed:
    for msg in feed:
        print(msg)
        break
```

---

## 8. 全市场紧凑格式（realtime_v2 / auction_v2 等）

下列接口支持一次拉取全市场紧凑快照：

| 方法 | 路径 | 用法 |
|------|------|------|
| `realtime_v2` | `/v2/realtime` | `all=True, market="SS"` |
| `auction_v2` | `/v2/auction` | `all=True`，可加 `market` / `include_minutes` |
| `convertible_auction_v2` | `/v2/convertible/auction` | `all=True` |
| `moneyflow_live` | `/v1/moneyflow/live` | `all=True` 或批量 `symbol` |

对照：

| 场景 | 方法 |
|------|------|
| 个股实时 / 竞价分时 | `realtime` / `auction` |
| 全市场快照 | `realtime_v2` / `auction_v2` |

`all=True` 时服务端返回紧凑格式；SDK 默认展开为行 / DataFrame。需要原始结构时传 `expand_compact_rows=False`。

```python
# 用法：全市场
df = pro.realtime_v2(all=True, market="SS")
df = pro.realtime_v2(
    all=True, market="SZ",
    include_valuation=True, include_depth=True,
)
auc = pro.auction_v2(all=True, market="SS")
auc_m = pro.auction_v2(all=True, include_minutes=True)
mf = pro.moneyflow_live(all=True)
cb = pro.convertible_auction_v2(all=True)
```

```python
# 进阶用法：按标的过滤
pro.realtime_v2(symbol="600519.SS")
pro.realtime_v2(symbol=["600519.SS", "000001.SZ"])
pro.auction_v2(symbol="600519.SS")
```

全市场包较大，对应独立 scope（如 `realtime_v2` / `auction_v2`），权限见 `pro.me()`。实时个股资金流全市场见 `moneyflow_live(all=True)`。

---

## 9. 专题提示

- **资金流板块榜** `moneyflow_ranking_boards` 需传 `category`（如 `industry` / `concept` / `csrc_industry`），可先查 `moneyflow_ranking_catalog()`。
- 龙虎榜 / 游资 / 涨停等方法名与路径一致，见下方「全接口参考」。

---

## 10. 通用请求

```python
pro.get("/v1/health")
pro.get("/v2/kline", params={"symbol": "600519.SS", "period": 86400, "count": 5})
pro.request_text("/public/v1/docs.md")
for ev in pro.stream("/v1/abnormal-events/stream"):
    ...
```

---

## 11. 工厂与模块级 API

```python
import klineshare as ks

ks.set_api_key("tg_...")
pro = ks.pro_api()                    # 或 Client(...)
ks.normalize_symbol("600519.SH")     # → 600519.SS
```

---

## 全接口参考

每个接口分两档，尽量穷尽可调用方式：

| 档位 | 含义 |
|------|------|
| **用法** | 基本调用与常用参数别名（如 `symbol` / `ks_code`、`all=True`） |
| **进阶用法** | 附加字段、返回形态（`raw` / DataFrame）、翻页、批量、紧凑格式展开等 |

每个接口另附 **数据样例** 与 **字段说明**；列表与嵌套对象优先用表格展示。

通用 `**opts`：`raw` / `as_dataframe` / `expand_compact_rows` / `auth` / `skip_limits`。

**统计：** 179 个接口；用法示例 191 段；进阶用法示例 514 段；数据样例 97 个。

## 元数据 / 公开文档

### `health`

- **路径：** `/v1/health`
- **类型：** http
- **说明：** 服务健康检查
- **签名：** `pro.health(**opts)`

**用法**

- 基本调用

```python
pro.health()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.health(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.health(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `success` | True |
| `version` | 1 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `success` | 是否成功 | True |
| `version` | 版本 | 1 |

### `me`

- **路径：** `/v1/me`
- **类型：** http
- **说明：** 当前密钥权限与限额
- **签名：** `pro.me(**opts)`
- **介绍：** 当前 Key 权限与限额 `GET /v1/me`（也是客户端限额缓存的数据源）。

**用法**

- 基本调用

```python
pro.me()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.me(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.me(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `account` | *** |
| `key` | *** |
| `level2_channels` | ["depth", "orders", "trades"] |
| `live_kline_bar_quota_note` | source=live 时按「标的数×count」合计，同一分钟内不可超过此根数 |
| `max_abnormal_events_subscriptions` | 2 |
| `max_futures_stream_subscriptions` | 0 |
| `max_level2_slots` | 1280 |
| `max_level2_subscriptions` | 5 |
| `max_level2_symbols` | 1280 |
| `max_live_kline_bars_per_minute` | 500000 |
| `max_market_flash_subscriptions` | 2 |
| `max_realtime_stream_subscriptions` | 0 |
| `max_realtime_stream_symbols` | 0 |
| `max_realtime_symbols` | 200 |
| `max_symbols_per_minute` | 6000 |
| `rate_limit_per_minute` | 3000 |
| `success` | True |
| `symbol_quota_note` | 实时/分时/分钟 K 线/ETF 同类接口共用，同一分钟内不同品种数上限 |

**`endpoint_access_status` 展开（20 条）**

| `access_mode` | `allowed` | `exhausted` | `group_id` | `group_label` | `id` | `label` | `max_uses` | `path` | `period_days` | `remaining` | `scope` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trial | True | False | live_compact | 全市场实时（compact） | realtime_v2_cn | A 股全市场 / 批量 | 30 | /v2/realtime | 1 | 26 | realtime_v2 |
| trial | True | False | live_compact | 全市场实时（compact） | realtime_v2_us | 美股全市场 / 批量 | 30 | /v2/realtime | 1 | 30 | realtime_v2 |
| trial | True | False | live_compact | 全市场实时（compact） | auction_v2 | 集合竞价全市场 / 批量 | 30 | /v2/auction | 1 | 26 | auction_v2 |
| locked | False |  | live_compact | 全市场实时（compact） | moneyflow_em_v2 | 东财资金流全市场 / 批量 |  | /v2/moneyflow/em |  |  | moneyflow_em_v2 |
| full | True |  | hs_quote | 沪深行情（实时） | realtime | 实时行情 |  | /v1/realtime |  |  | realtime |

（共 20 行，表中展示前 5 行、前 12/16 列）

**`kline` 展开**

| 字段 | 值 |
|------|-----|
| `adjust_types` | ["forward", "backward", "none"] |
| `allow_pagination` | True |
| `allowed_indicators` | ["ma", "ema", "rsi", "macd", "boll"] |
| `allowed_indicators_label` | 简单移动平均线 MA、指数移动平均线 EMA、相对强弱指标 RSI、MACD、布林带 BOLL |
| `max_count` | 2000 |
| `max_indicator_specs` | 8 |
| `max_minute_count` | 240 |
| `periods_label` | 1分钟、5分钟、15分钟、30分钟、60分钟、日线、周线、月线 |
| `plan` | 免费版 |

**`market_flash_trial` 展开**

| 字段 | 值 |
|------|-----|
| `daily_limit` | 1 |
| `max_uses` | 1 |
| `mode` | trial |
| `period_days` | 1 |

**`endpoints` 展开（1 条）**

| `exhausted` | `id` | `label` | `max_uses` | `path` | `period_days` | `remaining` | `used_today` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| False | market_flash_stream | 快讯实时订阅 | 1 | /v1/market-flash/stream | 1 | 1 | 0 |

**`rate_limit` 展开**

| 字段 | 值 |
|------|-----|
| `requests` | 3000 |
| `requests_per_minute` | 3000 |
| `window_minutes` | 1 |

**`realtime_feature_gates` 展开（2 条）**

| `description` | `label` | `param` | `routes` |
| --- | --- | --- | --- |
| PE/PB/市值、昨收、换手率、振幅、量比等 | 实时估值扩展 | include_valuation | {"etf_realtime": {"scope": "etf_realtime_valuat… |
| bid/ask 五档及内外盘成交量 | 买卖五档 | include_depth | {"etf_realtime": {"scope": "etf_realtime_depth"… |

**`scopes` 展开（20 条）**

| `allowed` | `name` | `rate_limit` | `rate_limit_per_minute` | `scope` |
| --- | --- | --- | --- | --- |
| True | 站内板块K线 | {"requests": 400, "requests_per_minute": 400, "… | 400 | plate_kline |
| True | 市场快讯 | {"requests": 10, "requests_per_minute": 10, "wi… | 10 | market_flash |
| True | 实时五档行情 | {"requests": 100, "requests_per_minute": 100, "… | 100 | realtime_depth |
| True | 上市公司资料 | {"requests": 600, "requests_per_minute": 600, "… | 600 | corp |
| True | ETF实时估值 | {"requests": 100, "requests_per_minute": 100, "… | 100 | etf_realtime_valuation |

（共 20 行，表中展示前 5 行）

**`subscription_summary` 展开**

| 字段 | 值 |
|------|-----|
| `effective_plan` | 旗舰版 |
| `effective_role_id` | premium_v2 |
| `main_expires_at` | 2026-10-21T00:30:23 |
| `main_plan` | 旗舰版 |
| `main_role_id` | premium_v2 |
| `subscription_active` | True |
| `symbol_quota_base` | 6000 |
| `symbol_quota_stacks` | 1 |
| `symbol_quota_total` | 6000 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `account` | 账号信息（文档已脱敏） | *** |
| `endpoint_access_status` | 接口权限状态 | [20 项，见下方展开] |
| `key` | 密钥信息（文档已脱敏） | *** |
| `kline` | K 线能力说明 | {9 字段，见下方展开} |
| `level2_channels` | Level2 频道 | ["depth", "orders", "trades"] |
| `live_kline_bar_quota_note` | 实时 K 线额度说明 | source=live 时按「标的数×count」合计，同一分钟内不可超过此根数 |
| `market_flash_trial` | 市场快讯试用额度 | {5 字段，见下方展开} |
| `max_abnormal_events_subscriptions` | 异动事件最大订阅数 | 2 |
| `max_futures_stream_subscriptions` | 期货推流最大订阅数 | 0 |
| `max_level2_slots` | Level2 最大槽位 | 1280 |
| `max_level2_subscriptions` | Level2 最大订阅数 | 5 |
| `max_level2_symbols` | Level2 最大标的数 | 1280 |
| `max_live_kline_bars_per_minute` | 每分钟实时 K 线条数上限 | 500000 |
| `max_market_flash_subscriptions` | 市场快讯最大订阅数 | 2 |
| `max_realtime_stream_subscriptions` | 实时推流最大订阅数 | 0 |
| `max_realtime_stream_symbols` | 实时推流最大标的数 | 0 |
| `max_realtime_symbols` | 实时行情最大标的数 | 200 |
| `max_symbols_per_minute` | 每分钟最大标的数 | 6000 |
| `rate_limit` | 限速配置 | {3 字段，见下方展开} |
| `rate_limit_per_minute` | 每分钟请求上限 | 3000 |
| `realtime_feature_gates` | 实时附加字段门控 | [2 项，见下方展开] |
| `scopes` | 权限范围 | [20 项，见下方展开] |
| `subscription_summary` | 订阅摘要 | {9 字段，见下方展开} |
| `success` | 是否成功 | True |
| `symbol_quota_note` | 标的配额说明 | 实时/分时/分钟 K 线/ETF 同类接口共用，同一分钟内不同品种数上限 |
| `endpoint_access_status.access_mode` | 接口权限状态 → 访问模式（trial/locked/open） | trial |
| `endpoint_access_status.allowed` | 接口权限状态 → 是否允许 | True |
| `endpoint_access_status.exhausted` | 接口权限状态 → 是否用尽 | False |
| `endpoint_access_status.group_id` | 接口权限状态 → 分组编号 | live_compact |
| `endpoint_access_status.group_label` | 接口权限状态 → 分组名称 | 全市场实时（compact） |
| `endpoint_access_status.id` | 接口权限状态 → 编号 | realtime_v2_cn |
| `endpoint_access_status.label` | 接口权限状态 → 标签 | A 股全市场 / 批量 |
| `endpoint_access_status.max_uses` | 接口权限状态 → 最大次数 | 30 |
| `endpoint_access_status.path` | 接口权限状态 → 路径 | /v2/realtime |
| `endpoint_access_status.period_days` | 接口权限状态 → 周期天数 | 1 |
| `endpoint_access_status.remaining` | 接口权限状态 → 剩余次数 | 26 |
| `endpoint_access_status.scope` | 接口权限状态 → 范围 | realtime_v2 |
| `endpoint_access_status.used_in_window` | 接口权限状态 → 窗口内已用 | 4 |
| `endpoint_access_status.expires_at` | 接口权限状态 → expires（时间） |  |
| `endpoint_access_status.rate_limit` | 接口权限状态 → 限速配置 |  |
| `endpoint_access_status.rate_limit_label` | 接口权限状态 → rate_limit（说明） |  |
| `kline.adjust_types` | K 线能力说明 → 可用复权类型 | ["forward", "backward", "none"] |
| `kline.allow_pagination` | K 线能力说明 → 是否支持分页 | True |
| `kline.allowed_indicators` | K 线能力说明 → 允许的附加指标 | ["ma", "ema", "rsi", "macd", "boll"] |
| `kline.allowed_indicators_label` | K 线能力说明 → 附加指标说明 | 简单移动平均线 MA、指数移动平均线 EMA、相对强弱指标 RSI、MACD、布林带 BOLL |
| `kline.max_count` | K 线能力说明 → 最大条数 | 2000 |
| `kline.max_indicator_specs` | K 线能力说明 → 最大指标规格数 | 8 |
| `kline.max_minute_count` | K 线能力说明 → 分钟线最大条数 | 240 |
| `kline.periods_label` | K 线能力说明 → 周期说明 | 1分钟、5分钟、15分钟、30分钟、60分钟、日线、周线、月线 |
| `kline.plan` | K 线能力说明 → 套餐 | 免费版 |
| `market_flash_trial.daily_limit` | 市场快讯试用额度 → 日限额 | 1 |
| `market_flash_trial.endpoints` | 市场快讯试用额度 → 接口列表 | [1 项，见下方展开] |
| `market_flash_trial.max_uses` | 市场快讯试用额度 → 最大次数 | 1 |
| `market_flash_trial.mode` | 市场快讯试用额度 → 模式 | trial |
| `market_flash_trial.period_days` | 市场快讯试用额度 → 周期天数 | 1 |
| `market_flash_trial.endpoints.exhausted` | 市场快讯试用额度 → 字段 `endpoints.exhausted` |  |
| `market_flash_trial.endpoints.id` | 市场快讯试用额度 → 字段 `endpoints.id` |  |
| `market_flash_trial.endpoints.label` | 市场快讯试用额度 → 字段 `endpoints.label` |  |
| `market_flash_trial.endpoints.max_uses` | 市场快讯试用额度 → 字段 `endpoints.max_uses` |  |
| `market_flash_trial.endpoints.path` | 市场快讯试用额度 → 字段 `endpoints.path` |  |

（共 84 个字段，表中展示前 60 个）

### `public_catalog`

- **路径：** `/public/v1/catalog`
- **类型：** http
- **说明：** 公开目录/档位
- **签名：** `pro.public_catalog(**opts)`

**用法**

- 基本调用

```python
pro.public_catalog()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_catalog(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_catalog(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `success` | True |
| `tier_compare_note` | v2 套餐：实时接口每分钟次数与 v1 同级；另设全局每分钟不同品种数上限（实时/分时/分钟 … |

**`api_surface` 展开（20 条）**

| `id` | `items` | `label` |
| --- | --- | --- |
| live_compact | [4 项，见下方展开] | 全市场实时（compact） |
| hs_quote | [6 项，见下方展开] | 沪深行情（实时） |
| bj_quote | [2 项，见下方展开] | 北交所行情（历史） |
| hsbj | [2 项，见下方展开] | 沪深京 |
| level2 | [1 项，见下方展开] | Level2 |

（共 20 行，表中展示前 5 行）

**`market_indices` 展开（10 条）**

| `group` | `is_primary` | `name` | `quote_ready` | `symbol` | `futures` |
| --- | --- | --- | --- | --- | --- |
| 宽基 | True | 深证成指 | True | 399001.SZ |  |
| 宽基 | True | 创业板指 | True | 399006.SZ |  |
| 宽基 | False | 沪深300 | True | 000300.SS | IF |
| 宽基 | False | 上证50 | True | 000016.SS | IH |
| 宽基 | False | 中证500 | True | 000905.SS | IC |

（共 10 行，表中展示前 5 行）

**`realtime_batch_limits` 展开（3 条）**

| `max_symbols` | `tier_id` | `tier_name` |
| --- | --- | --- |
| 80 | basic_v2 | 基础版 |
| 160 | pro_v2 | 专业版 |
| 200 | premium_v2 | 旗舰版 |

**`realtime_feature_gates` 展开（2 条）**

| `description` | `label` | `param` | `routes` |
| --- | --- | --- | --- |
| PE/PB/市值、昨收、换手率、振幅、量比等 | 实时估值扩展 | include_valuation | {"etf_realtime": {"scope": "etf_realtime_valuat… |
| bid/ask 五档及内外盘成交量 | 买卖五档 | include_depth | {"etf_realtime": {"scope": "etf_realtime_depth"… |

**`register_roles` 展开（4 条）**

| `id` | `name` | `tier_version` |
| --- | --- | --- |
| basic_v2 | 基础版 | 2 |
| pro_v2 | 专业版 | 2 |
| premium_v2 | 旗舰版 | 2 |
| cn_fut | 国内期货 | 1 |

**`scope_rows` 展开（20 条）**

| `availability` | `id` | `name` | `path` | `required_plan` | `scope` | `tier_names` | `tier_names_trial` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [4 项，见下方展开] | realtime | 实时行情 | /v1/realtime | 基础版 | realtime | ["基础版", "专业版", "旗舰版"] | [] |
| [4 项，见下方展开] | kline_v2 | K 线 v2 | /v2/kline | 基础版 | kline | ["基础版", "专业版", "旗舰版"] | [] |
| [4 项，见下方展开] | kline | K 线（过时） | /v1/kline | 基础版 | kline | ["基础版", "专业版", "旗舰版"] | [] |
| [4 项，见下方展开] | bj_kline | K 线 | /v1/bj/kline | 基础版 | kline | ["基础版", "专业版", "旗舰版"] | [] |
| [4 项，见下方展开] | adjust_factors | 复权因子 | /v1/adjust-factors | 基础版 | kline | ["基础版", "专业版", "旗舰版"] | [] |

（共 20 行，表中展示前 5 行）

**`symbol_quota_limits` 展开（3 条）**

| `max_symbols_per_minute` | `tier_id` | `tier_name` | `tier_version` |
| --- | --- | --- | --- |
| 1500 | basic_v2 | 基础版 | 2 |
| 2500 | pro_v2 | 专业版 | 2 |
| 6000 | premium_v2 | 旗舰版 | 2 |

**`tier_columns` 展开（4 条）**

| `id` | `name` | `tier_version` |
| --- | --- | --- |
| basic_v2 | 基础版 | 2 |
| pro_v2 | 专业版 | 2 |
| premium_v2 | 旗舰版 | 2 |
| cn_fut | 国内期货 | 1 |

**`tier_poster` 展开**

| 字段 | 值 |
|------|-----|
| `visible_keys` | ["periods", "max_count", "adjust", "indicators"… |

**`items` 展开（20 条）**

| `key` | `kind` | `label` | `endpoint_id` | `group` | `path` | `scope` |
| --- | --- | --- | --- | --- | --- | --- |
| *** | limit | K 线周期 |  |  |  |  |
| *** | limit | 单次条数 |  |  |  |  |
| *** | limit | 复权 |  |  |  |  |
| *** | limit | 技术指标 |  |  |  |  |
| *** | limit | 实时批量 |  |  |  |  |

（共 20 行，表中展示前 5 行）

**`tiers` 展开（4 条）**

| `cells` | `id` | `name` | `tier_rank` |
| --- | --- | --- | --- |
| [20 项，见下方展开] | basic_v2 | 基础版 | 1 |
| [20 项，见下方展开] | pro_v2 | 专业版 | 2 |
| [20 项，见下方展开] | premium_v2 | 旗舰版 | 3 |
| [20 项，见下方展开] | cn_fut | 国内期货 | 99 |

**`tiers` 展开（4 条）**

| `adjust_types` | `allowed_indicators_label` | `description` | `discount_label` | `discount_percent` | `id` | `max_count` | `max_realtime_symbols` | `max_symbols_per_minute` | `name` | `original_price` | `original_price_display` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ["forward", "backward", "none"] | 简单移动平均线 MA、指数移动平均线 EMA、相对强弱指标 RSI、MACD、布林带 BOLL | 基础版：全周期实时K线，可试用部分旗舰版功能 | 限时特惠 | 50 | basic_v2 | 1000 | 80 | 1500 | 基础版 | 199 | ¥199 |
| ["forward", "backward", "none"] | 简单移动平均线 MA、指数移动平均线 EMA、相对强弱指标 RSI、MACD、布林带 BOLL | 专业版：全周期实时K线， ETF 专用接口；打板/异动/快讯各接口日试用 2 次； | 限时特惠 | 33 | pro_v2 | 1500 | 160 | 2500 | 专业版 | 299 | ¥299 |
| ["forward", "backward", "none"] | 简单移动平均线 MA、指数移动平均线 EMA、相对强弱指标 RSI、MACD、布林带 BOLL | 旗舰版：全能力顶格；全局每分钟最多查询 3000 个不同品种（可叠加扩容） | 限时特惠 | 43 | premium_v2 | 2000 | 200 | 6000 | 旗舰版 | 699 | ¥699 |
| ["forward", "backward", "none"] | 简单移动平均线 MA、指数移动平均线 EMA、相对强弱指标 RSI、MACD、布林带 BOLL | 国内期货行情数据接口，支持tick级数据推送 | 限时特惠 | 60 | cn_fut | 500 |  |  | 国内期货 | 999 | ¥999 |

（共 4 行、前 12/22 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `api_surface` | API 能力面 | [20 项，见下方展开] |
| `market_indices` | 市场指数清单 | [10 项，见下方展开] |
| `realtime_batch_limits` | 实时批量上限 | [3 项，见下方展开] |
| `realtime_feature_gates` | 实时附加字段门控 | [2 项，见下方展开] |
| `register_roles` | 可注册角色 | [4 项，见下方展开] |
| `scope_rows` | 权限明细行 | [20 项，见下方展开] |
| `success` | 是否成功 | True |
| `symbol_quota_limits` | 标的配额明细 | [3 项，见下方展开] |
| `tier_columns` | 套餐对比列 | [4 项，见下方展开] |
| `tier_compare_note` | 套餐对比说明 | v2 套餐：实时接口每分钟次数与 v1 同级；另设全局每分钟不同品种数上限（实时/分时/分钟 … |
| `tier_poster` | 档位海报 | {3 字段，见下方展开} |
| `tiers` | 套餐档位 | [4 项，见下方展开] |
| `api_surface.id` | API 能力面 → 编号 | live_compact |
| `api_surface.items` | API 能力面 → 条目列表 | [4 项，见下方展开] |
| `api_surface.label` | API 能力面 → 标签 | 全市场实时（compact） |
| `market_indices.group` | 市场指数清单 → 分组 | 宽基 |
| `market_indices.is_primary` | 市场指数清单 → 是否主条目 | True |
| `market_indices.name` | 市场指数清单 → 名称 | 深证成指 |
| `market_indices.quote_ready` | 市场指数清单 → 行情是否就绪 | True |
| `market_indices.symbol` | 市场指数清单 → 标的代码 | 399001.SZ |
| `market_indices.futures` | 市场指数清单 → 期货 |  |
| `realtime_batch_limits.max_symbols` | 实时批量上限 → 最大标的数 | 80 |
| `realtime_batch_limits.tier_id` | 实时批量上限 → 套餐档位 ID | basic_v2 |
| `realtime_batch_limits.tier_name` | 实时批量上限 → 套餐档位名 | 基础版 |
| `realtime_feature_gates.description` | 实时附加字段门控 → 描述 | PE/PB/市值、昨收、换手率、振幅、量比等 |
| `realtime_feature_gates.label` | 实时附加字段门控 → 标签 | 实时估值扩展 |
| `realtime_feature_gates.param` | 实时附加字段门控 → 参数 | include_valuation |
| `realtime_feature_gates.routes` | 实时附加字段门控 → 路由 | {"etf_realtime": {"scope": "etf_realtime_valuat… |
| `register_roles.id` | 可注册角色 → 编号 | basic_v2 |
| `register_roles.name` | 可注册角色 → 名称 | 基础版 |
| `register_roles.tier_version` | 可注册角色 → 档位版本 | 2 |
| `scope_rows.availability` | 权限明细行 → 可用性 | [4 项，见下方展开] |
| `scope_rows.id` | 权限明细行 → 编号 | realtime |
| `scope_rows.name` | 权限明细行 → 名称 | 实时行情 |
| `scope_rows.path` | 权限明细行 → 路径 | /v1/realtime |
| `scope_rows.required_plan` | 权限明细行 → 所需套餐 | 基础版 |
| `scope_rows.scope` | 权限明细行 → 范围 | realtime |
| `scope_rows.tier_names` | 权限明细行 → 档位名称列表 | ["基础版", "专业版", "旗舰版"] |
| `scope_rows.tier_names_trial` | 权限明细行 → 试用档位名 | [] |
| `symbol_quota_limits.max_symbols_per_minute` | 标的配额明细 → 每分钟最大标的数 | 1500 |
| `symbol_quota_limits.tier_id` | 标的配额明细 → 套餐档位 ID | basic_v2 |
| `symbol_quota_limits.tier_name` | 标的配额明细 → 套餐档位名 | 基础版 |
| `symbol_quota_limits.tier_version` | 标的配额明细 → 档位版本 | 2 |
| `tier_columns.id` | 套餐对比列 → 编号 | basic_v2 |
| `tier_columns.name` | 套餐对比列 → 名称 | 基础版 |
| `tier_columns.tier_version` | 套餐对比列 → 档位版本 | 2 |
| `tier_poster.items` | 档位海报 → 条目列表 | [20 项，见下方展开] |
| `tier_poster.tiers` | 档位海报 → 套餐档位 | [4 项，见下方展开] |
| `tier_poster.visible_keys` | 档位海报 → 可见字段 | ["periods", "max_count", "adjust", "indicators"… |
| `tier_poster.items.key` | 档位海报 → 字段 `items.key` |  |
| `tier_poster.items.kind` | 档位海报 → 字段 `items.kind` |  |
| `tier_poster.items.label` | 档位海报 → 字段 `items.label` |  |
| `tier_poster.items.endpoint_id` | 档位海报 → items.endpoint（编号） |  |
| `tier_poster.items.group` | 档位海报 → 字段 `items.group` |  |
| `tier_poster.items.path` | 档位海报 → 字段 `items.path` |  |
| `tier_poster.items.scope` | 档位海报 → 字段 `items.scope` |  |
| `tier_poster.tiers.cells` | 档位海报 → 字段 `tiers.cells` |  |
| `tier_poster.tiers.id` | 档位海报 → 字段 `tiers.id` |  |
| `tier_poster.tiers.name` | 档位海报 → 字段 `tiers.name` |  |
| `tier_poster.tiers.tier_rank` | 档位海报 → 字段 `tiers.tier_rank` |  |

（共 82 个字段，表中展示前 60 个）

### `public_indices`

- **路径：** `/public/v1/indices`
- **类型：** http
- **说明：** 公开指数列表
- **签名：** `pro.public_indices(*, keyword=None, listed=None, limit=None, quote_ready=None, **opts)`

**用法**

- 基本调用

```python
pro.public_indices(limit=5)
```

**进阶用法**

- 进阶参数组合

```python
pro.public_indices(keyword='沪深', listed=True)
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_indices(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_indices(limit=5, as_dataframe=False)
```

**数据样例**

| `group` | `is_primary` | `name` | `quote_ready` | `symbol` | `futures` |
| --- | --- | --- | --- | --- | --- |
| 宽基 | True | 深证成指 | True | 399001.SZ |  |
| 宽基 | True | 创业板指 | True | 399006.SZ |  |
| 宽基 | False | 沪深300 | True | 000300.SS | IF |
| 宽基 | False | 上证50 | True | 000016.SS | IH |
| 宽基 | False | 中证500 | True | 000905.SS | IC |

（共 10 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `group` | 分组 | 宽基 |
| `is_primary` | 是否主条目 | True |
| `name` | 名称 | 深证成指 |
| `quote_ready` | 行情是否就绪 | True |
| `symbol` | 标的代码 | 399001.SZ |
| `futures` | 期货 |  |

### `public_metals`

- **路径：** `/public/v1/metals`
- **类型：** http
- **说明：** 贵金属公开清单
- **签名：** `pro.public_metals(*, keyword=None, group=None, limit=None, **opts)`
- **介绍：** 贵金属公开清单 `GET /public/v1/metals`。

**用法**

- 基本调用

```python
pro.public_metals(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_metals(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_metals(limit=5, as_dataframe=False)
```

- 关键词搜索

```python
pro.public_metals(limit=5, keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `public_futures`

- **路径：** `/public/v1/futures`
- **类型：** http
- **说明：** 期货 v1 公开清单
- **签名：** `pro.public_futures(*, exchange=None, keyword=None, limit=None, **opts)`
- **介绍：** 国内期货 v1 公开清单 `GET /public/v1/futures`。

**用法**

- 基本调用

```python
pro.public_futures(keyword='黄金', limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_futures(keyword='黄金', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_futures(keyword='黄金', limit=5, as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `public_futures_v2`

- **路径：** `/public/v1/futures-v2`
- **类型：** http
- **说明：** 期货 v2 公开清单
- **签名：** `pro.public_futures_v2(*, exchange=None, keyword=None, limit=None, **opts)`
- **介绍：** 国内期货 v2 公开清单 `GET /public/v1/futures-v2`。

**用法**

- 基本调用

```python
pro.public_futures_v2(exchange='SHFE')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_futures_v2(exchange='SHFE', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_futures_v2(exchange='SHFE', as_dataframe=False)
```

- 关键词搜索

```python
pro.public_futures_v2(exchange='SHFE', keyword='茅台')
```

- 返回条数上限

```python
pro.public_futures_v2(exchange='SHFE', limit=20)
```

**数据样例**

暂无可用样例：无样例

### `public_global_indices`

- **路径：** `/public/v1/global-indices`
- **类型：** http
- **说明：** 全球指数公开清单
- **签名：** `pro.public_global_indices(*, keyword=None, group=None, listed=None, limit=None, **opts)`
- **介绍：** 全球指数公开清单 `GET /public/v1/global-indices`。

**用法**

- 基本调用

```python
pro.public_global_indices(keyword='道指', limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_global_indices(keyword='道指', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_global_indices(keyword='道指', limit=5, as_dataframe=False)
```

- 仅已上市

```python
pro.public_global_indices(keyword='道指', limit=5, listed=True)
```

**数据样例**

暂无可用样例：无样例

### `public_global_bonds`

- **路径：** `/public/v1/global-bonds`
- **类型：** http
- **说明：** 国际债券公开清单
- **签名：** `pro.public_global_bonds(*, keyword=None, group=None, listed=None, limit=None, **opts)`
- **介绍：** 国际债券公开清单 `GET /public/v1/global-bonds`。

**用法**

- 基本调用

```python
pro.public_global_bonds(keyword='美债', limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_global_bonds(keyword='美债', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_global_bonds(keyword='美债', limit=5, as_dataframe=False)
```

- 仅已上市

```python
pro.public_global_bonds(keyword='美债', limit=5, listed=True)
```

**数据样例**

暂无可用样例：无样例

### `public_usstocks`

- **路径：** `/public/v1/usstocks`
- **类型：** http
- **说明：** 美股公开清单/搜索
- **签名：** `pro.public_usstocks(*, keyword=None, market=None, page=None, limit=None, **opts)`
- **介绍：** 美股公开清单/搜索 `GET /public/v1/usstocks`。`market` 为 `N`/`O`/`A`。

**用法**

- 基本调用

```python
pro.public_usstocks(keyword='AAPL', limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.public_usstocks(keyword='AAPL', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.public_usstocks(keyword='AAPL', limit=5, as_dataframe=False)
```

- 指定市场（如 `SS` / `SZ`）

```python
pro.public_usstocks(keyword='AAPL', limit=5, market='SS')
```

- 页码

```python
pro.public_usstocks(keyword='AAPL', limit=5, page=1)
```

**数据样例**

暂无可用样例：无样例

### `corp_schema`

- **路径：** `/public/v1/corp/schema`
- **类型：** http
- **说明：** 公司资料字段结构
- **签名：** `pro.corp_schema(**opts)`

**用法**

- 基本调用

```python
pro.corp_schema()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.corp_schema(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.corp_schema(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `description` | A 股公司资料字段说明 |

**`fields` 展开（20 条）**

| `desc` | `path` | `type` |
| --- | --- | --- |
| 数据更新时间，ISO 8601 | fetched_at | string |
| 证券基本信息 | security | object |
| 6 位证券代码 | security.code | string |
| 行情代码，与实时行情一致，如 600519.SS、920000.BJ | security.symbol | string |
| 证券简称 | security.short_name | string |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `description` | 描述 | A 股公司资料字段说明 |
| `fields` | 字段名列表 | [20 项，见下方展开] |
| `fields.desc` | 字段名列表 → 描述 | 数据更新时间，ISO 8601 |
| `fields.path` | 字段名列表 → 路径 | fetched_at |
| `fields.type` | 字段名列表 → 类型 | string |

### `finance_schema`

- **路径：** `/public/v1/finance/schema`
- **类型：** http
- **说明：** 财务字段结构
- **签名：** `pro.finance_schema(**opts)`

**用法**

- 基本调用

```python
pro.finance_schema()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.finance_schema(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.finance_schema(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `description` | 上市公司财务报表。reports 按 source 分表；每期指标含 value 与 yoy（… |
| `period_fields` | ["report_date", "year", "period_type", "label",… |

**`field_meta` 展开**

| 字段 | 值 |
|------|-----|
| `title` | 指标中文名 |

**`params` 展开**

| 字段 | 值 |
|------|-----|
| `period` | 单期：YYYYMMDD、YYYY-Qn、YYYY-H1/H2、YYYY-A（如 2025Q1 … |
| `periods` | 最近几期，默认 8，最大 40；传 0 表示全部 |
| `source` | 逗号分隔：metrics/income/balance/cashflow，默认四表；可选 sp… |
| `symbol` | 股票代码，如 600519.SS |
| `year` | 自然年 YYYY，返回该年全部报告期（如 2025） |
| `years` | 最近几个自然年，1–20（与 year 互斥，优先 year） |

**`sources` 展开（5 条）**

| `default` | `id` | `label` |
| --- | --- | --- |
| True | metrics | 关键指标 |
| True | income | 利润表 |
| True | balance | 资产负债表 |
| True | cashflow | 现金流量表 |
| False | special | 专项指标 |

**`value_fields` 展开**

| 字段 | 值 |
|------|-----|
| `value` | 期末值 |
| `yoy` | 同比 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `description` | 描述 | 上市公司财务报表。reports 按 source 分表；每期指标含 value 与 yoy（… |
| `field_meta` | 字段元数据 | {1 字段，见下方展开} |
| `params` | 参数 | {6 字段，见下方展开} |
| `period_fields` | 周期字段 | ["report_date", "year", "period_type", "label",… |
| `sources` | 字段 `sources` | [5 项，见下方展开] |
| `value_fields` | 数值字段 | {2 字段，见下方展开} |
| `field_meta.title` | 字段元数据 → 标题 | 指标中文名 |
| `params.period` | 参数 → 周期（秒） | 单期：YYYYMMDD、YYYY-Qn、YYYY-H1/H2、YYYY-A（如 2025Q1 … |
| `params.periods` | 参数 → 周期列表 | 最近几期，默认 8，最大 40；传 0 表示全部 |
| `params.source` | 参数 → 数据来源 | 逗号分隔：metrics/income/balance/cashflow，默认四表；可选 sp… |
| `params.symbol` | 参数 → 标的代码 | 股票代码，如 600519.SS |
| `params.year` | 参数 → 年份 | 自然年 YYYY，返回该年全部报告期（如 2025） |
| `params.years` | 参数 → 年份列表 | 最近几个自然年，1–20（与 year 互斥，优先 year） |
| `sources.default` | 字段 `sources` → 默认值 | True |
| `sources.id` | 字段 `sources` → 编号 | metrics |
| `sources.label` | 字段 `sources` → 标签 | 关键指标 |
| `value_fields.value` | 数值字段 → 数值 | 期末值 |
| `value_fields.yoy` | 数值字段 → 同比 | 同比 |

### `etf_schema`

- **路径：** `/public/v1/etf/schema`
- **类型：** http
- **说明：** 基金字段结构
- **签名：** `pro.etf_schema(**opts)`

**用法**

- 基本调用

```python
pro.etf_schema()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.etf_schema(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.etf_schema(as_dataframe=False)
```

**数据样例**

| `example` | `field` | `label` |
| --- | --- | --- |
| 515250.SS | symbol | 代码 |
| 515250 | code | 6位基金代码 |
| 富国中证智能汽车主题ETF | sname | 简称 |
|  | full_name | 基金全称 |
| 股票-主题 | category | 类别 |

（共 14 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `example` | 示例 | 515250.SS |
| `field` | 字段名 | symbol |
| `label` | 标签 | 代码 |

### `bond_schema`

- **路径：** `/public/v1/bond/schema`
- **类型：** http
- **说明：** 债券字段结构
- **签名：** `pro.bond_schema(**opts)`
- **介绍：** 债券字段说明 `GET /public/v1/bond/schema`。

**用法**

- 基本调用

```python
pro.bond_schema()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_schema(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_schema(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `moneyflow_schema`

- **路径：** `/public/v1/moneyflow/schema`
- **类型：** http
- **说明：** 资金流字段结构
- **签名：** `pro.moneyflow_schema(**opts)`

**用法**

- 基本调用

```python
pro.moneyflow_schema()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_schema(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_schema(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `description` | 个股资金流向字段说明；显式 bdate/edate 跨度最多 10 自然日；未指定日期时按 l… |

**`datasets` 展开（3 条）**

| `fields` | `id` | `label` |
| --- | --- | --- |
| [12 项，见下方展开] | daily-trend | 日资金流入趋势 |
| [10 项，见下方展开] | stage | 阶段主力动向 |
| [14 项，见下方展开] | distribution | 历史成交分布 |

**`query` 展开**


**`bdate` 展开**

| 字段 | 值 |
|------|-----|
| `description` | 起始日 YYYY-MM-DD 或 YYYYMMDD |
| `required` | False |

**`date` 展开**

| 字段 | 值 |
|------|-----|
| `description` | 单个交易日 YYYY-MM-DD 或 YYYYMMDD（与 bdate/edate 互斥） |
| `required` | False |

**`edate` 展开**

| 字段 | 值 |
|------|-----|
| `description` | 结束日 YYYY-MM-DD 或 YYYYMMDD |
| `required` | False |

**`limit` 展开**

| 字段 | 值 |
|------|-----|
| `description` | 最多返回条数；未指定日期时默认 1、最大 5（最近有数据交易日）；显式 date / bdat… |
| `required` | False |

**`symbol` 展开**

| 字段 | 值 |
|------|-----|
| `description` | 股票代码 |
| `required` | True |

**`routes` 展开**

| 字段 | 值 |
|------|-----|
| `daily-trend` | /v1/moneyflow/daily-trend |
| `distribution` | /v1/moneyflow/distribution |
| `stage` | /v1/moneyflow/stage |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `datasets` | 数据集 | [3 项，见下方展开] |
| `description` | 描述 | 个股资金流向字段说明；显式 bdate/edate 跨度最多 10 自然日；未指定日期时按 l… |
| `query` | 查询条件 | {5 字段，见下方展开} |
| `routes` | 路由 | {3 字段，见下方展开} |
| `datasets.fields` | 数据集 → 字段名列表 | [12 项，见下方展开] |
| `datasets.id` | 数据集 → 编号 | daily-trend |
| `datasets.label` | 数据集 → 标签 | 日资金流入趋势 |
| `query.bdate` | 查询条件 → 开始日 | {"description": "起始日 YYYY-MM-DD 或 YYYYMMDD", "r… |
| `query.date` | 查询条件 → 交易日 | {"description": "单个交易日 YYYY-MM-DD 或 YYYYMMDD（与 … |
| `query.edate` | 查询条件 → 结束日 | {"description": "结束日 YYYY-MM-DD 或 YYYYMMDD", "r… |
| `query.limit` | 查询条件 → 条数上限 | {"description": "最多返回条数；未指定日期时默认 1、最大 5（最近有数据交易… |
| `query.symbol` | 查询条件 → 标的代码 | {"description": "股票代码", "required": true} |
| `query.bdate.description` | 查询条件 → 字段 `bdate.description` |  |
| `query.bdate.required` | 查询条件 → 字段 `bdate.required` |  |
| `query.date.description` | 查询条件 → 字段 `date.description` |  |
| `query.date.required` | 查询条件 → 字段 `date.required` |  |
| `query.edate.description` | 查询条件 → 字段 `edate.description` |  |
| `query.edate.required` | 查询条件 → 字段 `edate.required` |  |
| `query.limit.description` | 查询条件 → 字段 `limit.description` |  |
| `query.limit.required` | 查询条件 → 字段 `limit.required` |  |
| `query.symbol.description` | 查询条件 → 字段 `symbol.description` |  |
| `query.symbol.required` | 查询条件 → 字段 `symbol.required` |  |
| `routes.daily-trend` | 路由 → 字段 `daily-trend` | /v1/moneyflow/daily-trend |
| `routes.distribution` | 路由 → 分红方式 | /v1/moneyflow/distribution |
| `routes.stage` | 路由 → 阶段 | /v1/moneyflow/stage |

### `moneyflow_ranking_catalog`

- **路径：** `/public/v1/moneyflow/ranking/catalog`
- **类型：** http
- **说明：** 新浪资金流榜单目录
- **签名：** `pro.moneyflow_ranking_catalog(**opts)`
- **介绍：** 新浪资金流排名目录 `GET /public/v1/moneyflow/ranking/catalog`。

**用法**

- 基本调用

```python
pro.moneyflow_ranking_catalog()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_catalog(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_catalog(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `captured_at_format` | 2026-07-13 13:57:11 |
| `captured_at_format_note` | 北京时间 YYYY-MM-DD HH:MM:SS（无时区后缀）。 |
| `policy` | today_intraday |
| `policy_label` | 仅当日盘中快照 |
| `policy_note` | 新浪资金流排名：返回当前业务日盘中资金流向排行；09:15 前为上一交易日。不支持按历史日期随… |
| `sort_note` | 净流入 / 主力 / 散户三类榜；sort 选择按额或按率。 |
| `source` | sina |
| `source_label` | 新浪 |
| `symbol_format` | 600519.SS |
| `symbol_format_note` | 个股 symbol、板块 ts_symbol 均为标准代码（代码+后缀）。 |

**`boards` 展开（3 条）**

| `id` | `label` |
| --- | --- |
| industry | 行业 |
| concept | 概念板块 |
| csrc_industry | 证监会行业 |

**`stock_sorts` 展开（6 条）**

| `id` | `label` |
| --- | --- |
| netamount | 净流入额 |
| ratioamount | 净流入率 |
| r0_net | 主力净流入额 |
| r0_ratio | 主力净流入率 |
| r3_net | 散户净流入额 |

（共 6 行，表中展示前 5 行）

**`stocks` 展开（3 条）**

| `default_sort` | `fields` | `id` | `label` | `path` | `sorts` |
| --- | --- | --- | --- | --- | --- |
| netamount | ["symbol", "name", "trade", "changeratio", "tur… | net | 净流入 | /v1/moneyflow/ranking/stocks/net | [2 项，见下方展开] |
| r0_net | ["symbol", "name", "trade", "changeratio", "tur… | main | 主力 | /v1/moneyflow/ranking/stocks/main | [2 项，见下方展开] |
| r3_net | ["symbol", "name", "trade", "changeratio", "tur… | retail | 散户 | /v1/moneyflow/ranking/stocks/retail | [2 项，见下方展开] |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `boards` | 板块列表 | [3 项，见下方展开] |
| `captured_at_format` | 采集时间格式 | 2026-07-13 13:57:11 |
| `captured_at_format_note` | 采集时间格式说明 | 北京时间 YYYY-MM-DD HH:MM:SS（无时区后缀）。 |
| `policy` | 策略 | today_intraday |
| `policy_label` | 策略说明 | 仅当日盘中快照 |
| `policy_note` | 策略备注 | 新浪资金流排名：返回当前业务日盘中资金流向排行；09:15 前为上一交易日。不支持按历史日期随… |
| `sort_note` | 排序说明 | 净流入 / 主力 / 散户三类榜；sort 选择按额或按率。 |
| `source` | 数据来源 | sina |
| `source_label` | 来源说明 | 新浪 |
| `stock_sorts` | 股票排序项 | [6 项，见下方展开] |
| `stocks` | 成分股列表 | [3 项，见下方展开] |
| `symbol_format` | 代码格式 | 600519.SS |
| `symbol_format_note` | 代码格式说明 | 个股 symbol、板块 ts_symbol 均为标准代码（代码+后缀）。 |
| `boards.id` | 板块列表 → 编号 | industry |
| `boards.label` | 板块列表 → 标签 | 行业 |
| `stock_sorts.id` | 股票排序项 → 编号 | netamount |
| `stock_sorts.label` | 股票排序项 → 标签 | 净流入额 |
| `stocks.default_sort` | 成分股列表 → 默认排序 | netamount |
| `stocks.fields` | 成分股列表 → 字段名列表 | ["symbol", "name", "trade", "changeratio", "tur… |
| `stocks.id` | 成分股列表 → 编号 | net |
| `stocks.label` | 成分股列表 → 标签 | 净流入 |
| `stocks.path` | 成分股列表 → 路径 | /v1/moneyflow/ranking/stocks/net |
| `stocks.sorts` | 成分股列表 → 可选排序 | [2 项，见下方展开] |

### `moneyflow_ranking_live_catalog`

- **路径：** `/public/v1/moneyflow/ranking/live/catalog`
- **类型：** http
- **说明：** 实时资金流榜单目录
- **签名：** `pro.moneyflow_ranking_live_catalog(**opts)`
- **介绍：** 实时资金流排名目录 `GET /public/v1/moneyflow/ranking/live/catalog`。

**用法**

- 基本调用

```python
pro.moneyflow_ranking_live_catalog()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_live_catalog(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_live_catalog(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `moneyflow_live_catalog`

- **路径：** `/public/v1/moneyflow/live/catalog`
- **类型：** http
- **说明：** 实时个股资金流（按码）目录
- **签名：** `pro.moneyflow_live_catalog(**opts)`
- **介绍：** 实时个股资金流（按码）目录 `GET /public/v1/moneyflow/live/catalog`。

**用法**

- 基本调用

```python
pro.moneyflow_live_catalog()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_live_catalog(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_live_catalog(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `plate_moneyflow_schema`

- **路径：** `/public/v1/plate/moneyflow/schema`
- **类型：** http
- **说明：** 板块资金流字段说明
- **签名：** `pro.plate_moneyflow_schema(**opts)`
- **介绍：** 板块资金流字段说明 `GET /public/v1/plate/moneyflow/schema`。

**用法**

- 基本调用

```python
pro.plate_moneyflow_schema()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.plate_moneyflow_schema(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.plate_moneyflow_schema(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `docs_md`

- **路径：** `/public/v1/docs.md`
- **类型：** text
- **说明：** 接口说明文档
- **签名：** `pro.docs_md()`

**用法**

- docs_md()

```python
pro.docs_md()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.docs_md(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.docs_md(as_dataframe=False)
```

**数据样例**

```text
# KlineShare 行情 API 参考

A 股**实时行情**、**分时图**、多周期 **K 线**、**股票信息**、**上市公司资料**、**增发配股**、**财报四表**、**交易日历**、**涨停专题**、**龙虎榜**、**游资名录**；沪深 ETF 走专用 `/v1/etf*` 路径。基础地址：`/v1`。

套餐档位、scope 与主要指数列表为动态配置，以 `GET /public/v1/catalog` 为准。

## 鉴权

除 `GET /v1/health`、本文档与 `/public/v1/*` 元数据外，数据接口均需 API Key。

```http
GET /v1/realtime?symbol=603778.SS
X-API-Key: tg_xxxxxxxxxxxxxxxxxxxxxxxx
```

也支持查询参数 `?api_key=tg_xxx`（不推荐，易泄露到日志）。Key 在用户中心签发，**完整 Key 仅显示一次**。

## 权限说明

权限分两层：**接口权限（scope）** 与 **K 线数据策略**。

### 接口权限

未开通相应 scope 时返回 `403`。各套餐接口差异见 `GET /public/v1/catalog` 的 `scope_rows`（含各档位 ✓/— 对照）与 `tier_columns`。

### K 线数据策略

在拥有 `kline` scope 的前提下，限制可请求的周期、条数、复权方式与技术指标。超出套餐上限时条数会自动裁切。`GET /v1/me` 可查看当前 Key 的 `kline` 摘要。

### 账号状态

- 用户中心「接口测试」无有效 Key → `403`
- 账号已过期 → `401`
- 账号或 Key 已禁用 → `401` / `403`
…
```

### `llms_txt`

- **路径：** `/public/v1/llms.txt`
- **类型：** text
- **说明：** 大模型短文档
- **签名：** `pro.llms_txt()`

**用法**

- llms_txt()

```python
pro.llms_txt()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.llms_txt(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.llms_txt(as_dataframe=False)
```

**数据样例**

```text
# KlineShare 行情 API

> A 股实时行情、分时图、多周期 K 线、股票信息、上市公司资料、财报四表、交易日历、涨停专题；鉴权 Header `X-API-Key`。支持 MCP 的 AI 客户端可配置远程 `/mcp` 端点查数据。

## 文档

- [完整 API 参考（Markdown）](/llms-full.txt): 所有公开数据接口、参数、示例与错误码
- [人类可读文档](/docs/): 网页版（含动态套餐表）
- [API 参考 Markdown](/public/v1/docs.md): 与 llms-full.txt 相同内容，JSON API 同源
- [MCP 远程端点](/mcp): 在支持 MCP 的 AI 客户端中配置 `url` + `X-API-Key`
- [套餐与权限（JSON）](/public/v1/catalog): 套餐档位、scope、主要指数列表
- [上市公司字段（JSON）](/public/v1/corp/schema): corp 响应字段说明
- [财报四表（JSON）](/public/v1/finance/schema): finance/report 表类型与结构说明
- [ETF 字段（JSON）](/public/v1/etf/schema): ETF 响应字段说明
- [债券概况字段（JSON）](/public/v1/bond/schema): 可转债/国债/企债概况 sections 说明
- [资金流向字段（JSON）](/public/v1/moneyflow/schema): 个股资金流向三表字段说明
- [主要指数列表（JSON）](/public/v1/indices): 精选清单；`?keyword=` 搜索全量（默认有日 K）
- [贵金属清单（JSON）](/…
```

### `llms_full_txt`

- **路径：** `/public/v1/llms-full.txt`
- **类型：** text
- **说明：** 大模型全文档
- **签名：** `pro.llms_full_txt()`

**用法**

- llms_full_txt()

```python
pro.llms_full_txt()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.llms_full_txt(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.llms_full_txt(as_dataframe=False)
```

**数据样例**

```text
# KlineShare 行情 API 参考

A 股**实时行情**、**分时图**、多周期 **K 线**、**股票信息**、**上市公司资料**、**增发配股**、**财报四表**、**交易日历**、**涨停专题**、**龙虎榜**、**游资名录**；沪深 ETF 走专用 `/v1/etf*` 路径。基础地址：`/v1`。

套餐档位、scope 与主要指数列表为动态配置，以 `GET /public/v1/catalog` 为准。

## 鉴权

除 `GET /v1/health`、本文档与 `/public/v1/*` 元数据外，数据接口均需 API Key。

```http
GET /v1/realtime?symbol=603778.SS
X-API-Key: tg_xxxxxxxxxxxxxxxxxxxxxxxx
```

也支持查询参数 `?api_key=tg_xxx`（不推荐，易泄露到日志）。Key 在用户中心签发，**完整 Key 仅显示一次**。

## 权限说明

权限分两层：**接口权限（scope）** 与 **K 线数据策略**。

### 接口权限

未开通相应 scope 时返回 `403`。各套餐接口差异见 `GET /public/v1/catalog` 的 `scope_rows`（含各档位 ✓/— 对照）与 `tier_columns`。

### K 线数据策略

在拥有 `kline` scope 的前提下，限制可请求的周期、条数、复权方式与技术指标。超出套餐上限时条数会自动裁切。`GET /v1/me` 可查看当前 Key 的 `kline` 摘要。

### 账号状态

- 用户中心「接口测试」无有效 Key → `403`
- 账号已过期 → `401`
- 账号或 Key 已禁用 → `401` / `403`
…
```

## 行情（个股 / 北交所 / 资料）

### `realtime`

- **路径：** `/v1/realtime`
- **类型：** http
- **说明：** 个股实时
- **签名：** `pro.realtime(symbol=None, *, ks_code=None, include_valuation=None, include_depth=None, **opts)`
- **介绍：** 沪深京 A 股实时行情 `GET /v1/realtime`（北交所 `*.BJ` 与沪深同路径）。

**用法**

- 基本调用

```python
pro.realtime(symbol='600519.SH')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.realtime(ks_code='sh600519')
```

**进阶用法**

- 附带估值 / 盘口字段

```python
pro.realtime(symbol=['600519.SH', '000001.SZ'], include_valuation=True, include_depth=True)
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.realtime(symbol='600519.SH', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.realtime(symbol='600519.SH', as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `change` | -2.56 |
| `change_percent` | -0.00204179 |
| `close` | 1251.24 |
| `date` | 20260923 |
| `high` | 1271.5 |
| `low` | 1250.89 |
| `name` | 贵州茅台 |
| `open` | 1255.03 |
| `pre_close` | 1253.8 |
| `price` | 1251.24 |
| `symbol` | 600519.SS |
| `timestamp` | 1790146800000 |
| `trade_status` | BREAK |
| `turnover` | 3.89463e+09 |
| `volume` | 3.09812e+06 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change` | 涨跌额 | -2.56 |
| `change_percent` | 涨跌幅（%） | -0.00204179 |
| `close` | 收盘价 / 最新价 | 1251.24 |
| `date` | 交易日 | 20260923 |
| `high` | 最高价 | 1271.5 |
| `low` | 最低价 | 1250.89 |
| `name` | 名称 | 贵州茅台 |
| `open` | 开盘价 | 1255.03 |
| `pre_close` | 昨收 | 1253.8 |
| `price` | 最新价 | 1251.24 |
| `symbol` | 标的代码 | 600519.SS |
| `timestamp` | 时间戳（毫秒） | 1790146800000 |
| `trade_status` | 交易状态 | BREAK |
| `turnover` | 换手相关 | 3.89463e+09 |
| `volume` | 成交量 | 3.09812e+06 |

### `realtime_v2`

- **路径：** `/v2/realtime`
- **类型：** http
- **说明：** 全市场紧凑格式实时（一般用 all=True）
- **签名：** `pro.realtime_v2(symbol=None, *, ks_code=None, all=None, market=None, include_valuation=None, include_depth=None, **opts)`
- **介绍：** 全市场 compact 实时 `GET /v2/realtime`（独立 scope `realtime_v2`）。

**用法**

- 全市场（推荐）

```python
pro.realtime_v2(all=True, market='SS')
```

**进阶用法**

- 指定标的 / 批量

```python
pro.realtime_v2(symbol='600519.SS')
```

- 全市场含估值与盘口

```python
pro.realtime_v2(
    all=True, market='SS', include_valuation=True, include_depth=True,
)
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.realtime_v2(all=True, market='SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.realtime_v2(all=True, market='SS', as_dataframe=False)
```

- 保留紧凑格式原始结构（`expand_compact_rows=False`）

```python
pro.realtime_v2(all=True, market='SS', expand_compact_rows=False)
```

**数据样例**

暂无可用样例：无样例

### `auction`

- **路径：** `/v1/auction`
- **类型：** http
- **说明：** 集合竞价分时（单标的）
- **签名：** `pro.auction(symbol=None, *, ks_code=None, **opts)`
- **介绍：** 沪深京单票集合竞价分时 `GET /v1/auction`。

**用法**

- 基本调用

```python
pro.auction(symbol='600519.SS')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.auction(ks_code='600519.SH')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.auction(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.auction(symbol='600519.SS', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `auction_v2`

- **路径：** `/v2/auction`
- **类型：** http
- **说明：** 集合竞价紧凑格式（一般用 all=True 拉全市场）
- **签名：** `pro.auction_v2(symbol=None, *, ks_code=None, all=None, market=None, trade_date=None, include_minutes=None, **opts)`
- **介绍：** 集合竞价 compact `GET /v2/auction`。

**用法**

- 全市场（推荐）

```python
pro.auction_v2(all=True, market='SS')
```

**进阶用法**

- 全市场含分时明细

```python
pro.auction_v2(all=True, include_minutes=True)
```

- 指定标的

```python
pro.auction_v2(symbol='600519.SS')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.auction_v2(all=True, market='SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.auction_v2(all=True, market='SS', as_dataframe=False)
```

- 指定交易日

```python
pro.auction_v2(all=True, market='SS', trade_date='20250102')
```

- 保留紧凑格式原始结构（`expand_compact_rows=False`）

```python
pro.auction_v2(all=True, market='SS', expand_compact_rows=False)
```

**数据样例**

暂无可用样例：无样例

### `trend`

- **路径：** `/v1/trend`
- **类型：** http
- **说明：** 分时
- **签名：** `pro.trend(symbol=None, *, ks_code=None, date=None, **opts)`
- **介绍：** 分时图 `GET /v1/trend`（每次仅 1 个 symbol）。

**用法**

- 基本调用

```python
pro.trend(symbol='600519.SS')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.trend(ks_code='600519.SH', date='20250102')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.trend(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.trend(symbol='600519.SS', as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `date` |  |
| `pre_close` | 1253.8 |
| `symbol` |  |
| `total` | 241 |

**`data` 展开（20 条）**

| `avg_price` | `change` | `change_percent` | `high` | `low` | `open` | `price` | `timestamp` | `turnover` | `volume` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1255.03 | 1.23 | 0.0981018 | 1261 | 1254 | 1258.33 | 1255.03 | 1790127000000 | 0 | 0 |
| 1255.3 | 2.95 | 0.235285 | 1257.5 | 1253.99 | 1254.99 | 1256.75 | 1790127060000 | 71679371 | 57100 |
| 1255.66 | 3.19 | 0.254427 | 1257.5 | 1255.22 | 1255.22 | 1256.99 | 1790127120000 | 28136597 | 22390 |
| 1255.85 | 1.71 | 0.136385 | 1257 | 1255.5 | 1256.05 | 1255.51 | 1790127180000 | 29278027 | 23300 |
| 1255.88 | 2.84 | 0.226511 | 1256.89 | 1255 | 1255.64 | 1256.64 | 1790127240000 | 28260339 | 22500 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `data` | 业务数据（可展开） | [20 项，见下方展开] |
| `date` | 交易日 |  |
| `pre_close` | 昨收 | 1253.8 |
| `symbol` | 标的代码 |  |
| `total` | 总数 | 241 |
| `data.avg_price` | 业务数据（可展开） → 均价 | 1255.03 |
| `data.change` | 业务数据（可展开） → 涨跌额 | 1.23 |
| `data.change_percent` | 业务数据（可展开） → 涨跌幅（%） | 0.0981018 |
| `data.high` | 业务数据（可展开） → 最高价 | 1261 |
| `data.low` | 业务数据（可展开） → 最低价 | 1254 |
| `data.open` | 业务数据（可展开） → 开盘价 | 1258.33 |
| `data.price` | 业务数据（可展开） → 最新价 | 1255.03 |
| `data.timestamp` | 业务数据（可展开） → 时间戳（毫秒） | 1790127000000 |
| `data.turnover` | 业务数据（可展开） → 换手相关 | 0 |
| `data.volume` | 业务数据（可展开） → 成交量 | 0 |

### `kline`

- **路径：** `/v2/kline`
- **类型：** http
- **说明：** K线（默认 raw 格式并展开为行）
- **签名：** `pro.kline(symbol=None, *, ks_code=None, period=None, adjust_type=None, count=None, timestamp=None, indicators=None, source=None, batch=None, format='raw', **opts)`
- **介绍：** K 线 `GET /v2/kline`（默认 `format=raw` 极限体积分隔串，展开为行 / DataFrame）。

**用法**

- 日线前复权

```python
pro.kline(symbol='600519.SH', period=86400, adjust_type='forward', count=5)
```

- ks_code 别名

```python
pro.kline(ks_code='600519', period=86400, count=3)
```

**进阶用法**

- 毫秒 timestamp 翻页 + raw 信封

```python
pro.kline(
    symbol='600519.SS', period=86400, count=2, timestamp=1_784_073_600_000, raw=True,
)
```

- format=None 使用服务端列式

```python
pro.kline(symbol='600519.SS', period=86400, count=2, format=None)
```

- 返回 list / dict，不转 DataFrame

```python
pro.kline(symbol='600519.SH', period=86400, adjust_type='forward', count=5, as_dataframe=False)
```

- 附加指标

```python
pro.kline(symbol='600519.SH', period=86400, adjust_type='forward', count=5, indicators='ma')
```

- 数据源

```python
pro.kline(symbol='600519.SH', period=86400, adjust_type='forward', count=5, source='default')
```

- 多标的批量策略：`multi` / `single` / `auto`

```python
pro.kline(symbol='600519.SH', period=86400, adjust_type='forward', count=5, batch='auto')
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` | `turnover` | `average_px` | `px_change` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 600519.SS | 20260917 | 1789603200000 | 1257.98 | 1267.6 | 1254 | 1266.98 | 1755380 |  | 2217338283 | 0 | 8.98 |
| 600519.SS | 20260918 | 1789689600000 | 1262.99 | 1265.88 | 1256.1 | 1257.12 | 2489087 |  | 3135849108 | 0 | -9.86 |
| 600519.SS | 20260921 | 1789948800000 | 1259 | 1259.95 | 1250.8 | 1252.57 | 2501689 |  | 3135910045 | 0 | -4.55 |
| 600519.SS | 20260922 | 1790035200000 | 1252.15 | 1265.88 | 1248.1 | 1253.8 | 2457294 |  | 3088526148 | 0 | 1.23 |
| 600519.SS | 20260923 | 1790121600000 | 1255.03 | 1271.5 | 1250.89 | 1251.24 | 3098122 |  | 3894630783 | 0 | -2.56 |

（共 5 行、前 12/15 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | 600519.SS |
| `date` | 交易日 | 20260917 |
| `timestamp` | 时间戳（毫秒） | 1789603200000 |
| `open` | 开盘价 | 1257.98 |
| `high` | 最高价 | 1267.6 |
| `low` | 最低价 | 1254 |
| `close` | 收盘价 / 最新价 | 1266.98 |
| `volume` | 成交量 | 1755380 |
| `amount` | 成交额 |  |
| `turnover` | 换手相关 | 2217338283 |
| `average_px` | 均价 | 0 |
| `px_change` | 涨跌额 | 8.98 |
| `px_change_rate` | 涨跌幅 | 0.713831 |
| `avg_px` | 均价 | 0 |
| `turnover_ratio` | 换手率 | 0.140421 |

### `iter_kline`

- **路径：** `/v2/kline`
- **类型：** helper
- **说明：** K线向更早翻页迭代
- **签名：** `pro.iter_kline(symbol=None, *, ks_code=None, period=None, adjust_type=None, count=None, timestamp=None, indicators=None, source=None, format='raw', max_pages=None, **opts)`
- **介绍：** 向更早时间翻页拉取 K 线，逐页 yield（与 `kline` 相同返回形态）。

**用法**

- max_pages=2

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2))
```

- ks_code

```python
list(pro.iter_kline(ks_code='600519.SH', period=86400, count=2, max_pages=1))
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), as_dataframe=False)
```

- 复权类型

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), adjust_type='forward')
```

- 翻页游标（请求参数为秒）

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), timestamp=1700000000)
```

- 附加指标

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), indicators='ma')
```

- 数据源

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), source='default')
```

- 不传 `format=raw`，改用服务端列式数组

```python
list(pro.iter_kline(symbol='600519.SS', period=86400, count=3, max_pages=2), format=None)
```

**数据样例**

```json
[
  [
    {
      "symbol": "600519.SS",
      "date": "20260921",
      "timestamp": 1789948800000,
      "open": 1259,
      "high": 1259.95,
      "low": 1250.8,
      "close": 1252.57,
      "volume": 2501689,
      "amount": null,
      "turnover": 3135910045,
      "average_px": 0,
      "px_change": -4.55,
      "px_change_rate": -0.361938,
      "avg_px": 0,
      "turnover_ratio": 0.200122
    },
    {
      "symbol": "600519.SS",
      "date": "20260922",
      "timestamp": 1790035200000,
      "open": 1252.15,
      "high": 1265.88,
      "low": 1248.1,
      "close": 1253.8,
      "volume": 2457294,
      "amount": null,
      "turnover": 3088526148,
      "average_px": 0,
      "px_change": 1.23,
      "px_change_rate": 0.098198,
      "avg_px": 0,
      "turnover_ratio": 0.196571
    },
    {
      "symbol": "600519.SS",
      "date": "20260923",
      "timestamp": 1790121600000,
      "open": 1255.03,
      "high": 1271.5,
      "low": 1250.89,
      "close": 1251.24,
      "volume": 3098122,
      "amount": null,
      "turnover": 3894630783,
      "average_px": 0,
      "px_change": -2.56,
      "px_change_rate": -0.204179,
      "avg_px": 0,
      "turnover_ratio": 0.2478
    }
  ],
  [
    {
      "symbol": "600519.SS",
      "date": "20260916",
      "timestamp": 1789516800000,
      "open": 1273.93,
      "high": 1274.98,
      "low": 1254.1,
      "close": 1258,
      "volume": 2623524,
      "amount": null,
      "turnover": 3307926407,
      "average_px": 0,
      "px_change": -14.75,
      "px_change_rate": -1.158908,
      "avg_px": 0,
      "turnover_ratio": 0.209868
    },
    {
      "symbol": "600519.SS",
      "date": "20260917",
      "timestamp": 1789603200000,
      "open": 1257.98,
      "high": 1267.6,
      "low": 1254,
      "close": 1266.98,
      "volume": 1755380,
      "amount": null,
      "turnover": 2217338283,
      "average_px": 0,
      "px_change": 8.98,
      "px_change_rate": 0.713831,
      "avg_px": 0,
      "turnover_ratio": 0.140421
    },
    {
      "symbol": "600519.SS",
      "date": "20260918",
      "timestamp": 1789689600000,
      "open": 1262.99,
      "high": 1265.88,
      "low": 1256.1,
      "close": 1257.12,
      "volume": 2489087,
      "amount": null,
      "turnover": 3135849108,
      "average_px": 0,
      "px_change": -9.86,
      "px_change_rate": -0.778229,
      "avg_px": 0,
      "turnover_ratio": 0.199114
    }
  ]
]
```

### `kline_batch`

- **路径：** `/v2/kline`
- **类型：** http
- **说明：** K线多标的批量（最多5个）

**用法**

- kline 3 symbols

```python
pro.kline(
    symbol=['600519.SS', '000001.SZ', '000002.SZ'],
    period=86400,
    count=2,
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.kline(
    symbol=['600519.SS', '000001.SZ', '000002.SZ'],
    period=86400,
    count=2,, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.kline(
    symbol=['600519.SS', '000001.SZ', '000002.SZ'],
    period=86400,
    count=2,, as_dataframe=False)
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` | `turnover` | `average_px` | `px_change` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 600519.SS | 20260922 | 1790035200000 | 1252.15 | 1265.88 | 1248.1 | 1253.8 | 2457294 |  | 3088526148 | 0 | 1.23 |
| 600519.SS | 20260923 | 1790121600000 | 1255.03 | 1271.5 | 1250.89 | 1251.24 | 3098122 |  | 3894630783 | 0 | -2.56 |
| 000001.SZ | 20260922 | 1790035200000 | 11.7 | 11.75 | 11.62 | 11.71 | 75945732 |  | 8.87703e+08 | 0 | -0.02 |
| 000001.SZ | 20260923 | 1790121600000 | 11.68 | 11.71 | 11.55 | 11.6 | 90672565 |  | 1.05202e+09 | 0 | -0.11 |
| 000002.SZ | 20260922 | 1790035200000 | 3.57 | 3.89 | 3.54 | 3.81 | 819832133 |  | 3.03786e+09 | 0 | 0.16 |

（共 6 行，表中展示前 5 行、前 12/15 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | 600519.SS |
| `date` | 交易日 | 20260922 |
| `timestamp` | 时间戳（毫秒） | 1790035200000 |
| `open` | 开盘价 | 1252.15 |
| `high` | 最高价 | 1265.88 |
| `low` | 最低价 | 1248.1 |
| `close` | 收盘价 / 最新价 | 1253.8 |
| `volume` | 成交量 | 2457294 |
| `amount` | 成交额 |  |
| `turnover` | 换手相关 | 3088526148 |
| `average_px` | 均价 | 0 |
| `px_change` | 涨跌额 | 1.23 |
| `px_change_rate` | 涨跌幅 | 0.098198 |
| `avg_px` | 均价 | 0 |
| `turnover_ratio` | 换手率 | 0.196571 |

### `realtime_batch`

- **路径：** `/v1/realtime`
- **类型：** http
- **说明：** 实时多标的批量

**用法**

- realtime 2 symbols

```python
pro.realtime(symbol=['600519.SH', '000001.SZ'])
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.realtime(symbol=['600519.SH', '000001.SZ'], raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.realtime(symbol=['600519.SH', '000001.SZ'], as_dataframe=False)
```

**数据样例**

| `change` | `change_percent` | `close` | `date` | `high` | `low` | `name` | `open` | `pre_close` | `price` | `symbol` | `timestamp` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -2.56 | -0.00204179 | 1251.24 | 20260923 | 1271.5 | 1250.89 | 贵州茅台 | 1255.03 | 1253.8 | 1251.24 | 600519.SS | 1790146800000 |
| -0.11 | -0.00939368 | 11.6 | 20260923 | 11.71 | 11.55 | 平安银行 | 11.68 | 11.71 | 11.6 | 000001.SZ | 1790147088000 |

（共 2 行、前 12/15 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change` | 涨跌额 | -2.56 |
| `change_percent` | 涨跌幅（%） | -0.00204179 |
| `close` | 收盘价 / 最新价 | 1251.24 |
| `date` | 交易日 | 20260923 |
| `high` | 最高价 | 1271.5 |
| `low` | 最低价 | 1250.89 |
| `name` | 名称 | 贵州茅台 |
| `open` | 开盘价 | 1255.03 |
| `pre_close` | 昨收 | 1253.8 |
| `price` | 最新价 | 1251.24 |
| `symbol` | 标的代码 | 600519.SS |
| `timestamp` | 时间戳（毫秒） | 1790146800000 |
| `trade_status` | 交易状态 | BREAK |
| `turnover` | 换手相关 | 3.89463e+09 |
| `volume` | 成交量 | 3.09812e+06 |

### `adjust_factors`

- **路径：** `/v1/adjust-factors`
- **类型：** http
- **说明：** 复权因子
- **签名：** `pro.adjust_factors(symbol=None, *, ks_code=None, adjust_type=None, count=None, start=None, end=None, **opts)`
- **介绍：** 复权因子 `GET /v1/adjust-factors`（**不建议**；请改用 `adjust_params`）。

**用法**

- 基本调用

```python
pro.adjust_factors(symbol='600519.SS')
```

**进阶用法**

- 进阶参数组合

```python
pro.adjust_factors(symbol='600519.SS', start='20200101', end='20250101')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.adjust_factors(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.adjust_factors(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.adjust_factors(ks_code='sh600519')
```

- 复权类型

```python
pro.adjust_factors(symbol='600519.SS', adjust_type='forward')
```

- 返回条数

```python
pro.adjust_factors(symbol='600519.SS', count=10)
```

**数据样例**

| `date` | `factor` |
| --- | --- |
| 19000101 | 8.88251 |
| 20010827 | 8.88251 |
| 20020725 | 7.94191 |
| 20030714 | 7.16373 |
| 20040701 | 5.46172 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `date` | 交易日 | 19000101 |
| `factor` | 因子 | 8.88251 |

### `exrights`

- **路径：** `/v1/exrights`
- **类型：** http
- **说明：** 除权除息
- **签名：** `pro.exrights(symbol=None, *, ks_code=None, count=None, start=None, end=None, **opts)`
- **介绍：** 除权除息 `GET /v1/exrights`。

**用法**

- 基本调用

```python
pro.exrights(symbol='600519.SS', count=20)
```

**进阶用法**

- 进阶参数组合

```python
pro.exrights(symbol='600519.SS', start='20200101', end='20241231')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.exrights(symbol='600519.SS', count=20, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.exrights(symbol='600519.SS', count=20, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.exrights(ks_code='sh600519', count=20)
```

**数据样例**

| `date` | `distribution_ratio` | `dividend` | `placing_price` | `placing_ratio` |
| --- | --- | --- | --- | --- |
| 20110701 | 0.1 | 2.3 | 0 | 0 |
| 20120705 | 0 | 3.997 | 0 | 0 |
| 20130607 | 0 | 6.419 | 0 | 0 |
| 20140625 | 0.1 | 4.374 | 0 | 0 |
| 20150717 | 0.1 | 4.374 | 0 | 0 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `date` | 交易日 | 20110701 |
| `distribution_ratio` | 分红比例 | 0.1 |
| `dividend` | 分红 | 2.3 |
| `placing_price` | 配售价 | 0 |
| `placing_ratio` | 配售比例 | 0 |

### `adjust_params`

- **路径：** `/v1/adjust-params`
- **类型：** http
- **说明：** 复权参数
- **签名：** `pro.adjust_params(symbol=None, *, ks_code=None, adjust_type=None, count=None, start=None, end=None, **opts)`
- **介绍：** 复权参数 `GET /v1/adjust-params`（**推荐**自行复权；affine：价=(原价×multiplier+addend)/10000）。

**用法**

- 基本调用

```python
pro.adjust_params(symbol='600519.SS', adjust_type='forward', count=64)
```

**进阶用法**

- 进阶参数组合

```python
pro.adjust_params(symbol='600519.SS', adjust_type='backward', start='20200101')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.adjust_params(symbol='600519.SS', adjust_type='forward', count=64, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.adjust_params(symbol='600519.SS', adjust_type='forward', count=64, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.adjust_params(ks_code='sh600519', adjust_type='forward', count=64)
```

- 结束日期

```python
pro.adjust_params(symbol='600519.SS', adjust_type='forward', count=64, end='20241231')
```

**数据样例**

| `addend` | `date` | `multiplier` |
| --- | --- | --- |
| -3198039 | 20020725 | 1877 |
| -3196912 | 20030714 | 2065 |
| -3196499 | 20040701 | 2272 |
| -3195818 | 20050805 | 2953 |
| -3194341 | 20060525 | 3544 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `addend` | 加项 | -3198039 |
| `date` | 交易日 | 20020725 |
| `multiplier` | 乘数 | 1877 |

### `bj_trend`

- **路径：** `/v1/bj/trend`
- **类型：** http
- **说明：** 北交所分时
- **签名：** `pro.bj_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.bj_trend(symbol='920000.BJ', date='20260824')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bj_trend(symbol='920000.BJ', date='20260824', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bj_trend(symbol='920000.BJ', date='20260824', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bj_trend(ks_code='sh600519', date='20260824')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `date` | 20260824 |
| `pre_close` | 13.42 |
| `symbol` | 920000.BJ |
| `total` | 241 |

**`data` 展开（20 条）**

| `avg_price` | `change` | `change_percent` | `high` | `low` | `open` | `price` | `timestamp` | `turnover` | `volume` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 13.3735 | -0.04 | -0.00298063 | 13.38 | 13.38 | 13.38 | 13.38 | 1787535000000 | 0 | 0 |
| 13.3735 | -0.05 | -0.00372578 | 13.38 | 13.37 | 13.38 | 13.37 | 1787535060000 | 16075 | 1202 |
| 13.3873 | 0.03 | 0.00223547 | 13.45 | 13.38 | 13.38 | 13.45 | 1787535120000 | 32628 | 2436 |
| 13.3962 | -0.01 | -0.000745156 | 13.43 | 13.32 | 13.36 | 13.41 | 1787535180000 | 41976 | 3131 |
| 13.4912 | 0.17 | 0.0126677 | 13.6 | 13.39 | 13.5 | 13.59 | 1787535240000 | 321098 | 23753 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `data` | 业务数据（可展开） | [20 项，见下方展开] |
| `date` | 交易日 | 20260824 |
| `pre_close` | 昨收 | 13.42 |
| `symbol` | 标的代码 | 920000.BJ |
| `total` | 总数 | 241 |
| `data.avg_price` | 业务数据（可展开） → 均价 | 13.3735 |
| `data.change` | 业务数据（可展开） → 涨跌额 | -0.04 |
| `data.change_percent` | 业务数据（可展开） → 涨跌幅（%） | -0.00298063 |
| `data.high` | 业务数据（可展开） → 最高价 | 13.38 |
| `data.low` | 业务数据（可展开） → 最低价 | 13.38 |
| `data.open` | 业务数据（可展开） → 开盘价 | 13.38 |
| `data.price` | 业务数据（可展开） → 最新价 | 13.38 |
| `data.timestamp` | 业务数据（可展开） → 时间戳（毫秒） | 1787535000000 |
| `data.turnover` | 业务数据（可展开） → 换手相关 | 0 |
| `data.volume` | 业务数据（可展开） → 成交量 | 0 |

### `bj_kline`

- **路径：** `/v1/bj/kline`
- **类型：** http
- **说明：** 北交所K线
- **签名：** `pro.bj_kline(symbol=None, *, ks_code=None, period=None, adjust_type=None, count=None, timestamp=None, source=None, format='raw', **opts)`

**用法**

- 基本调用

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bj_kline(ks_code='sh600519', period=86400, count=3)
```

- 复权类型

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3, adjust_type='forward')
```

- 翻页游标（请求参数为秒）

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3, timestamp=1700000000)
```

- 数据源

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3, source='default')
```

- 不传 `format=raw`，改用服务端列式数组

```python
pro.bj_kline(symbol='920000.BJ', period=86400, count=3, format=None)
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` | `turnover` | `average_px` | `avg_px` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 920000.BJ | 20260820 | 1787155200000 | 13.71 | 13.99 | 13.33 | 13.54 | 675640 |  | 0 | 0 | 0 |
| 920000.BJ | 20260821 | 1787241600000 | 13.41 | 13.55 | 13.36 | 13.42 | 382607 |  | 0 | 0 | 0 |
| 920000.BJ | 20260824 | 1787500800000 | 13.38 | 13.74 | 13 | 13.56 | 656429 |  | 0 | 0 | 0 |

（共 3 行、前 12/15 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | 920000.BJ |
| `date` | 交易日 | 20260820 |
| `timestamp` | 时间戳（毫秒） | 1787155200000 |
| `open` | 开盘价 | 13.71 |
| `high` | 最高价 | 13.99 |
| `low` | 最低价 | 13.33 |
| `close` | 收盘价 / 最新价 | 13.54 |
| `volume` | 成交量 | 675640 |
| `amount` | 成交额 |  |
| `turnover` | 换手相关 | 0 |
| `average_px` | 均价 | 0 |
| `avg_px` | 均价 | 0 |
| `px_change` | 涨跌额 | -0.11 |
| `px_change_rate` | 涨跌幅 | -0.805861 |
| `turnover_ratio` | 换手率 | 0 |

### `stock`

- **路径：** `/v1/stock`
- **类型：** http
- **说明：** 个股基础信息
- **签名：** `pro.stock(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.stock(symbol='600519.SS')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.stock(ks_code='600519.SH')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.stock(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.stock(symbol='600519.SS', as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `code` | 600519 |
| `market` | sh |
| `name` | 贵州茅台 |
| `symbol` | 600519.SS |
| `update_time` | 2026-07-14 15:15:15 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 600519 |
| `market` | 市场 | sh |
| `name` | 名称 | 贵州茅台 |
| `symbol` | 标的代码 | 600519.SS |
| `update_time` | 更新时间 | 2026-07-14 15:15:15 |

### `stocks`

- **路径：** `/v1/stocks`
- **类型：** http
- **说明：** 股票列表搜索
- **签名：** `pro.stocks(*, keyword=None, market=None, limit=None, page=None, num=None, **opts)`

**用法**

- 基本调用

```python
pro.stocks(keyword='茅台', limit=5)
```

**进阶用法**

- 进阶参数组合

```python
pro.stocks(market='SS', page=1, num=10)
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.stocks(keyword='茅台', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.stocks(keyword='茅台', limit=5, as_dataframe=False)
```

**数据样例**

| `code` | `market` | `name` | `symbol` | `update_time` |
| --- | --- | --- | --- | --- |
| 600519 | sh | 贵州茅台 | 600519.SS | 2026-07-14 15:15:15 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 600519 |
| `market` | 市场 | sh |
| `name` | 名称 | 贵州茅台 |
| `symbol` | 标的代码 | 600519.SS |
| `update_time` | 更新时间 | 2026-07-14 15:15:15 |

### `corp`

- **路径：** `/v1/corp`
- **类型：** http
- **说明：** 公司资料
- **签名：** `pro.corp(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.corp(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.corp(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.corp(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.corp(ks_code='sh600519')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `fetched_at` | 2026-07-23T12:57:38 |
| `governance_documents` | [] |
| `indices_refreshed_at` | 2026-07-23T12:57:38 |

**`capital` 展开**

| 字段 | 值 |
|------|-----|
| `a_shares` | 125008 |
| `b_shares` | 0 |
| `float_a_shares` | 125008 |
| `float_b_shares` | 0 |
| `float_shares` | 125008 |
| `h_shares` | 0 |
| `total_shares` | 125008 |
| `unit` | 万股 |

**`currencies` 展开**

| 字段 | 值 |
|------|-----|
| `a` | CNY |
| `b` |  |
| `h` |  |

**`classification` 展开**

| 字段 | 值 |
|------|-----|
| `concepts` | ["保险重仓", "QFII重仓", "基金重仓", "奢侈品", "融资融券", "白酒概念… |

**`industry` 展开**

| 字段 | 值 |
|------|-----|
| `name` | 白酒 |
| `standard` | 申万行业分类 |

**`company` 展开**

| 字段 | 值 |
|------|-----|
| `disclosure_url` |  |
| `english_name` | Kweichow Moutai Co.,Ltd. |
| `founded_date` | 1999-11-20 |
| `full_name` | 贵州茅台酒股份有限公司 |
| `institution_type` | 其它 |
| `introduction` | 公司是根据贵州省人民政府黔府函〔1999〕291号文,由中国贵州茅台酒厂有限责任公司作为主发起… |
| `main_business` | 贵州茅台酒系列产品的生产与销售,饮料、食品、包装材料的生产与销售,防伪技术开发;信息产业相关产… |
| `office_address` | 贵州省仁怀市茅台镇 |
| `organization_form` |  |
| `registered_address` | 贵州省仁怀市茅台镇 |
| `registered_capital` | 125008万元(CNY) |
| `registered_capital_currency` | CNY |
| `website` | http://www.moutaichina.com |

**`contact` 展开**

| 字段 | 值 |
|------|-----|
| `email` | *** |
| `fax` | 0851-22386193 |
| `phone` | *** |
| `zip_code` | 564501 |

**`secretary` 展开**

| 字段 | 值 |
|------|-----|
| `email` | *** |
| `fax` | 0851-22386193 |
| `name` | 余思明 |
| `phone` | *** |

**`financials` 展开**

| 字段 | 值 |
|------|-----|
| `avg_price_5d` | 164.338 |
| `bps` | 216.322 |
| `eps` | 823.201 |
| `eps_last_year` | 65.66 |
| `eps_ttm` | 827.151 |

**`close_price_days_ago` 展开**

| 字段 | 值 |
|------|-----|
| `10` | 1268 |
| `120` | 1422 |
| `20` | 1311 |
| `250` | 1486.11 |
| `5` | 1279 |
| `60` | 1445 |

**`indices` 展开（20 条）**

| `code` | `enter_date` | `exit_date` | `name` |
| --- | --- | --- | --- |
| 000010 | 2002-07-01 |  | 上证180 |
| 823000 |  |  | 经常消费 |
| 816100 |  |  | 中信大盘 |
| 816110 | 1900-01-01 |  | 大盘价值 |
| 816050 | 2004-01-02 |  | 中标50 |

（共 20 行，表中展示前 5 行）

**`management` 展开（20 条）**

| `end_date` | `group` | `name` | `start_date` | `title` |
| --- | --- | --- | --- | --- |
| -- | 高管 | 王莉 | 2023-08-19 | 代理总经理 |
| -- | 高管 | 王莉 | 2023-08-17 | 党委副书记 |
| -- | 高管 | 涂华彬 | 2026-06-11 | 副总经理 |
| -- | 高管 | 向平 | 2024-08-16 | 党委委员 |
| -- | 高管 | 向平 | 2024-08-16 | 副总经理 |

（共 20 行，表中展示前 5 行）

**`related_securities` 展开（2 条）**

| `code` | `name` |
| --- | --- |
| 600519 | 贵州茅台 |
| 580990 | 茅台JCP1 |

**`security` 展开**

| 字段 | 值 |
|------|-----|
| `code` | 600519 |
| `exchange` | sh |
| `former_names` | G茅台 贵州茅台 |
| `ipo_price` | 31.39 |
| `list_date` | 2001-08-27 |
| `market` | 上海证券交易所 |
| `security_type` | EQA |
| `short_name` | 贵州茅台 |
| `stock_class` | A |
| `symbol` | 600519.SS |
| `underwriter` | 南方证券有限公司 |

**`related_codes` 展开**

| 字段 | 值 |
|------|-----|
| `a` | 600519.SS |
| `b` |  |
| `hk` |  |

**`trading` 展开**

| 字段 | 值 |
|------|-----|
| `status` | 1 |
| `transfer_flag` | 1 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `capital` | 股本 | {9 字段，见下方展开} |
| `classification` | 分类 | {2 字段，见下方展开} |
| `company` | 公司 | {13 字段，见下方展开} |
| `contact` | 联系方式 | {5 字段，见下方展开} |
| `fetched_at` | 拉取时间 | 2026-07-23T12:57:38 |
| `financials` | 财务数据 | {6 字段，见下方展开} |
| `governance_documents` | 治理文件 | [] |
| `indices` | 指数列表 | [20 项，见下方展开] |
| `indices_refreshed_at` | 指数刷新时间 | 2026-07-23T12:57:38 |
| `management` | 管理层 | [20 项，见下方展开] |
| `related_securities` | 关联证券 | [2 项，见下方展开] |
| `security` | 证券 | {12 字段，见下方展开} |
| `trading` | 交易中 | {2 字段，见下方展开} |
| `capital.a_shares` | 股本 → A 股股本 | 125008 |
| `capital.b_shares` | 股本 → B 股股本 | 0 |
| `capital.currencies` | 股本 → 币种列表 | {"a": "CNY", "b": "", "h": ""} |
| `capital.float_a_shares` | 股本 → 流通 A 股 | 125008 |
| `capital.float_b_shares` | 股本 → 流通 B 股 | 0 |
| `capital.float_shares` | 股本 → 流通股本 | 125008 |
| `capital.h_shares` | 股本 → H 股股本 | 0 |
| `capital.total_shares` | 股本 → 总股本 | 125008 |
| `capital.unit` | 股本 → 单位 | 万股 |
| `capital.currencies.a` | 股本 → 字段 `currencies.a` |  |
| `capital.currencies.b` | 股本 → 字段 `currencies.b` |  |
| `capital.currencies.h` | 股本 → 字段 `currencies.h` |  |
| `classification.concepts` | 分类 → 概念列表 | ["保险重仓", "QFII重仓", "基金重仓", "奢侈品", "融资融券", "白酒概念… |
| `classification.industry` | 分类 → 行业 | {"name": "白酒", "standard": "申万行业分类"} |
| `classification.industry.name` | 分类 → 字段 `industry.name` |  |
| `classification.industry.standard` | 分类 → 字段 `industry.standard` |  |
| `company.disclosure_url` | 公司 → 披露链接 |  |
| `company.english_name` | 公司 → 英文名 | Kweichow Moutai Co.,Ltd. |
| `company.founded_date` | 公司 → 成立日期 | 1999-11-20 |
| `company.full_name` | 公司 → 全称 | 贵州茅台酒股份有限公司 |
| `company.institution_type` | 公司 → 机构类型 | 其它 |
| `company.introduction` | 公司 → 介绍 | 公司是根据贵州省人民政府黔府函〔1999〕291号文,由中国贵州茅台酒厂有限责任公司作为主发起… |
| `company.main_business` | 公司 → 主营业务 | 贵州茅台酒系列产品的生产与销售,饮料、食品、包装材料的生产与销售,防伪技术开发;信息产业相关产… |
| `company.office_address` | 公司 → 办公地址 | 贵州省仁怀市茅台镇 |
| `company.organization_form` | 公司 → 组织形式 |  |
| `company.registered_address` | 公司 → 注册地址 | 贵州省仁怀市茅台镇 |
| `company.registered_capital` | 公司 → 注册资本 | 125008万元(CNY) |
| `company.registered_capital_currency` | 公司 → 注册资本币种 | CNY |
| `company.website` | 公司 → 官网 | http://www.moutaichina.com |
| `contact.email` | 联系方式 → 邮箱 | *** |
| `contact.fax` | 联系方式 → 传真 | 0851-22386193 |
| `contact.phone` | 联系方式 → 电话 | *** |
| `contact.secretary` | 联系方式 → 董秘 | {"email": "***", "fax": "0851-22386193", "name"… |
| `contact.zip_code` | 联系方式 → 邮编 | 564501 |
| `contact.secretary.email` | 联系方式 → 字段 `secretary.email` |  |
| `contact.secretary.fax` | 联系方式 → 字段 `secretary.fax` |  |
| `contact.secretary.name` | 联系方式 → 字段 `secretary.name` |  |
| `contact.secretary.phone` | 联系方式 → 字段 `secretary.phone` |  |
| `financials.avg_price_5d` | 财务数据 → 近5日均价 | 164.338 |
| `financials.bps` | 财务数据 → 每股净资产 | 216.322 |
| `financials.close_price_days_ago` | 财务数据 → N 日前收盘价 | {"10": 1268.0, "120": 1422.0, "20": 1311.0, "25… |
| `financials.eps` | 财务数据 → 每股收益 | 823.201 |
| `financials.eps_last_year` | 财务数据 → 去年每股收益 | 65.66 |
| `financials.eps_ttm` | 财务数据 → TTM 每股收益 | 827.151 |
| `financials.close_price_days_ago.10` | 财务数据 → 字段 `close_price_days_ago.10` |  |
| `financials.close_price_days_ago.120` | 财务数据 → 字段 `close_price_days_ago.120` |  |
| `financials.close_price_days_ago.20` | 财务数据 → 字段 `close_price_days_ago.20` |  |

（共 91 个字段，表中展示前 60 个）

### `finance_report`

- **路径：** `/v1/finance/report`
- **类型：** http
- **说明：** 财务报表
- **签名：** `pro.finance_report(symbol=None, *, ks_code=None, source=None, periods=None, year=None, years=None, period=None, **opts)`

**用法**

- 基本调用

```python
pro.finance_report(symbol='600519.SS')
```

**进阶用法**

- 进阶参数组合

```python
pro.finance_report(symbol='600519.SS', year=2024, period='Q4')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.finance_report(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.finance_report(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.finance_report(ks_code='sh600519')
```

- 数据源

```python
pro.finance_report(symbol='600519.SS', source='default')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `code` | 600519 |
| `latest_publish_date` | 20260815 |
| `name` | 贵州茅台 |
| `symbol` | 600519.SS |
| `unit` | CNY |
| `updated_at` | 2026-08-25T04:41:01 |

**`reports` 展开**


**`balance` 展开**

| 字段 | 值 |
|------|-----|
| `count` | 8 |
| `fields` | {"ACCHELDFORS": {"title": "划分为持有待售的资产"}, "ACCOP… |
| `label` | 资产负债表 |
| `periods` | [8 项，见下方展开] |
| `values` | {"20240930": {"ACCHELDFORS": {"value": null, "y… |

**`cashflow` 展开**

| 字段 | 值 |
|------|-----|
| `count` | 8 |
| `fields` | {"ACQUASSETCASH": {"title": "购建固定资产、无形资产和其他长期资产… |
| `label` | 现金流量表 |
| `periods` | [8 项，见下方展开] |
| `values` | {"20240930": {"ACQUASSETCASH": {"value": 287436… |

**`income` 展开**

| 字段 | 值 |
|------|-----|
| `count` | 8 |
| `fields` | {"AMORTIZCOSTASSETSSAPI": {"title": "以摊余成本计量的金融… |
| `label` | 利润表 |
| `periods` | [8 项，见下方展开] |
| `values` | {"20240930": {"AMORTIZCOSTASSETSSAPI": {"value"… |

**`metrics` 展开**

| 字段 | 值 |
|------|-----|
| `count` | 8 |
| `fields` | {"ACCPAYRT": {"title": "应付账款周转率"}, "ACCPAYTDAYS… |
| `label` | 关键指标 |
| `periods` | [8 项，见下方展开] |
| `values` | {"20240930": {"ACCPAYRT": {"value": 4.183531, "… |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 600519 |
| `latest_publish_date` | 最近披露日 | 20260815 |
| `name` | 名称 | 贵州茅台 |
| `reports` | 报告列表 | {4 字段，见下方展开} |
| `symbol` | 标的代码 | 600519.SS |
| `unit` | 单位 | CNY |
| `updated_at` | 更新时间 | 2026-08-25T04:41:01 |
| `reports.balance` | 报告列表 → 资产负债表 | {"count": 8, "fields": {"ACCHELDFORS": {"title"… |
| `reports.cashflow` | 报告列表 → 现金流量表 | {"count": 8, "fields": {"ACQUASSETCASH": {"titl… |
| `reports.income` | 报告列表 → 利润表 | {"count": 8, "fields": {"AMORTIZCOSTASSETSSAPI"… |
| `reports.metrics` | 报告列表 → 指标集 | {"count": 8, "fields": {"ACCPAYRT": {"title": "… |
| `reports.balance.count` | 报告列表 → 字段 `balance.count` |  |
| `reports.balance.fields` | 报告列表 → 字段 `balance.fields` |  |
| `reports.balance.label` | 报告列表 → 字段 `balance.label` |  |
| `reports.balance.periods` | 报告列表 → 字段 `balance.periods` |  |
| `reports.balance.values` | 报告列表 → 字段 `balance.values` |  |
| `reports.cashflow.count` | 报告列表 → 字段 `cashflow.count` |  |
| `reports.cashflow.fields` | 报告列表 → 字段 `cashflow.fields` |  |
| `reports.cashflow.label` | 报告列表 → 字段 `cashflow.label` |  |
| `reports.cashflow.periods` | 报告列表 → 字段 `cashflow.periods` |  |
| `reports.cashflow.values` | 报告列表 → 字段 `cashflow.values` |  |
| `reports.income.count` | 报告列表 → 字段 `income.count` |  |
| `reports.income.fields` | 报告列表 → 字段 `income.fields` |  |
| `reports.income.label` | 报告列表 → 字段 `income.label` |  |
| `reports.income.periods` | 报告列表 → 字段 `income.periods` |  |
| `reports.income.values` | 报告列表 → 字段 `income.values` |  |
| `reports.metrics.count` | 报告列表 → 字段 `metrics.count` |  |
| `reports.metrics.fields` | 报告列表 → 字段 `metrics.fields` |  |
| `reports.metrics.label` | 报告列表 → 字段 `metrics.label` |  |
| `reports.metrics.periods` | 报告列表 → 字段 `metrics.periods` |  |
| `reports.metrics.values` | 报告列表 → 字段 `metrics.values` |  |

### `calendar`

- **路径：** `/v1/calendar`
- **类型：** http
- **说明：** 交易日历
- **签名：** `pro.calendar(*, date=None, start=None, end=None, window=None, **opts)`

**用法**

- 基本调用

```python
pro.calendar()
```

**进阶用法**

- 进阶参数组合

```python
pro.calendar(start='20250101', end='20250131')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.calendar(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.calendar(as_dataframe=False)
```

- 指定交易日

```python
pro.calendar(date='20250102')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `future_trading_days` | ["2026-09-28", "2026-09-29", "2026-09-30", "202… |
| `latest_trading_day` | 2026-09-24 |
| `market` | CN |
| `next_trading_day` | 2026-09-28 |
| `recent_trading_days` | ["2026-09-24", "2026-09-23", "2026-09-22", "202… |

**`trading_sessions` 展开（2 条）**

| `end` | `name` | `start` |
| --- | --- | --- |
| 11:30 | morning | 09:15 |
| 15:00 | afternoon | 13:00 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `future_trading_days` | 未来交易日 | ["2026-09-28", "2026-09-29", "2026-09-30", "202… |
| `latest_trading_day` | 最近交易日 | 2026-09-24 |
| `market` | 市场 | CN |
| `next_trading_day` | 下一交易日 | 2026-09-28 |
| `recent_trading_days` | 近期交易日 | ["2026-09-24", "2026-09-23", "2026-09-22", "202… |
| `trading_sessions` | 交易时段 | [2 项，见下方展开] |
| `trading_sessions.end` | 交易时段 → 结束 | 11:30 |
| `trading_sessions.name` | 交易时段 → 名称 | morning |
| `trading_sessions.start` | 交易时段 → 开始 | 09:15 |

## 指数 / ETF

### `index_realtime`

- **路径：** `/v1/index/realtime`
- **类型：** http
- **说明：** 指数实时
- **签名：** `pro.index_realtime(symbol=None, *, ks_code=None, include_valuation=None, include_depth=None, **opts)`

**用法**

- 基本调用

```python
pro.index_realtime(symbol='000001.SH')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.index_realtime(ks_code='000001.SH')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.index_realtime(symbol='000001.SH', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.index_realtime(symbol='000001.SH', as_dataframe=False)
```

- 附带估值字段

```python
pro.index_realtime(symbol='000001.SH', include_valuation=True)
```

- 附带盘口深度

```python
pro.index_realtime(symbol='000001.SH', include_depth=True)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `change` | -15.6081 |
| `change_percent` | -0.00394929 |
| `close` | 3936.52 |
| `date` | 20260923 |
| `high` | 3951.52 |
| `low` | 3934.46 |
| `name` | 上证指数 |
| `open` | 3951.37 |
| `pre_close` | 3952.13 |
| `price` | 3936.52 |
| `symbol` | 000001.SS |
| `timestamp` | 1790147097000 |
| `trade_status` | BREAK |
| `turnover` | 8.34133e+11 |
| `volume` | 4.66914e+10 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change` | 涨跌额 | -15.6081 |
| `change_percent` | 涨跌幅（%） | -0.00394929 |
| `close` | 收盘价 / 最新价 | 3936.52 |
| `date` | 交易日 | 20260923 |
| `high` | 最高价 | 3951.52 |
| `low` | 最低价 | 3934.46 |
| `name` | 名称 | 上证指数 |
| `open` | 开盘价 | 3951.37 |
| `pre_close` | 昨收 | 3952.13 |
| `price` | 最新价 | 3936.52 |
| `symbol` | 标的代码 | 000001.SS |
| `timestamp` | 时间戳（毫秒） | 1790147097000 |
| `trade_status` | 交易状态 | BREAK |
| `turnover` | 换手相关 | 8.34133e+11 |
| `volume` | 成交量 | 4.66914e+10 |

### `index_trend`

- **路径：** `/v1/index/trend`
- **类型：** http
- **说明：** 指数分时
- **签名：** `pro.index_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.index_trend(symbol='000001.SH')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.index_trend(symbol='000001.SH', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.index_trend(symbol='000001.SH', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.index_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.index_trend(symbol='000001.SH', date='20250102')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `date` |  |
| `pre_close` | 3952.13 |
| `symbol` |  |
| `total` | 241 |

**`data` 展开（20 条）**

| `avg_price` | `change` | `change_percent` | `high` | `low` | `open` | `price` | `timestamp` | `turnover` | `volume` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3951.37 | -0.7617 | -0.0192732 | 3951.96 | 3951.37 | 3951.96 | 3951.37 | 1790127000000 | 0 | 0 |
| 3949.47 | -4.5538 | -0.115224 | 3951.52 | 3946.89 | 3951.52 | 3947.57 | 1790127060000 | 3.0465e+10 | 17313716 |
| 3949.73 | -1.8761 | -0.0474706 | 3950.25 | 3947.32 | 3947.32 | 3950.25 | 1790127120000 | 1.64672e+10 | 9286630 |
| 3948.85 | -5.9402 | -0.150304 | 3949.62 | 3945.69 | 3949.62 | 3946.19 | 1790127180000 | 1.45384e+10 | 8555184 |
| 3948.18 | -6.6311 | -0.167786 | 3947.47 | 3944.7 | 3945.67 | 3945.5 | 1790127240000 | 1.24466e+10 | 6608241 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `data` | 业务数据（可展开） | [20 项，见下方展开] |
| `date` | 交易日 |  |
| `pre_close` | 昨收 | 3952.13 |
| `symbol` | 标的代码 |  |
| `total` | 总数 | 241 |
| `data.avg_price` | 业务数据（可展开） → 均价 | 3951.37 |
| `data.change` | 业务数据（可展开） → 涨跌额 | -0.7617 |
| `data.change_percent` | 业务数据（可展开） → 涨跌幅（%） | -0.0192732 |
| `data.high` | 业务数据（可展开） → 最高价 | 3951.96 |
| `data.low` | 业务数据（可展开） → 最低价 | 3951.37 |
| `data.open` | 业务数据（可展开） → 开盘价 | 3951.96 |
| `data.price` | 业务数据（可展开） → 最新价 | 3951.37 |
| `data.timestamp` | 业务数据（可展开） → 时间戳（毫秒） | 1790127000000 |
| `data.turnover` | 业务数据（可展开） → 换手相关 | 0 |
| `data.volume` | 业务数据（可展开） → 成交量 | 0 |

### `index_kline`

- **路径：** `/v2/index/kline`
- **类型：** http
- **说明：** 指数K线
- **签名：** `pro.index_kline(symbol=None, *, ks_code=None, period=None, count=None, timestamp=None, source=None, format='raw', **opts)`

**用法**

- 基本调用

```python
pro.index_kline(symbol='000001.SH', period=86400, count=3)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.index_kline(symbol='000001.SH', period=86400, count=3, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.index_kline(symbol='000001.SH', period=86400, count=3, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.index_kline(ks_code='sh600519', period=86400, count=3)
```

- 翻页游标（请求参数为秒）

```python
pro.index_kline(symbol='000001.SH', period=86400, count=3, timestamp=1700000000)
```

- 数据源

```python
pro.index_kline(symbol='000001.SH', period=86400, count=3, source='default')
```

- 不传 `format=raw`，改用服务端列式数组

```python
pro.index_kline(symbol='000001.SH', period=86400, count=3, format=None)
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` | `turnover` | `average_px` | `px_change` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 000001.SS | 20260921 | 1789948800000 | 3920.27 | 3950.94 | 3918.13 | 3949.91 | 50235487700 |  | 9.46819e+11 | 0 | 38.0354 |
| 000001.SS | 20260922 | 1790035200000 | 3963.81 | 3967.68 | 3945.42 | 3952.13 | 50614836900 |  | 1.008e+12 | 0 | 2.2212 |
| 000001.SS | 20260923 | 1790121600000 | 3951.37 | 3951.52 | 3934.46 | 3936.52 | 46691393300 |  | 8.34133e+11 | 0 | -15.6081 |

（共 3 行、前 12/15 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | 000001.SS |
| `date` | 交易日 | 20260921 |
| `timestamp` | 时间戳（毫秒） | 1789948800000 |
| `open` | 开盘价 | 3920.27 |
| `high` | 最高价 | 3950.94 |
| `low` | 最低价 | 3918.13 |
| `close` | 收盘价 / 最新价 | 3949.91 |
| `volume` | 成交量 | 50235487700 |
| `amount` | 成交额 |  |
| `turnover` | 换手相关 | 9.46819e+11 |
| `average_px` | 均价 | 0 |
| `px_change` | 涨跌额 | 38.0354 |
| `px_change_rate` | 涨跌幅 | 0.972307 |
| `avg_px` | 均价 | 0 |
| `turnover_ratio` | 换手率 | 0 |

### `etf`

- **路径：** `/v1/etf`
- **类型：** http
- **说明：** 基金资料
- **签名：** `pro.etf(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.etf(symbol='510300.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.etf(symbol='510300.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.etf(symbol='510300.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.etf(ks_code='sh600519')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `aum` | 224.85B |
| `aum_yi` | 2280.79 |
| `avg_volume_10d` | 1.16B |
| `benchmark` | 沪深300指数 |
| `category` | 股票-规模 |
| `code` | 510300 |
| `custodian` | 中国工商银行股份有限公司 |
| `custodian_fee` | 0.05% |
| `e_sname` |  |
| `finance_style` | 价值型 |
| `full_name` | 华泰柏瑞沪深300交易型开放式指数证券投资基金 |
| `fund_subtype` | 指数型 |
| `fund_type` | 股票型 |
| `has_basic` | True |
| `inception_date` | 2012-05-04 |
| `invest_scope` | 本基金以标的指数成份股、备选成份股为主要投资对象。此外，为更好地实现投资目标，本基金可少量投资… |
| `invest_target` | 紧密跟踪标的指数表现，追求跟踪偏离度和跟踪误差的最小化。本基金力争将日均跟踪偏离度控制在0.2… |
| `listing_date` |  |
| `management_fee` | 0.15% |
| `manager_company` | 华泰柏瑞基金管理有限公司 |
| `manager_name` | 柳军 |
| `market` | sh |
| `operation_type` | 开放式 |
| `premium` | 0.0000% |
| `premium_date` | 20260709 |
| `scale_style` | 大盘 |
| `sname` | 华泰柏瑞沪深300ETF |
| `symbol` | 510300.SS |
| `updated_at` | 2026-06-23T11:46:24 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `aum` | 资产管理规模 | 224.85B |
| `aum_yi` | 规模（亿） | 2280.79 |
| `avg_volume_10d` | 近10日均量 | 1.16B |
| `benchmark` | 业绩比较基准 | 沪深300指数 |
| `category` | 分类 | 股票-规模 |
| `code` | 代码 | 510300 |
| `custodian` | 托管人 | 中国工商银行股份有限公司 |
| `custodian_fee` | 托管费 | 0.05% |
| `e_sname` | 英文简称 |  |
| `finance_style` | 财务风格 | 价值型 |
| `full_name` | 全称 | 华泰柏瑞沪深300交易型开放式指数证券投资基金 |
| `fund_subtype` | 基金子类型 | 指数型 |
| `fund_type` | 基金类型 | 股票型 |
| `has_basic` | 是否含基础字段 | True |
| `inception_date` | 成立日 | 2012-05-04 |
| `invest_scope` | 投资范围 | 本基金以标的指数成份股、备选成份股为主要投资对象。此外，为更好地实现投资目标，本基金可少量投资… |
| `invest_target` | 投资目标 | 紧密跟踪标的指数表现，追求跟踪偏离度和跟踪误差的最小化。本基金力争将日均跟踪偏离度控制在0.2… |
| `listing_date` | 上市日期 |  |
| `management_fee` | 管理费 | 0.15% |
| `manager_company` | 管理人 | 华泰柏瑞基金管理有限公司 |
| `manager_name` | 基金经理 | 柳军 |
| `market` | 市场 | sh |
| `operation_type` | 操作类型 | 开放式 |
| `premium` | 溢价率 | 0.0000% |
| `premium_date` | 溢价日期 | 20260709 |
| `scale_style` | 规模风格 | 大盘 |
| `sname` | 证券简称 | 华泰柏瑞沪深300ETF |
| `symbol` | 标的代码 | 510300.SS |
| `updated_at` | 更新时间 | 2026-06-23T11:46:24 |

### `etfs`

- **路径：** `/v1/etfs`
- **类型：** http
- **说明：** 基金列表
- **签名：** `pro.etfs(*, keyword=None, market=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.etfs(keyword='沪深300', limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.etfs(keyword='沪深300', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.etfs(keyword='沪深300', limit=5, as_dataframe=False)
```

- 指定市场（如 `SS` / `SZ`）

```python
pro.etfs(keyword='沪深300', limit=5, market='SS')
```

**数据样例**

| `aum` | `aum_yi` | `avg_volume_10d` | `benchmark` | `category` | `code` | `custodian` | `custodian_fee` | `e_sname` | `finance_style` | `full_name` | `fund_subtype` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 104.48B | 1059.3 | 438.27M | 沪深300指数 | 股票-规模 | 159919 | 中国银行股份有限公司 | 0.05% | CSI300ETF | 价值型 | 嘉实沪深300交易型开放式指数证券投资基金 | 指数型 |
| 2.87B | 29.13 | 17.12M | 沪深300指数 | 股票-规模 | 159925 | 中国工商银行股份有限公司 | 0.05% | CS300ETF | 价值型 | 南方沪深300交易型开放式指数证券投资基金 | 指数型 |
| 105.82M | 1.1 | 159300 | 沪深300金融地产指数 | 股票-行业 | 159933 | 中国工商银行股份有限公司 | 0.13% | FINANCIALS ETF | 价值型 | 国投瑞银沪深300金融地产交易型开放式指数证券投资基金 | 指数型 |
| 703.73M | 7.12 | 17737 | 沪深300指数收益率×95%+银行活期存款利率(税后)×5% | 股票-规模 | 160615 | 中国工商银行股份有限公司 | 0.05% | PENGHUA CSI300 FUND | 价值型 | 鹏华沪深300交易型开放式指数证券投资基金联接基金(LOF) | 指数型 |
| 8.14B | 82.44 | 1.47M | 95%×沪深300指数增长率+5%×银行活期存款税后利率 | 股票-规模 | 160706 | 中国银行股份有限公司 | 0.05% | HARVEST SHSZ300 A | 价值型 | 嘉实沪深300交易型开放式指数证券投资基金联接基金(LOF) | 指数型 |

（共 5 行、前 12/29 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `aum` | 资产管理规模 | 104.48B |
| `aum_yi` | 规模（亿） | 1059.3 |
| `avg_volume_10d` | 近10日均量 | 438.27M |
| `benchmark` | 业绩比较基准 | 沪深300指数 |
| `category` | 分类 | 股票-规模 |
| `code` | 代码 | 159919 |
| `custodian` | 托管人 | 中国银行股份有限公司 |
| `custodian_fee` | 托管费 | 0.05% |
| `e_sname` | 英文简称 | CSI300ETF |
| `finance_style` | 财务风格 | 价值型 |
| `full_name` | 全称 | 嘉实沪深300交易型开放式指数证券投资基金 |
| `fund_subtype` | 基金子类型 | 指数型 |
| `fund_type` | 基金类型 | 股票型 |
| `has_basic` | 是否含基础字段 | True |
| `inception_date` | 成立日 | 2012-05-07 |
| `invest_scope` | 投资范围 | 本基金投资范围主要为标的指数成份股及备选成份股（含存托凭证，下同），投资于标的指数成份股及备选… |
| `invest_target` | 投资目标 | 本基金进行被动式指数化投资，紧密跟踪标的指数，追求跟踪偏离度和跟踪误差的最小化。 |
| `listing_date` | 上市日期 |  |
| `management_fee` | 管理费 | 0.15% |
| `manager_company` | 管理人 | 嘉实基金管理有限公司 |
| `manager_name` | 基金经理 | 刘珈吟 |
| `market` | 市场 | sz |
| `operation_type` | 操作类型 | 开放式 |
| `premium` | 溢价率 | -0.0234% |
| `premium_date` | 溢价日期 | 20260709 |
| `scale_style` | 规模风格 | 大盘 |
| `sname` | 证券简称 | 嘉实沪深300ETF |
| `symbol` | 标的代码 | 159919.SZ |
| `updated_at` | 更新时间 | 2026-06-23T11:45:21 |

### `etf_realtime`

- **路径：** `/v1/etf/realtime`
- **类型：** http
- **说明：** 基金实时
- **签名：** `pro.etf_realtime(symbol=None, *, ks_code=None, include_valuation=None, include_depth=None, **opts)`

**用法**

- 基本调用

```python
pro.etf_realtime(symbol='510300.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.etf_realtime(symbol='510300.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.etf_realtime(symbol='510300.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.etf_realtime(ks_code='sh600519')
```

- 附带估值字段

```python
pro.etf_realtime(symbol='510300.SS', include_valuation=True)
```

- 附带盘口深度

```python
pro.etf_realtime(symbol='510300.SS', include_depth=True)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `change` | -0.023 |
| `change_percent` | -0.00498591 |
| `close` | 4.59 |
| `date` | 20260923 |
| `high` | 4.621 |
| `low` | 4.586 |
| `name` | 沪深300ETF华泰柏瑞 |
| `open` | 4.62 |
| `pre_close` | 4.613 |
| `price` | 4.59 |
| `symbol` | 510300.SS |
| `timestamp` | 1790146800000 |
| `trade_status` | BREAK |
| `turnover` | 2.92854e+09 |
| `volume` | 6.36458e+08 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change` | 涨跌额 | -0.023 |
| `change_percent` | 涨跌幅（%） | -0.00498591 |
| `close` | 收盘价 / 最新价 | 4.59 |
| `date` | 交易日 | 20260923 |
| `high` | 最高价 | 4.621 |
| `low` | 最低价 | 4.586 |
| `name` | 名称 | 沪深300ETF华泰柏瑞 |
| `open` | 开盘价 | 4.62 |
| `pre_close` | 昨收 | 4.613 |
| `price` | 最新价 | 4.59 |
| `symbol` | 标的代码 | 510300.SS |
| `timestamp` | 时间戳（毫秒） | 1790146800000 |
| `trade_status` | 交易状态 | BREAK |
| `turnover` | 换手相关 | 2.92854e+09 |
| `volume` | 成交量 | 6.36458e+08 |

### `etf_trend`

- **路径：** `/v1/etf/trend`
- **类型：** http
- **说明：** 基金分时
- **签名：** `pro.etf_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.etf_trend(symbol='510300.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.etf_trend(symbol='510300.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.etf_trend(symbol='510300.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.etf_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.etf_trend(symbol='510300.SS', date='20250102')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `date` |  |
| `pre_close` | 4.613 |
| `symbol` |  |
| `total` | 241 |

**`data` 展开（20 条）**

| `avg_price` | `change` | `change_percent` | `high` | `low` | `open` | `price` | `timestamp` | `turnover` | `volume` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4.619 | 0.006 | 0.130067 | 4.626 | 4.619 | 4.625 | 4.619 | 1790127000000 | 0 | 0 |
| 4.61935 | 0.006 | 0.130067 | 4.62 | 4.618 | 4.62 | 4.619 | 1790127060000 | 48441259 | 10486600 |
| 4.61897 | 0.005 | 0.108389 | 4.62 | 4.617 | 4.62 | 4.618 | 1790127120000 | 50585352 | 10952500 |
| 4.6178 | 0.001 | 0.0216779 | 4.619 | 4.614 | 4.619 | 4.614 | 1790127180000 | 56833062 | 12312500 |
| 4.6167 | 0.003 | 0.0650336 | 4.617 | 4.612 | 4.613 | 4.616 | 1790127240000 | 66972885 | 14514300 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `data` | 业务数据（可展开） | [20 项，见下方展开] |
| `date` | 交易日 |  |
| `pre_close` | 昨收 | 4.613 |
| `symbol` | 标的代码 |  |
| `total` | 总数 | 241 |
| `data.avg_price` | 业务数据（可展开） → 均价 | 4.619 |
| `data.change` | 业务数据（可展开） → 涨跌额 | 0.006 |
| `data.change_percent` | 业务数据（可展开） → 涨跌幅（%） | 0.130067 |
| `data.high` | 业务数据（可展开） → 最高价 | 4.626 |
| `data.low` | 业务数据（可展开） → 最低价 | 4.619 |
| `data.open` | 业务数据（可展开） → 开盘价 | 4.625 |
| `data.price` | 业务数据（可展开） → 最新价 | 4.619 |
| `data.timestamp` | 业务数据（可展开） → 时间戳（毫秒） | 1790127000000 |
| `data.turnover` | 业务数据（可展开） → 换手相关 | 0 |
| `data.volume` | 业务数据（可展开） → 成交量 | 0 |

### `etf_kline`

- **路径：** `/v2/etf/kline`
- **类型：** http
- **说明：** 基金K线
- **签名：** `pro.etf_kline(symbol=None, *, ks_code=None, period=None, adjust_type=None, count=None, timestamp=None, source=None, format='raw', **opts)`

**用法**

- 基本调用

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.etf_kline(ks_code='sh600519', period=86400, count=3)
```

- 复权类型

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3, adjust_type='forward')
```

- 翻页游标（请求参数为秒）

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3, timestamp=1700000000)
```

- 数据源

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3, source='default')
```

- 不传 `format=raw`，改用服务端列式数组

```python
pro.etf_kline(symbol='510300.SS', period=86400, count=3, format=None)
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` | `turnover` | `average_px` | `px_change` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 510300.SS | 20260921 | 1789948800000 | 4.586 | 4.615 | 4.581 | 4.608 | 570203884 |  | 2624224493 | 0 | 0.026 |
| 510300.SS | 20260922 | 1790035200000 | 4.636 | 4.658 | 4.612 | 4.613 | 644587351 |  | 2987237086 | 0 | 0.005 |
| 510300.SS | 20260923 | 1790121600000 | 4.62 | 4.621 | 4.586 | 4.59 | 636457533 |  | 2928541597 | 0 | -0.023 |

（共 3 行、前 12/15 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | 510300.SS |
| `date` | 交易日 | 20260921 |
| `timestamp` | 时间戳（毫秒） | 1789948800000 |
| `open` | 开盘价 | 4.586 |
| `high` | 最高价 | 4.615 |
| `low` | 最低价 | 4.581 |
| `close` | 收盘价 / 最新价 | 4.608 |
| `volume` | 成交量 | 570203884 |
| `amount` | 成交额 |  |
| `turnover` | 换手相关 | 2624224493 |
| `average_px` | 均价 | 0 |
| `px_change` | 涨跌额 | 0.026 |
| `px_change_rate` | 涨跌幅 | 0.567438 |
| `avg_px` | 均价 | 0 |
| `turnover_ratio` | 换手率 | 0 |

## 专题（涨停 / 龙虎榜 / 资金流 / 停复牌等）

### `limit_up`

- **路径：** `/v1/limit-up`
- **类型：** http
- **说明：** 涨停池
- **签名：** `pro.limit_up(**opts)`

**用法**

- 基本调用

```python
pro.limit_up()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up(as_dataframe=False)
```

**数据样例**

| `change_percent` | `consecutive_days` | `first_sealed_at` | `first_sealed_time` | `last_sealed_at` | `last_sealed_time` | `name` | `open_count` | `price` | `symbol` | `turnover_rate` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.099881 | 4 | 1790127016 | 09:30:16 | 1790127016 | 09:30:16 | 新华文轩 | 0 | 18.5 | 601811.SS | 0.021003 |
| 0.100145 | 4 | 1790127039 | 09:30:39 | 1790127039 | 09:30:39 | 大亚圣象 | 0 | 7.58 | 000910.SZ | 0.055118 |
| 0.100171 | 3 | 1790126700 | 09:25:00 | 1790126700 | 09:25:00 | 泰慕士 | 0 | 32.18 | 001234.SZ | 0.030417 |
| 0.099875 | 3 | 1790126700 | 09:25:00 | 1790128717 | 09:58:37 | 南威软件 | 3 | 8.81 | 603636.SS | 0.126182 |
| 0.099688 | 3 | 1790126700 | 09:25:00 | 1790126700 | 09:25:00 | 新华传媒 | 0 | 7.06 | 600825.SS | 0.004383 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.099881 |
| `consecutive_days` | 连板天数 | 4 |
| `first_sealed_at` | 首次封板时间 | 1790127016 |
| `first_sealed_time` | 首次封板时刻 | 09:30:16 |
| `last_sealed_at` | 最后封板时间 | 1790127016 |
| `last_sealed_time` | 最后封板时刻 | 09:30:16 |
| `name` | 名称 | 新华文轩 |
| `open_count` | 打开次数 | 0 |
| `price` | 最新价 | 18.5 |
| `symbol` | 标的代码 | 601811.SS |
| `turnover_rate` | 换手率 | 0.021003 |

### `limit_up_break`

- **路径：** `/v1/limit-up/break`
- **类型：** http
- **说明：** 破板
- **签名：** `pro.limit_up_break(**opts)`

**用法**

- 基本调用

```python
pro.limit_up_break()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up_break(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up_break(as_dataframe=False)
```

**数据样例**

| `break_count` | `change_percent` | `consecutive_days` | `first_break_at` | `first_break_time` | `first_limit_up_at` | `first_limit_up_time` | `name` | `price` | `symbol` | `turnover_rate` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 35 | 0.199875 | 1 | 1790128797 | 09:59:57 | 1790128776 | 09:59:36 | 通用电梯 | 19.21 | 300931.SZ | 0.240062 |
| 24 | 0.200277 | 1 | 1790141501 | 13:31:41 | 1790141297 | 13:28:17 | 慧智微 | 17.32 | 688512.SS | 0.177142 |
| 10 | 0.099715 | 3 | 1790127030 | 09:30:30 | 1790127021 | 09:30:21 | 我爱我家 | 3.86 | 000560.SZ | 0.134532 |
| 9 | 0.100291 | 3 | 1790127645 | 09:40:45 | 1790127069 | 09:31:09 | 奥佳华 | 7.57 | 002614.SZ | 0.297995 |
| 8 | 0.101124 | 3 | 1790129663 | 10:14:23 | 1790127836 | 09:43:56 | 华丽家族 | 2.94 | 600503.SS | 0.258583 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `break_count` | 炸板次数 | 35 |
| `change_percent` | 涨跌幅（%） | 0.199875 |
| `consecutive_days` | 连板天数 | 1 |
| `first_break_at` | 首次炸板时间 | 1790128797 |
| `first_break_time` | 首次炸板时刻 | 09:59:57 |
| `first_limit_up_at` | 首次涨停时间 | 1790128776 |
| `first_limit_up_time` | 首次涨停时刻 | 09:59:36 |
| `name` | 名称 | 通用电梯 |
| `price` | 最新价 | 19.21 |
| `symbol` | 标的代码 | 300931.SZ |
| `turnover_rate` | 换手率 | 0.240062 |

### `limit_down`

- **路径：** `/v1/limit-up/limit-down`
- **类型：** http
- **说明：** 跌停
- **签名：** `pro.limit_down(**opts)`

**用法**

- 基本调用

```python
pro.limit_down()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_down(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_down(as_dataframe=False)
```

**数据样例**

| `break_count` | `change_percent` | `consecutive_down_days` | `first_sealed_at` | `first_sealed_time` | `last_sealed_at` | `last_sealed_time` | `name` | `price` | `symbol` | `turnover_rate` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | -0.100137 | 1 | 1790126700 | 09:25:00 | 1790126700 | 09:25:00 | *ST美芝 | 19.77 | 002856.SZ | 0.010986 |
| 9 | -0.099952 | 1 | 1790126700 | 09:25:00 | 1790128197 | 09:49:57 | 闽东电力 | 18.82 | 000993.SZ | 0.088655 |
| 0 | -0.100292 | 1 | 1790126700 | 09:25:00 | 1790126700 | 09:25:00 | 川大智胜 | 9.24 | 002253.SZ | 0.008651 |
| 9 | -0.210111 | 1 | 1790127051 | 09:30:51 | 1790140916 | 13:21:56 | C沈鼓 | 30 | 601091.SS | 0.558774 |
| 11 | -0.100211 | 1 | 1790127063 | 09:31:03 | 1790128368 | 09:52:48 | 龙头股份 | 8.53 | 600630.SS | 0.141958 |

（共 14 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `break_count` | 炸板次数 | 0 |
| `change_percent` | 涨跌幅（%） | -0.100137 |
| `consecutive_down_days` | 连续下跌天数 | 1 |
| `first_sealed_at` | 首次封板时间 | 1790126700 |
| `first_sealed_time` | 首次封板时刻 | 09:25:00 |
| `last_sealed_at` | 最后封板时间 | 1790126700 |
| `last_sealed_time` | 最后封板时刻 | 09:25:00 |
| `name` | 名称 | *ST美芝 |
| `price` | 最新价 | 19.77 |
| `symbol` | 标的代码 | 002856.SZ |
| `turnover_rate` | 换手率 | 0.010986 |

### `yesterday_limit_up`

- **路径：** `/v1/limit-up/yesterday`
- **类型：** http
- **说明：** 昨日涨停
- **签名：** `pro.yesterday_limit_up(**opts)`

**用法**

- 基本调用

```python
pro.yesterday_limit_up()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.yesterday_limit_up(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.yesterday_limit_up(as_dataframe=False)
```

**数据样例**

| `change_percent` | `name` | `price` | `symbol` | `turnover_rate` | `yesterday_consecutive_days` | `yesterday_first_sealed_at` | `yesterday_first_sealed_time` | `yesterday_last_sealed_at` | `yesterday_last_sealed_time` | `yesterday_open_count` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.069513 | 华瓷股份 | 28.31 | 001216.SZ | 0.231073 | 6 | 1790040300 | 09:25:00 | 1790040300 | 09:25:00 | 0 |
| 0.02943 | 内蒙新华 | 16.79 | 603230.SS | 0.208053 | 5 | 1790040875 | 09:34:35 | 1790041334 | 09:42:14 | 3 |
| 0.053675 | 南华生物 | 12.76 | 000504.SZ | 0.317909 | 4 | 1790040300 | 09:25:00 | 1790040300 | 09:25:00 | 0 |
| 0.100145 | 大亚圣象 | 7.58 | 000910.SZ | 0.055118 | 3 | 1790053935 | 13:12:15 | 1790053935 | 13:12:15 | 0 |
| 0.099881 | 新华文轩 | 18.5 | 601811.SS | 0.021003 | 3 | 1790040300 | 09:25:00 | 1790040300 | 09:25:00 | 0 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.069513 |
| `name` | 名称 | 华瓷股份 |
| `price` | 最新价 | 28.31 |
| `symbol` | 标的代码 | 001216.SZ |
| `turnover_rate` | 换手率 | 0.231073 |
| `yesterday_consecutive_days` | 昨日连板天数 | 6 |
| `yesterday_first_sealed_at` | 昨日首次封板时间 | 1790040300 |
| `yesterday_first_sealed_time` | 昨日首次封板时刻 | 09:25:00 |
| `yesterday_last_sealed_at` | 昨日最后封板时间 | 1790040300 |
| `yesterday_last_sealed_time` | 昨日最后封板时刻 | 09:25:00 |
| `yesterday_open_count` | 昨日打开次数 | 0 |

### `limit_up_ladder`

- **路径：** `/v1/limit-up/ladder`
- **类型：** http
- **说明：** 连板天梯
- **签名：** `pro.limit_up_ladder(**opts)`

**用法**

- 基本调用

```python
pro.limit_up_ladder()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up_ladder(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up_ladder(as_dataframe=False)
```

**数据样例**

| `count` | `height` | `label` | `stocks` |
| --- | --- | --- | --- |
| 2 | 4 | 4连板 | [2 项，见下方展开] |
| 7 | 3 | 3连板 | [7 项，见下方展开] |
| 3 | 2 | 2连板 | [3 项，见下方展开] |
| 39 | 1 | 1连板 | [20 项，见下方展开] |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `count` | 条数 | 2 |
| `height` | 高度/连板高度 | 4 |
| `label` | 标签 | 4连板 |
| `stocks` | 成分股列表 | [2 项，见下方展开] |

### `limit_up_plates_trending`

- **路径：** `/v1/limit-up/plates/trending`
- **类型：** http
- **说明：** 涨停板块热度
- **签名：** `pro.limit_up_plates_trending(*, limit=None, field=None, **opts)`

**用法**

- 基本调用

```python
pro.limit_up_plates_trending(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up_plates_trending(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up_plates_trending(limit=5, as_dataframe=False)
```

**数据样例**

| `change_percent` | `description` | `fall_count` | `fund_flow` | `id` | `limit_up_count` | `name` | `rise_count` | `stocks` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.019055 | 多家公司相继发布调价通知 | 33 | 6.69502e+09 | 19426649 | 4 | PCB板 | 85 | [2 项，见下方展开] |
| 0.036825 | 业界首个端到端实时量子纠错解码器亮相 | 8 | 8.89367e+08 | 91348766 | 1 | 量子计算 | 12 | [2 项，见下方展开] |
| 0.013456 | 矢量网络分析仪（NVA）测试需求增长 | 44 | 9.3353e+08 | 16856569 | 5 | 仪器仪表 | 58 | [2 项，见下方展开] |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.019055 |
| `description` | 描述 | 多家公司相继发布调价通知 |
| `fall_count` | 下跌家数 | 33 |
| `fund_flow` | 资金流向 | 6.69502e+09 |
| `id` | 编号 | 19426649 |
| `limit_up_count` | 涨停家数 | 4 |
| `name` | 名称 | PCB板 |
| `rise_count` | 上涨家数 | 85 |
| `stocks` | 成分股列表 | [2 项，见下方展开] |

### `limit_up_plates_industry`

- **路径：** `/v1/limit-up/plates/industry`
- **类型：** http
- **说明：** 涨停行业板块
- **签名：** `pro.limit_up_plates_industry(*, limit=None, field=None, **opts)`

**用法**

- 基本调用

```python
pro.limit_up_plates_industry(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up_plates_industry(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up_plates_industry(limit=5, as_dataframe=False)
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `id` | `limit_up_count` | `name` | `rise_count` |
| --- | --- | --- | --- | --- | --- | --- |
| 0.021241 | 2 | -8.45347e+06 | 38053809 | 0 | 黄酒 | 2 |
| 0.020702 | 3 | 4.62417e+08 | 1822777 | 0 | 环氧树脂 | 6 |
| 0.020077 | 24 | 7.64859e+08 | 26021321 | 0 | 疫苗 | 20 |
| 0.019055 | 33 | 6.69502e+09 | 19426649 | 4 | PCB板 | 85 |
| 0.013593 | 13 | 1.34955e+08 | 17380377 | 1 | 水泥 | 17 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.021241 |
| `fall_count` | 下跌家数 | 2 |
| `fund_flow` | 资金流向 | -8.45347e+06 |
| `id` | 编号 | 38053809 |
| `limit_up_count` | 涨停家数 | 0 |
| `name` | 名称 | 黄酒 |
| `rise_count` | 上涨家数 | 2 |

### `limit_up_plates_concept`

- **路径：** `/v1/limit-up/plates/concept`
- **类型：** http
- **说明：** 涨停概念板块
- **签名：** `pro.limit_up_plates_concept(*, limit=None, field=None, **opts)`

**用法**

- 基本调用

```python
pro.limit_up_plates_concept(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up_plates_concept(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up_plates_concept(limit=5, as_dataframe=False)
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `id` | `limit_up_count` | `name` | `rise_count` |
| --- | --- | --- | --- | --- | --- | --- |
| 0.036825 | 8 | 8.89367e+08 | 91348766 | 1 | 量子计算 | 12 |
| 0.029038 | 2 | 7.78613e+08 | 55250353 | 0 | 金刚线 | 7 |
| 0.026266 | 3 | 1.42689e+09 | 69803577 | 0 | 电子树脂 | 11 |
| 0.024723 | 10 | 1.87722e+09 | 85460510 | 4 | PET复合铜箔 | 29 |
| 0.023621 | 11 | 2.60922e+09 | 92084622 | 1 | 玻璃基板封装 | 36 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.036825 |
| `fall_count` | 下跌家数 | 8 |
| `fund_flow` | 资金流向 | 8.89367e+08 |
| `id` | 编号 | 91348766 |
| `limit_up_count` | 涨停家数 | 1 |
| `name` | 名称 | 量子计算 |
| `rise_count` | 上涨家数 | 12 |

### `limit_up_plates_style`

- **路径：** `/v1/limit-up/plates/style`
- **类型：** http
- **说明：** 涨停风格板块
- **签名：** `pro.limit_up_plates_style(*, limit=None, field=None, **opts)`

**用法**

- 基本调用

```python
pro.limit_up_plates_style(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.limit_up_plates_style(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.limit_up_plates_style(limit=5, as_dataframe=False)
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `id` | `limit_up_count` | `name` | `rise_count` |
| --- | --- | --- | --- | --- | --- | --- |
| 0.006674 | 59 | 1.39272e+09 | 13011026 | 3 | 高价股 | 65 |
| 0.003715 | 46 | -3.22134e+08 | 17864537 | 0 | 次新股 | 44 |
| 0.003152 | 28 | 9.09575e+08 | 54856094 | 0 | 科创50 | 22 |
| 0.002576 | 14 | 4.09725e+08 | 17249694 | 0 | 举牌 | 6 |
| 0.000979 | 138 | 1.01132e+09 | 7198750 | 3 | 回购 | 85 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.006674 |
| `fall_count` | 下跌家数 | 59 |
| `fund_flow` | 资金流向 | 1.39272e+09 |
| `id` | 编号 | 13011026 |
| `limit_up_count` | 涨停家数 | 3 |
| `name` | 名称 | 高价股 |
| `rise_count` | 上涨家数 | 65 |

### `abnormal_events`

- **路径：** `/v1/abnormal-events`
- **类型：** http
- **说明：** 异动事件
- **签名：** `pro.abnormal_events(*, count=None, types=None, kind=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.abnormal_events(count=10)
```

**进阶用法**

- 进阶参数组合

```python
pro.abnormal_events(types='limit_up', kind='stock')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.abnormal_events(count=10, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.abnormal_events(count=10, as_dataframe=False)
```

- 翻页游标（请求参数为秒）

```python
pro.abnormal_events(count=10, timestamp=1700000000)
```

**数据样例**

| `change_percent` | `id` | `kind` | `name` | `occurred_at` | `occurred_time` | `sentiment` | `stocks` | `type` | `type_label` | `minute_change_percent` | `plates` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -0.010074 | 9990847 | plate | 低价股 | 1790146800 | 15:00:00 | 1 | [3 项，见下方展开] | plate_surge | 板块拉升 |  |  |
| -0.005383 | 9990846 | plate | 华为产业链 | 1790146800 | 15:00:00 | 1 | [3 项，见下方展开] | plate_surge | 板块拉升 |  |  |
| -0.09913 | 9990845 | stock | 云煤能源 | 1790146800 | 15:00:00 | 1 |  | limit_down_open | 打开跌停板 | 0 | [2 项，见下方展开] |
| 0.099906 | 9990843 | stock | 江淮汽车 | 1790146610 | 14:56:50 | 1 |  | limit_up_about_open | 即将打开涨停 | 0 | [15 项，见下方展开] |
| 0.200277 | 9990844 | stock | 慧智微 | 1790146608 | 14:56:48 | 1 |  | limit_up_seal | 封涨停板 | 0 | [8 项，见下方展开] |

（共 10 行，表中展示前 5 行、前 12/14 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | -0.010074 |
| `id` | 编号 | 9990847 |
| `kind` | 种类 | plate |
| `name` | 名称 | 低价股 |
| `occurred_at` | 发生时间 | 1790146800 |
| `occurred_time` | 发生时刻 | 15:00:00 |
| `sentiment` | 市场情绪 | 1 |
| `stocks` | 成分股列表 | [3 项，见下方展开] |
| `type` | 类型 | plate_surge |
| `type_label` | 类型说明 | 板块拉升 |
| `minute_change_percent` | 分时涨跌幅 |  |
| `plates` | 板块列表 |  |
| `price` | 最新价 |  |
| `symbol` | 标的代码 |  |

### `abnormal_events_stream`

- **路径：** `/v1/abnormal-events/stream`
- **类型：** sse
- **说明：** 异动推流
- **签名：** `pro.abnormal_events_stream(*, types=None, kind=None, timeout=None)`

**用法**

- one event

```python
next(iter(pro.abnormal_events_stream()))
```

**数据样例**

暂无可用样例：无样例

### `market_flash_stream`

- **路径：** `/v1/market-flash/stream`
- **类型：** sse
- **说明：** 快讯推流
- **签名：** `pro.market_flash_stream(*, actions=None, include_withdrawn=None, timeout=None)`

**用法**

- market_flash_stream

```python
next(iter(pro.market_flash_stream()))
```

**数据样例**

暂无可用样例：无样例

### `lhb_daily`

- **路径：** `/v1/lhb/daily`
- **类型：** http
- **说明：** 龙虎榜日数据
- **签名：** `pro.lhb_daily(*, date=None, tradedate=None, with_details=None, **opts)`

**用法**

- 基本调用

```python
pro.lhb_daily()
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.lhb_daily(tradedate='20250102')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.lhb_daily(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.lhb_daily(as_dataframe=False)
```

- 指定交易日

```python
pro.lhb_daily(date='20250102')
```

- 附带明细

```python
pro.lhb_daily(with_details=True)
```

**数据样例**

| `amount_10k_cny` | `close` | `code` | `metric_pct` | `name` | `reason` | `tradedate` | `type` | `volume_10k_shares` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 166.719 | 0.46 | 000004 | 0 | 国华退 | 退市整理的证券 | 2026-07-10 | 33 | 363.059 |
| 238.252 | 0.21 | 002808 | 0 | 恒久退 | 退市整理的证券 | 2026-07-10 | 33 | 1161.9 |
| 185.299 | 0.35 | 002898 | 0 | 赛隆退 | 退市整理的证券 | 2026-07-10 | 33 | 535.084 |
| 894.8 | 0.56 | 920305 | 0 | 云创退 | 退市整理的证券 | 2026-07-10 | 33 | 1551.8 |
| 44485.1 | 1.89 | 000078 | 16.67 | ST海王 | 振幅值达15%的证券 | 2026-07-10 | 03 | 24702.1 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `amount_10k_cny` | 金额（万元） | 166.719 |
| `close` | 收盘价 / 最新价 | 0.46 |
| `code` | 代码 | 000004 |
| `metric_pct` | 指标百分比 | 0 |
| `name` | 名称 | 国华退 |
| `reason` | 涨停/异动原因 | 退市整理的证券 |
| `tradedate` | 交易日（入参别名） | 2026-07-10 |
| `type` | 类型 | 33 |
| `volume_10k_shares` | 成交量（万股） | 363.059 |

### `lhb_stock`

- **路径：** `/v1/lhb/stock`
- **类型：** http
- **说明：** 龙虎榜个股
- **签名：** `pro.lhb_stock(symbol=None, *, ks_code=None, bdate=None, edate=None, **opts)`

**用法**

- 基本调用

```python
pro.lhb_stock(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.lhb_stock(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.lhb_stock(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.lhb_stock(ks_code='sh600519', bdate='2026-07-01', edate='2026-07-10')
```

**数据样例**

```json
[]
```

### `lhb`

- **路径：** `/v1/lhb`
- **类型：** http
- **说明：** 龙虎榜综合
- **签名：** `pro.lhb(symbol=None, *, ks_code=None, date=None, bdate=None, edate=None, **opts)`

**用法**

- 基本调用

```python
pro.lhb(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.lhb(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.lhb(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.lhb(ks_code='sh600519', bdate='2026-07-01', edate='2026-07-10')
```

- 指定交易日

```python
pro.lhb(symbol='600519.SS', bdate='2026-07-01', edate='2026-07-10', date='20250102')
```

**数据样例**

```json
[]
```

### `lhb_dates`

- **路径：** `/v1/lhb/dates`
- **类型：** http
- **说明：** 龙虎榜日期
- **签名：** `pro.lhb_dates(**opts)`

**用法**

- 基本调用

```python
pro.lhb_dates()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.lhb_dates(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.lhb_dates(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `count` | 1579 |
| `dates` | ["2020-01-02", "2020-01-03", "2020-01-06", "202… |
| `first` | 2020-01-02 |
| `last` | 2026-07-10 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `count` | 条数 | 1579 |
| `dates` | 日期列表 | ["2020-01-02", "2020-01-03", "2020-01-06", "202… |
| `first` | 首项 | 2020-01-02 |
| `last` | 最新价 | 2026-07-10 |

### `lhb_stats`

- **路径：** `/v1/lhb/stats`
- **类型：** http
- **说明：** 龙虎榜统计
- **签名：** `pro.lhb_stats(*, kind=None, lastdays=None, bdate=None, edate=None, page=None, **opts)`

**用法**

- 基本调用

```python
pro.lhb_stats()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.lhb_stats(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.lhb_stats(as_dataframe=False)
```

- 起始日

```python
pro.lhb_stats(bdate='20240101')
```

- 结束日

```python
pro.lhb_stats(edate='20241231')
```

- 页码

```python
pro.lhb_stats(page=1)
```

**数据样例**

| `buy_seats` | `buy_total_10k` | `code` | `list_count` | `name` | `net_10k` | `sell_seats` | `sell_total_10k` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 600288 | 7 | 大恒科技 | 0 | 0 | 0 |
| 0 | 0 | 920193 | 7 | 吉和昌 | 0 | 0 | 0 |
| 0 | 0 | 000566 | 6 | 海南海药 | 0 | 0 | 0 |
| 0 | 0 | 001399 | 6 | 惠科股份 | 0 | 0 | 0 |
| 0 | 0 | 301516 | 6 | 中远通 | 0 | 0 | 0 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `buy_seats` | 买方席位数 | 0 |
| `buy_total_10k` | 买入合计（万元） | 0 |
| `code` | 代码 | 600288 |
| `list_count` | 列表条数 | 7 |
| `name` | 名称 | 大恒科技 |
| `net_10k` | 净流入（万元） | 0 |
| `sell_seats` | 卖方席位数 | 0 |
| `sell_total_10k` | 卖出合计（万元） | 0 |

### `hot_money`

- **路径：** `/v1/hot-money`
- **类型：** http
- **说明：** 游资名录
- **签名：** `pro.hot_money(*, name=None, keyword=None, q=None, **opts)`

**用法**

- 基本调用

```python
pro.hot_money()
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.hot_money(q='章盟主')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hot_money(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hot_money(as_dataframe=False)
```

- 关键词搜索

```python
pro.hot_money(keyword='茅台')
```

**数据样例**

| `desc` | `intro` | `name` | `seats` |
| --- | --- | --- | --- |
| 淘股吧知名选手，理解力惊人，完全理解投机本质，真正为交易而生。低吸、追涨、打板样样精通，是典型… | 江苏籍90后资深短线投资者，擅长多种超短线策略，胜率高。自20年起活跃于网络，凭借情绪理解力，… | 92科比 | ["兴业证券股份有限公司南京天元东路证券营业部"] |
|  | 邱宝裕，别号A神，是新晋游资界备受追捧的标杆人物。他对于超短线交易有着独到的见解，认为成功的关… | Asking | ["兴业证券股份有限公司福州湖东路证券营业部"] |
| 擅长低吸和打板，短线趋势交易 | 在股票论坛中，一位擅长波段交易的知名投资者，被股民尊称为二哥。他擅长长期趋势投资，短线操作，仅… | N周二 | ["中信证券股份有限公司杭州凤起路证券营业部"] |
| 此类席位每天做T，其乐无穷。 | 每天从事此类座位工作，乐趣无穷无尽。 | T王 | ["东方财富证券股份有限公司山南香曲东路证券营业部", "东方财富证券股份有限公司拉萨东城区江… |
| 论坛知名短线选手，小资金做大的典范，曾完成四年一千倍的超级战绩。 | 这位以短线交易著称，其资金规模在四年内增长千倍，被誉为“股坛车神”。其严格的交易纪律和专注度使… | bike770 | ["国泰君安证券股份有限公司南宁民族大道证券营业部", "国泰海通证券股份有限公司南宁民族大道… |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `desc` | 描述 | 淘股吧知名选手，理解力惊人，完全理解投机本质，真正为交易而生。低吸、追涨、打板样样精通，是典型… |
| `intro` | 简介 | 江苏籍90后资深短线投资者，擅长多种超短线策略，胜率高。自20年起活跃于网络，凭借情绪理解力，… |
| `name` | 名称 | 92科比 |
| `seats` | 席位 | ["兴业证券股份有限公司南京天元东路证券营业部"] |

### `hot_money_seat`

- **路径：** `/v1/hot-money/seat`
- **类型：** http
- **说明：** 游资席位
- **签名：** `pro.hot_money_seat(*, broker=None, seat=None, **opts)`

**用法**

- 基本调用

```python
pro.hot_money_seat(
    broker='兴业证券股份有限公司南京天元东路证券营业部',
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hot_money_seat(
    broker='兴业证券股份有限公司南京天元东路证券营业部',, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hot_money_seat(
    broker='兴业证券股份有限公司南京天元东路证券营业部',, as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `broker` | 兴业证券股份有限公司南京天元东路证券营业部 |
| `hot_money` | ["92科比"] |

**`traders` 展开（1 条）**

| `desc` | `intro` | `name` | `seats` |
| --- | --- | --- | --- |
| 淘股吧知名选手，理解力惊人，完全理解投机本质，真正为交易而生。低吸、追涨、打板样样精通，是典型… | 江苏籍90后资深短线投资者，擅长多种超短线策略，胜率高。自20年起活跃于网络，凭借情绪理解力，… | 92科比 | ["兴业证券股份有限公司南京天元东路证券营业部"] |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `broker` | 券商 | 兴业证券股份有限公司南京天元东路证券营业部 |
| `hot_money` | 游资 | ["92科比"] |
| `traders` | 营业部/席位 | [1 项，见下方展开] |
| `traders.desc` | 营业部/席位 → 描述 | 淘股吧知名选手，理解力惊人，完全理解投机本质，真正为交易而生。低吸、追涨、打板样样精通，是典型… |
| `traders.intro` | 营业部/席位 → 简介 | 江苏籍90后资深短线投资者，擅长多种超短线策略，胜率高。自20年起活跃于网络，凭借情绪理解力，… |
| `traders.name` | 营业部/席位 → 名称 | 92科比 |
| `traders.seats` | 营业部/席位 → 席位 | ["兴业证券股份有限公司南京天元东路证券营业部"] |

### `hot_money_detail`

- **路径：** `/v1/hot-money/detail`
- **类型：** http
- **说明：** 游资明细
- **签名：** `pro.hot_money_detail(*, name=None, symbol=None, ks_code=None, **opts)`
- **介绍：** 游资反查 `GET /v1/hot-money/detail`。

**用法**

- 基本调用

```python
pro.hot_money_detail(name='92科比')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hot_money_detail(name='92科比', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hot_money_detail(name='92科比', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.hot_money_detail(name='92科比', ks_code='sh600519')
```

**数据样例**

```json
[]
```

### `hot_money_stats`

- **路径：** `/v1/hot-money/stats`
- **类型：** http
- **说明：** 游资统计
- **签名：** `pro.hot_money_stats(**opts)`
- **介绍：** 游资统计 `GET /v1/hot-money/stats`。

**用法**

- 基本调用

```python
pro.hot_money_stats()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hot_money_stats(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hot_money_stats(as_dataframe=False)
```

**数据样例**

| `buy_seats` | `buy_total_10k` | `list_count` | `name` | `net_10k` | `sell_seats` | `sell_total_10k` | `top_buy_stocks` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 597 | 5.25849e+06 | 1206 | 机构专用 | 899086 | 609 | 4.3594e+06 | 002428(云南锗业),300475(香农芯创),001309(德明利) |
| 519 | 5.3062e+06 | 1049 | 量化基金 | 822975 | 530 | 4.48323e+06 | 603986(兆易创新),600584(长电科技),600176(中国巨石) |
| 154 | 166775 | 311 | T王 | -29216.1 | 157 | 195991 | 600667(太极实业),920725(惠丰钻石),002584(西陇科学) |
| 152 | 4.53576e+06 | 298 | 深股通专用 | 484010 | 146 | 4.05176e+06 | 301396(宏景科技),001309(德明利),002428(云南锗业) |
| 127 | 4.336e+06 | 251 | 沪股通专用 | 791871 | 124 | 3.54413e+06 | 603986(兆易创新),600584(长电科技),600176(中国巨石) |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `buy_seats` | 买方席位数 | 597 |
| `buy_total_10k` | 买入合计（万元） | 5.25849e+06 |
| `list_count` | 列表条数 | 1206 |
| `name` | 名称 | 机构专用 |
| `net_10k` | 净流入（万元） | 899086 |
| `sell_seats` | 卖方席位数 | 609 |
| `sell_total_10k` | 卖出合计（万元） | 4.3594e+06 |
| `top_buy_stocks` | 买入前排股票 | 002428(云南锗业),300475(香农芯创),001309(德明利) |

### `moneyflow_daily_trend`

- **路径：** `/v1/moneyflow/daily-trend`
- **类型：** http
- **说明：** 资金流日趋势
- **签名：** `pro.moneyflow_daily_trend(symbol=None, *, ks_code=None, date=None, bdate=None, edate=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.moneyflow_daily_trend(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_daily_trend(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_daily_trend(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.moneyflow_daily_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.moneyflow_daily_trend(symbol='600519.SS', date='20250102')
```

- 起始日

```python
pro.moneyflow_daily_trend(symbol='600519.SS', bdate='20240101')
```

- 结束日

```python
pro.moneyflow_daily_trend(symbol='600519.SS', edate='20241231')
```

- 返回条数上限

```python
pro.moneyflow_daily_trend(symbol='600519.SS', limit=20)
```

**数据样例**

| `cate_na` | `cate_ra` | `changeratio` | `cnt_r0x_ratio` | `date` | `netamount` | `r0_net` | `r0_ratio` | `r0x_ratio` | `ratioamount` | `trade` | `turnover` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 914051666.22 | 0.0492137 | -0.00204179 | -1 | 2026-09-23 | -31965682.92 | -125448286.1 | -0.03221057 | -93.6271 | -0.00820763 | 1251.24 | 24.7834 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `cate_na` | 分类名称 | 914051666.22 |
| `cate_ra` | 分类比率 | 0.0492137 |
| `changeratio` | 涨跌幅 | -0.00204179 |
| `cnt_r0x_ratio` | 超大单占比计数 | -1 |
| `date` | 交易日 | 2026-09-23 |
| `netamount` | 净流入额 | -31965682.92 |
| `r0_net` | 超大单净流入 | -125448286.1 |
| `r0_ratio` | 超大单净占比 | -0.03221057 |
| `r0x_ratio` | 超大单占比 | -93.6271 |
| `ratioamount` | 净流入占比 | -0.00820763 |
| `trade` | 是否交易日 | 1251.24 |
| `turnover` | 换手相关 | 24.7834 |

### `moneyflow_stage`

- **路径：** `/v1/moneyflow/stage`
- **类型：** http
- **说明：** 资金流阶段
- **签名：** `pro.moneyflow_stage(symbol=None, *, ks_code=None, date=None, bdate=None, edate=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.moneyflow_stage(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_stage(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_stage(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.moneyflow_stage(ks_code='sh600519')
```

- 指定交易日

```python
pro.moneyflow_stage(symbol='600519.SS', date='20250102')
```

- 起始日

```python
pro.moneyflow_stage(symbol='600519.SS', bdate='20240101')
```

- 结束日

```python
pro.moneyflow_stage(symbol='600519.SS', edate='20241231')
```

- 返回条数上限

```python
pro.moneyflow_stage(symbol='600519.SS', limit=20)
```

**数据样例**

| `date` | `r0_net_10` | `r0_net_3` | `r0_net_5` | `r0_ratio_10` | `r0_ratio_3` | `r0_ratio_5` | `r0x_ratio_10` | `r0x_ratio_3` | `r0x_ratio_5` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-23 | -1556313967.33 | -264471314.62 | -244658823.35 | -0.05372678 | -0.02613594 | -0.01610411 | -119.75 | -100.146 | -108.453 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `date` | 交易日 | 2026-09-23 |
| `r0_net_10` | 近10日超大单净流入 | -1556313967.33 |
| `r0_net_3` | 近3日超大单净流入 | -264471314.62 |
| `r0_net_5` | 近5日超大单净流入 | -244658823.35 |
| `r0_ratio_10` | 近10日超大单净占比 | -0.05372678 |
| `r0_ratio_3` | 近3日超大单净占比 | -0.02613594 |
| `r0_ratio_5` | 近5日超大单净占比 | -0.01610411 |
| `r0x_ratio_10` | 近10日超大单占比 | -119.75 |
| `r0x_ratio_3` | 近3日超大单占比 | -100.146 |
| `r0x_ratio_5` | 近5日超大单占比 | -108.453 |

### `moneyflow_distribution`

- **路径：** `/v1/moneyflow/distribution`
- **类型：** http
- **说明：** 资金流分布
- **签名：** `pro.moneyflow_distribution(symbol=None, *, ks_code=None, date=None, bdate=None, edate=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.moneyflow_distribution(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_distribution(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_distribution(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.moneyflow_distribution(ks_code='sh600519')
```

- 指定交易日

```python
pro.moneyflow_distribution(symbol='600519.SS', date='20250102')
```

- 起始日

```python
pro.moneyflow_distribution(symbol='600519.SS', bdate='20240101')
```

- 结束日

```python
pro.moneyflow_distribution(symbol='600519.SS', edate='20241231')
```

- 返回条数上限

```python
pro.moneyflow_distribution(symbol='600519.SS', limit=20)
```

**数据样例**

| `changeratio` | `date` | `netamount` | `r0` | `r0_net` | `r1` | `r1_net` | `r2` | `r2_net` | `r3` | `r3_net` | `ratioamount` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -0.00204179 | 2026-09-23 | -31965682.92 | 2653165980.64 | -125448286.1 | 1213412733.1 | 70736943.4 | 80722005.42 | 22783192.18 | 37532.4 | -37532.4 | -0.00820763 |

（共 1 行、前 12/14 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `changeratio` | 涨跌幅 | -0.00204179 |
| `date` | 交易日 | 2026-09-23 |
| `netamount` | 净流入额 | -31965682.92 |
| `r0` | 超大单 | 2653165980.64 |
| `r0_net` | 超大单净流入 | -125448286.1 |
| `r1` | 大单 | 1213412733.1 |
| `r1_net` | 大单净流入 | 70736943.4 |
| `r2` | 中单 | 80722005.42 |
| `r2_net` | 中单净流入 | 22783192.18 |
| `r3` | 小单 | 37532.4 |
| `r3_net` | 小单净流入 | -37532.4 |
| `ratioamount` | 净流入占比 | -0.00820763 |
| `trade` | 是否交易日 | 1251.24 |
| `turnover` | 换手相关 | 24.7834 |

### `moneyflow_ranking_boards`

- **路径：** `/v1/moneyflow/ranking/boards`
- **类型：** http
- **说明：** 板块资金榜
- **签名：** `pro.moneyflow_ranking_boards(*, category=None, **opts)`

**用法**

- 基本调用

```python
pro.moneyflow_ranking_boards(category='industry')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_boards(category='industry', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_boards(category='industry', as_dataframe=False)
```

**数据样例**

| `avg_changeratio` | `avg_price` | `captured_at` | `cate_type` | `category` | `inamount` | `name` | `netamount` | `outamount` | `ratioamount` | `trade_date` | `ts_changeratio` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -0.000247292 | 20.6646 | 2026-09-23 15:06:02 | 0 | new_dzqj | 7.13001e+10 | 电子器件 | 6.01588e+09 | 6.52842e+10 | 0.0420339 | 2026-09-23 | 0.117257 |
| -0.000747219 | 4.1114 | 2026-09-23 15:06:02 | 0 | new_fdc | 2.14961e+10 | 房地产 | 4.23867e+09 | 1.72574e+10 | 0.107106 | 2026-09-23 | 0.101562 |
| -0.00108395 | 79.9351 | 2026-09-23 15:06:02 | 0 | new_ljhy | 7.5582e+09 | 酿酒行业 | 9.44761e+08 | 6.61344e+09 | 0.0626247 | 2026-09-23 | 0.0500463 |
| -0.0088044 | 14.5843 | 2026-09-23 15:06:02 | 0 | new_qczz | 1.48669e+10 | 汽车制造 | 7.71701e+08 | 1.40952e+10 | 0.0257739 | 2026-09-23 | 0.1 |
| 0.00247376 | 17.7661 | 2026-09-23 15:06:02 | 0 | new_blhy | 7.15246e+09 | 玻璃行业 | 7.23557e+08 | 6.4289e+09 | 0.0512401 | 2026-09-23 | 0.10119 |

（共 20 行，表中展示前 5 行、前 12/17 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `avg_changeratio` | 平均涨跌幅 | -0.000247292 |
| `avg_price` | 均价 | 20.6646 |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `cate_type` | 分类类型 | 0 |
| `category` | 分类 | new_dzqj |
| `inamount` | 流入额 | 7.13001e+10 |
| `name` | 名称 | 电子器件 |
| `netamount` | 净流入额 | 6.01588e+09 |
| `outamount` | 流出额 | 6.52842e+10 |
| `ratioamount` | 净流入占比 | 0.0420339 |
| `trade_date` | 交易日 | 2026-09-23 |
| `ts_changeratio` | 分时涨跌幅 | 0.117257 |
| `ts_name` | 分时名称 | 安居宝 |
| `ts_ratioamount` | 分时净流入占比 | 0.448594 |
| `ts_symbol` | 分时标的 | 300155.SZ |
| `ts_trade` | 分时成交 | 5.05 |
| `turnover` | 换手相关 | 296.451 |

### `moneyflow_ranking_stocks`

- **路径：** `/v1/moneyflow/ranking/stocks`
- **类型：** http
- **说明：** 个股资金榜
- **签名：** `pro.moneyflow_ranking_stocks(*, sort=None, **opts)`
- **介绍：** 兼容入口；精确榜单请用 `moneyflow_ranking_stocks_net|main|retail`。

**用法**

- 基本调用

```python
pro.moneyflow_ranking_stocks()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_stocks(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_stocks(as_dataframe=False)
```

- 排序维度

```python
pro.moneyflow_ranking_stocks(sort='net')
```

**数据样例**

| `amount` | `captured_at` | `changeratio` | `inamount` | `name` | `netamount` | `outamount` | `r0_in` | `r0_net` | `r0_out` | `r0_ratio` | `r0x_ratio` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4.9929e+09 | 2026-09-23 15:06:02 | 0.100021 | 3.63016e+09 | 沃格光电 | 2.5559e+09 | 1.07426e+09 | 3.22005e+09 | 2.26874e+09 | 9.51311e+08 | 0.454394 | 77.586 |
| 7.95583e+09 | 2026-09-23 15:06:02 | 0.0928212 | 4.48462e+09 | 先导基电 | 1.47794e+09 | 3.00667e+09 | 3.92885e+09 | 1.51595e+09 | 2.41291e+09 | 0.190545 | 64.0277 |
| 4.93545e+09 | 2026-09-23 15:06:02 | 0.0999062 | 2.94492e+09 | 江淮汽车 | 1.19129e+09 | 1.75363e+09 | 2.36213e+09 | 1.07152e+09 | 1.29061e+09 | 0.217107 | 65.2895 |
| 4.2921e+09 | 2026-09-23 15:06:02 | 0.0288714 | 2.69069e+09 | 万 科Ａ | 1.13275e+09 | 1.55793e+09 | 2.11626e+09 | 8.93755e+08 | 1.22251e+09 | 0.208233 | 82.1063 |
| 5.85308e+09 | 2026-09-23 15:06:02 | 0.0785091 | 3.2995e+09 | 超声电子 | 1.04639e+09 | 2.2531e+09 | 2.65051e+09 | 1.01824e+09 | 1.63228e+09 | 0.173966 | 65.7108 |

（共 20 行，表中展示前 5 行、前 12/21 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `amount` | 成交额 | 4.9929e+09 |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `changeratio` | 涨跌幅 | 0.100021 |
| `inamount` | 流入额 | 3.63016e+09 |
| `name` | 名称 | 沃格光电 |
| `netamount` | 净流入额 | 2.5559e+09 |
| `outamount` | 流出额 | 1.07426e+09 |
| `r0_in` | 超大单流入 | 3.22005e+09 |
| `r0_net` | 超大单净流入 | 2.26874e+09 |
| `r0_out` | 超大单流出 | 9.51311e+08 |
| `r0_ratio` | 超大单净占比 | 0.454394 |
| `r0x_ratio` | 超大单占比 | 77.586 |
| `r3_in` | 小单流入 | 2.12761e+07 |
| `r3_net` | 小单净流入 | 2.05597e+07 |
| `r3_out` | 小单流出 | 716308 |
| `r3_ratio` | 小单净占比 | 0.0041178 |
| `ratioamount` | 净流入占比 | 0.511906 |
| `symbol` | 标的代码 | 603773.SS |
| `trade` | 是否交易日 | 102.5 |
| `trade_date` | 交易日 | 2026-09-23 |
| `turnover` | 换手相关 | 2194.32 |

### `moneyflow_ranking_stocks_sort`

- **路径：** `/v1/moneyflow/ranking/stocks/net`
- **类型：** http
- **说明：** 个股资金榜（按排序映射路径）

**进阶用法**

- sort=net path suffix

```python
pro.moneyflow_ranking_stocks(sort='net')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_stocks(sort='net', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_stocks(sort='net', as_dataframe=False)
```

**数据样例**

| `amount` | `captured_at` | `changeratio` | `inamount` | `name` | `netamount` | `outamount` | `r0x_ratio` | `ratioamount` | `symbol` | `trade` | `trade_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4.9929e+09 | 2026-09-23 15:06:02 | 0.100021 | 3.63016e+09 | 沃格光电 | 2.5559e+09 | 1.07426e+09 | 77.586 | 0.511906 | 603773.SS | 102.5 | 2026-09-23 |
| 7.95583e+09 | 2026-09-23 15:06:02 | 0.0928212 | 4.48462e+09 | 先导基电 | 1.47794e+09 | 3.00667e+09 | 64.0277 | 0.185769 | 600641.SS | 47.8 | 2026-09-23 |
| 4.93545e+09 | 2026-09-23 15:06:02 | 0.0999062 | 2.94492e+09 | 江淮汽车 | 1.19129e+09 | 1.75363e+09 | 65.2895 | 0.241373 | 600418.SS | 23.45 | 2026-09-23 |
| 4.2921e+09 | 2026-09-23 15:06:02 | 0.0288714 | 2.69069e+09 | 万 科Ａ | 1.13275e+09 | 1.55793e+09 | 82.1063 | 0.263916 | 000002.SZ | 3.92 | 2026-09-23 |
| 5.85308e+09 | 2026-09-23 15:06:02 | 0.0785091 | 3.2995e+09 | 超声电子 | 1.04639e+09 | 2.2531e+09 | 65.7108 | 0.178777 | 000823.SZ | 27.2 | 2026-09-23 |

（共 20 行，表中展示前 5 行、前 12/13 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `amount` | 成交额 | 4.9929e+09 |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `changeratio` | 涨跌幅 | 0.100021 |
| `inamount` | 流入额 | 3.63016e+09 |
| `name` | 名称 | 沃格光电 |
| `netamount` | 净流入额 | 2.5559e+09 |
| `outamount` | 流出额 | 1.07426e+09 |
| `r0x_ratio` | 超大单占比 | 77.586 |
| `ratioamount` | 净流入占比 | 0.511906 |
| `symbol` | 标的代码 | 603773.SS |
| `trade` | 是否交易日 | 102.5 |
| `trade_date` | 交易日 | 2026-09-23 |
| `turnover` | 换手相关 | 2194.32 |

### `moneyflow_ranking_stocks_net`

- **路径：** `/v1/moneyflow/ranking/stocks/net`
- **类型：** http
- **说明：** 个股净流入榜
- **签名：** `pro.moneyflow_ranking_stocks_net(**opts)`

**用法**

- 基本调用

```python
pro.moneyflow_ranking_stocks_net()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_stocks_net(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_stocks_net(as_dataframe=False)
```

**数据样例**

| `amount` | `captured_at` | `changeratio` | `inamount` | `name` | `netamount` | `outamount` | `r0x_ratio` | `ratioamount` | `symbol` | `trade` | `trade_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4.9929e+09 | 2026-09-23 15:06:02 | 0.100021 | 3.63016e+09 | 沃格光电 | 2.5559e+09 | 1.07426e+09 | 77.586 | 0.511906 | 603773.SS | 102.5 | 2026-09-23 |
| 7.95583e+09 | 2026-09-23 15:06:02 | 0.0928212 | 4.48462e+09 | 先导基电 | 1.47794e+09 | 3.00667e+09 | 64.0277 | 0.185769 | 600641.SS | 47.8 | 2026-09-23 |
| 4.93545e+09 | 2026-09-23 15:06:02 | 0.0999062 | 2.94492e+09 | 江淮汽车 | 1.19129e+09 | 1.75363e+09 | 65.2895 | 0.241373 | 600418.SS | 23.45 | 2026-09-23 |
| 4.2921e+09 | 2026-09-23 15:06:02 | 0.0288714 | 2.69069e+09 | 万 科Ａ | 1.13275e+09 | 1.55793e+09 | 82.1063 | 0.263916 | 000002.SZ | 3.92 | 2026-09-23 |
| 5.85308e+09 | 2026-09-23 15:06:02 | 0.0785091 | 3.2995e+09 | 超声电子 | 1.04639e+09 | 2.2531e+09 | 65.7108 | 0.178777 | 000823.SZ | 27.2 | 2026-09-23 |

（共 20 行，表中展示前 5 行、前 12/13 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `amount` | 成交额 | 4.9929e+09 |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `changeratio` | 涨跌幅 | 0.100021 |
| `inamount` | 流入额 | 3.63016e+09 |
| `name` | 名称 | 沃格光电 |
| `netamount` | 净流入额 | 2.5559e+09 |
| `outamount` | 流出额 | 1.07426e+09 |
| `r0x_ratio` | 超大单占比 | 77.586 |
| `ratioamount` | 净流入占比 | 0.511906 |
| `symbol` | 标的代码 | 603773.SS |
| `trade` | 是否交易日 | 102.5 |
| `trade_date` | 交易日 | 2026-09-23 |
| `turnover` | 换手相关 | 2194.32 |

### `moneyflow_ranking_stocks_main`

- **路径：** `/v1/moneyflow/ranking/stocks/main`
- **类型：** http
- **说明：** 主力榜
- **签名：** `pro.moneyflow_ranking_stocks_main(**opts)`

**用法**

- 基本调用

```python
pro.moneyflow_ranking_stocks_main()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_stocks_main(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_stocks_main(as_dataframe=False)
```

**数据样例**

| `amount` | `captured_at` | `changeratio` | `name` | `r0_in` | `r0_net` | `r0_out` | `r0_ratio` | `r0x_ratio` | `symbol` | `trade` | `trade_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4.9929e+09 | 2026-09-23 15:06:02 | 0.100021 | 沃格光电 | 3.22005e+09 | 2.26874e+09 | 9.51311e+08 | 0.454394 | 77.586 | 603773.SS | 102.5 | 2026-09-23 |
| 7.95583e+09 | 2026-09-23 15:06:02 | 0.0928212 | 先导基电 | 3.92885e+09 | 1.51595e+09 | 2.41291e+09 | 0.190545 | 64.0277 | 600641.SS | 47.8 | 2026-09-23 |
| 4.93545e+09 | 2026-09-23 15:06:02 | 0.0999062 | 江淮汽车 | 2.36213e+09 | 1.07152e+09 | 1.29061e+09 | 0.217107 | 65.2895 | 600418.SS | 23.45 | 2026-09-23 |
| 5.85308e+09 | 2026-09-23 15:06:02 | 0.0785091 | 超声电子 | 2.65051e+09 | 1.01824e+09 | 1.63228e+09 | 0.173966 | 65.7108 | 000823.SZ | 27.2 | 2026-09-23 |
| 7.07208e+09 | 2026-09-23 15:06:02 | 0.0377572 | 兴森科技 | 3.1703e+09 | 9.58359e+08 | 2.21194e+09 | 0.135513 | 74.4309 | 002436.SZ | 45.9 | 2026-09-23 |

（共 20 行，表中展示前 5 行、前 12/13 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `amount` | 成交额 | 4.9929e+09 |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `changeratio` | 涨跌幅 | 0.100021 |
| `name` | 名称 | 沃格光电 |
| `r0_in` | 超大单流入 | 3.22005e+09 |
| `r0_net` | 超大单净流入 | 2.26874e+09 |
| `r0_out` | 超大单流出 | 9.51311e+08 |
| `r0_ratio` | 超大单净占比 | 0.454394 |
| `r0x_ratio` | 超大单占比 | 77.586 |
| `symbol` | 标的代码 | 603773.SS |
| `trade` | 是否交易日 | 102.5 |
| `trade_date` | 交易日 | 2026-09-23 |
| `turnover` | 换手相关 | 2194.32 |

### `moneyflow_ranking_stocks_retail`

- **路径：** `/v1/moneyflow/ranking/stocks/retail`
- **类型：** http
- **说明：** 散户榜
- **签名：** `pro.moneyflow_ranking_stocks_retail(**opts)`

**用法**

- 基本调用

```python
pro.moneyflow_ranking_stocks_retail()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_stocks_retail(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_stocks_retail(as_dataframe=False)
```

**数据样例**

| `amount` | `captured_at` | `changeratio` | `name` | `r0x_ratio` | `r3_in` | `r3_net` | `r3_out` | `r3_ratio` | `symbol` | `trade` | `trade_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.21034e+09 | 2026-09-23 15:06:02 | 0.0997151 | 我爱我家 | 78.7431 | 3.4357e+07 | 3.4357e+07 | 0 | 0.0283862 | 000560.SZ | 3.86 | 2026-09-23 |
| 6.87815e+08 | 2026-09-23 15:06:02 | 0.100372 | 胜利精密 | 76.8692 | 3.29963e+07 | 3.29963e+07 | 0 | 0.0479726 | 002426.SZ | 2.96 | 2026-09-23 |
| 1.93089e+08 | 2026-09-23 15:06:02 | 0.099711 | 上工申贝 | 70.6771 | 2.56039e+07 | 2.56039e+07 | 0 | 0.132602 | 600843.SS | 7.61 | 2026-09-23 |
| 1.47891e+09 | 2026-09-23 15:06:02 | 0.100123 | 康强电子 | 73.7475 | 3.09983e+07 | 2.55657e+07 | 5.43256e+06 | 0.0172869 | 002119.SZ | 26.92 | 2026-09-23 |
| 9.71213e+08 | 2026-09-23 15:06:02 | 0.0998553 | 依顿电子 | 71.803 | 2.37999e+07 | 2.33371e+07 | 462840 | 0.0240288 | 603328.SS | 15.2 | 2026-09-23 |

（共 20 行，表中展示前 5 行、前 12/13 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `amount` | 成交额 | 1.21034e+09 |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `changeratio` | 涨跌幅 | 0.0997151 |
| `name` | 名称 | 我爱我家 |
| `r0x_ratio` | 超大单占比 | 78.7431 |
| `r3_in` | 小单流入 | 3.4357e+07 |
| `r3_net` | 小单净流入 | 3.4357e+07 |
| `r3_out` | 小单流出 | 0 |
| `r3_ratio` | 小单净占比 | 0.0283862 |
| `symbol` | 标的代码 | 000560.SZ |
| `trade` | 是否交易日 | 3.86 |
| `trade_date` | 交易日 | 2026-09-23 |
| `turnover` | 换手相关 | 1345.32 |

### `moneyflow_ranking_snapshot`

- **路径：** `/v1/moneyflow/ranking/snapshot`
- **类型：** http
- **说明：** 资金流快照
- **签名：** `pro.moneyflow_ranking_snapshot(**opts)`

**用法**

- 基本调用

```python
pro.moneyflow_ranking_snapshot()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_snapshot(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_snapshot(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `board_rows` | 383 |
| `captured_at` | 2026-09-23 15:06:02 |
| `source` | sina |
| `source_label` | 新浪 |
| `stock_rows` | 6437 |
| `trade_date` | 2026-09-23 |

**`boards` 展开**

| 字段 | 值 |
|------|-----|
| `concept` | 181 |
| `csrc_industry` | 154 |
| `industry` | 48 |

**`stocks` 展开**

| 字段 | 值 |
|------|-----|
| `snapshot` | 6437 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `board_rows` | 板块行 | 383 |
| `boards` | 板块列表 | {3 字段，见下方展开} |
| `captured_at` | 采集时间 | 2026-09-23 15:06:02 |
| `source` | 数据来源 | sina |
| `source_label` | 来源说明 | 新浪 |
| `stock_rows` | 股票行 | 6437 |
| `stocks` | 成分股列表 | {1 字段，见下方展开} |
| `trade_date` | 交易日 | 2026-09-23 |
| `boards.concept` | 板块列表 → 概念 | 181 |
| `boards.csrc_industry` | 板块列表 → 证监会行业 | 154 |
| `boards.industry` | 板块列表 → 行业 | 48 |
| `stocks.snapshot` | 成分股列表 → 快照 | 6437 |

### `moneyflow_ranking_live_stocks`

- **路径：** `/v1/moneyflow/ranking/live/stocks`
- **类型：** http
- **说明：** 实时个股资金流排名（分页）
- **签名：** `pro.moneyflow_ranking_live_stocks(*, offset=None, limit=None, sort=None, order=None, **opts)`
- **介绍：** 实时个股资金流排名（分页）`GET /v1/moneyflow/ranking/live/stocks`。

**用法**

- 基本调用

```python
pro.moneyflow_ranking_live_stocks(offset=0, limit=50, sort='net')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_ranking_live_stocks(offset=0, limit=50, sort='net', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_ranking_live_stocks(offset=0, limit=50, sort='net', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `moneyflow_live`

- **路径：** `/v1/moneyflow/live`
- **类型：** http
- **说明：** 实时个股资金流向（按码 / 批量 / 全市场）
- **签名：** `pro.moneyflow_live(symbol=None, *, ks_code=None, all=None, **opts)`
- **介绍：** 实时个股资金流向 `GET /v1/moneyflow/live`。

**用法**

- 单码

```python
pro.moneyflow_live(symbol='600519.SS')
```

**进阶用法**

- 全市场（推荐）

```python
pro.moneyflow_live(all=True)
```

- 批量

```python
pro.moneyflow_live(symbol=['600519.SS', '000001.SZ'])
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.moneyflow_live(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.moneyflow_live(symbol='600519.SS', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `suspend`

- **路径：** `/v1/suspend`
- **类型：** http
- **说明：** 停复牌
- **签名：** `pro.suspend(**opts)`

**用法**

- 基本调用

```python
pro.suspend()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.suspend(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.suspend(as_dataframe=False)
```

**数据样例**

| `code` | `end` | `exchange` | `market_value` | `name` | `predict_resume` | `reason` | `start` | `suspend_end` | `suspend_expire` | `symbol` | `trade_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 200706 |  | SZ |  | 瓦轴B |  | 刊登重要公告 | 2026-03-02 |  | 连续停牌 | 200706.SZ | 2026-03-02 |
| 300333 |  | SZ | 2.98032e+09 | 兆日科技 |  | 重大事项 | 2026-07-30 |  | 连续停牌 | 300333.SZ | 2026-07-30 |
| 600984 |  | SH | 5.64413e+09 | 建设机械 |  | 刊登重要公告 | 2026-08-11 |  | 连续停牌 | 600984.SS | 2026-08-11 |
| 603221 |  | SH | 6.61397e+09 | 爱丽家居 |  | 重要公告 | 2026-08-11 |  | 连续停牌 | 603221.SS | 2026-08-11 |

（共 4 行、前 12/13 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 200706 |
| `end` | 结束 |  |
| `exchange` | 交易所 | SZ |
| `market_value` | 市值 |  |
| `name` | 名称 | 瓦轴B |
| `predict_resume` | 预计复牌 |  |
| `reason` | 涨停/异动原因 | 刊登重要公告 |
| `start` | 开始 | 2026-03-02 |
| `suspend_end` | 停牌结束 |  |
| `suspend_expire` | 停牌到期 | 连续停牌 |
| `symbol` | 标的代码 | 200706.SZ |
| `trade_date` | 交易日 | 2026-03-02 |
| `trade_market` | 交易市场 | 深交所主板 |

### `suspend_daily`

- **路径：** `/v1/suspend/daily`
- **类型：** http
- **说明：** 停复牌日
- **签名：** `pro.suspend_daily(*, date=None, **opts)`

**用法**

- 基本调用

```python
pro.suspend_daily()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.suspend_daily(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.suspend_daily(as_dataframe=False)
```

- 指定交易日

```python
pro.suspend_daily(date='20250102')
```

**数据样例**

```json
[]
```

### `suspend_dates`

- **路径：** `/v1/suspend/dates`
- **类型：** http
- **说明：** 停复牌日期
- **签名：** `pro.suspend_dates(**opts)`

**用法**

- 基本调用

```python
pro.suspend_dates()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.suspend_dates(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.suspend_dates(as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `count` | 2019 |
| `dates` | ["2012-02-22", "2012-03-20", "2012-03-23", "201… |
| `first` | 2012-02-22 |
| `last` | 2026-08-13 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `count` | 条数 | 2019 |
| `dates` | 日期列表 | ["2012-02-22", "2012-03-20", "2012-03-23", "201… |
| `first` | 首项 | 2012-02-22 |
| `last` | 最新价 | 2026-08-13 |

### `suspend_stock`

- **路径：** `/v1/suspend/stock`
- **类型：** http
- **说明：** 个股停复牌
- **签名：** `pro.suspend_stock(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.suspend_stock(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.suspend_stock(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.suspend_stock(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.suspend_stock(ks_code='sh600519')
```

**数据样例**

```json
[]
```

### `zfpg`

- **路径：** `/v1/zfpg`
- **类型：** http
- **说明：** 增发配股
- **签名：** `pro.zfpg(**opts)`

**用法**

- 基本调用

```python
pro.zfpg()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.zfpg(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.zfpg(as_dataframe=False)
```

**数据样例**

| `code` | `event_type` | `name` | `symbol` | `tab` | `update_date` |
| --- | --- | --- | --- | --- | --- |
| 688628 | 其他发行 | 优利德 | 688628.SS | all | 2026-09-15 |
| 301577 | 其他发行 | 美信科技 | 301577.SZ | all | 2026-09-14 |
| 688312 | 其他发行 | 燕麦科技 | 688312.SS | all | 2026-09-14 |
| 301125 | 其他发行 | 腾亚精工 | 301125.SZ | all | 2026-09-14 |
| 920025 | 公开增发 | 凯达重工 | 920025.BJ | all | 2026-09-14 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 688628 |
| `event_type` | 事件类型 | 其他发行 |
| `name` | 名称 | 优利德 |
| `symbol` | 标的代码 | 688628.SS |
| `tab` | 页签/分类 | all |
| `update_date` | 更新日期 | 2026-09-15 |

### `zfpg_daily`

- **路径：** `/v1/zfpg/daily`
- **类型：** http
- **说明：** 增发配股日
- **签名：** `pro.zfpg_daily(*, date=None, **opts)`

**用法**

- 基本调用

```python
pro.zfpg_daily(date='2026-09-15')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.zfpg_daily(date='2026-09-15', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.zfpg_daily(date='2026-09-15', as_dataframe=False)
```

**数据样例**

| `code` | `event_type` | `name` | `symbol` | `tab` | `update_date` |
| --- | --- | --- | --- | --- | --- |
| 688628 | 其他发行 | 优利德 | 688628.SS | all | 2026-09-15 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 688628 |
| `event_type` | 事件类型 | 其他发行 |
| `name` | 名称 | 优利德 |
| `symbol` | 标的代码 | 688628.SS |
| `tab` | 页签/分类 | all |
| `update_date` | 更新日期 | 2026-09-15 |

### `zfpg_stock`

- **路径：** `/v1/zfpg/stock`
- **类型：** http
- **说明：** 个股增发配股
- **签名：** `pro.zfpg_stock(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.zfpg_stock(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.zfpg_stock(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.zfpg_stock(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.zfpg_stock(ks_code='sh600519')
```

**数据样例**

```json
[]
```

### `zfpg_tabs`

- **路径：** `/v1/zfpg/tabs`
- **类型：** http
- **说明：** 增发配股分类页签
- **签名：** `pro.zfpg_tabs(**opts)`

**用法**

- 基本调用

```python
pro.zfpg_tabs()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.zfpg_tabs(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.zfpg_tabs(as_dataframe=False)
```

**数据样例**

| `available` | `date_field` | `label` | `type` |
| --- | --- | --- | --- |
| True | update_date | 全部 | all |
| True | update_date | 定向增发 | directional |
| True | update_date | 公开增发 | public |
| True | update_date | 其他发行 | other |
| True | update_date | 增发预案 | plan |

（共 7 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `available` | 是否可用 | True |
| `date_field` | 日期字段名 | update_date |
| `label` | 标签 | 全部 |
| `type` | 类型 | all |

### `yjfp`

- **路径：** `/v1/yjfp`
- **类型：** http
- **说明：** 业绩分配
- **签名：** `pro.yjfp(**opts)`

**用法**

- 基本调用

```python
pro.yjfp()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.yjfp(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.yjfp(as_dataframe=False)
```

**数据样例**

| `assign_progress` | `basic_eps` | `bd10_close_adjchrate` | `bonus_it_ratio` | `bonus_ratio` | `bvps` | `code` | `d10_close_adjchrate` | `d30_close_adjchrate` | `dividend_ratio` | `equity_record_date` | `ex_dividend_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 董事会决议通过 | 0.58 |  |  |  | 18.1553 | 600482 |  |  | 0.00332347 |  |  |
| 董事会决议通过 | 0.19 |  |  |  | 4.68426 | 688548 |  |  | 0.00272727 |  |  |
| 董事会决议通过 | 0.5 |  |  |  | 5.00652 | 605016 |  |  | 0.00347383 |  |  |
| 实施分配 | 0.66 | 1.64403 |  |  | 6.89226 | 601058 |  |  | 0.0105485 | 2026-09-10 | 2026-09-11 |
| 董事会决议通过 | 0.23 |  |  |  | 5.14101 | 603949 |  |  | 0.014245 |  |  |

（共 20 行，表中展示前 5 行、前 12/30 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `assign_progress` | 分红进度 | 董事会决议通过 |
| `basic_eps` | 基本每股收益 | 0.58 |
| `bd10_close_adjchrate` | 除权前10日复权涨跌幅 |  |
| `bonus_it_ratio` | 送转所得税比例 |  |
| `bonus_ratio` | 送转比例 |  |
| `bvps` | 每股净资产 | 18.1553 |
| `code` | 代码 | 600482 |
| `d10_close_adjchrate` | 近10日复权涨跌幅 |  |
| `d30_close_adjchrate` | 近30日复权涨跌幅 |  |
| `dividend_ratio` | 股息率 | 0.00332347 |
| `equity_record_date` | 股权登记日 |  |
| `ex_dividend_date` | 除权除息日 |  |
| `ex_dividend_days` | 除权天数 | -2.91219e+06 |
| `impl_plan_profile` | 实施方案概况 | 10派1.1569元(含税) |
| `is_kcb` | 是否科创板 |  |
| `it_ratio` | 所得税比例 |  |
| `market_type` | 市场类型 | 069001001001 |
| `name` | 名称 | 中国动力 |
| `notice_date` | 公告日 | 2026-08-31 |
| `per_capital_reserve` | 每股资本公积 | 12.2552 |
| `per_unassign_profit` | 每股未分配利润 | 4.37547 |
| `plan_notice_date` | 预案公告日 | 2026-08-31 |
| `pnp_yoy_ratio` | 归母净利润同比 | 42.7393 |
| `pretax_bonus_rmb` | 税前红利（元） | 1.1569 |
| `publish_date` | 公告日 | 2026-08-31 |
| `report_date` | 报告期 | 2026-06-30 |
| `status` | 状态 | plan |
| `symbol` | 标的代码 | 600482.SS |
| `tab` | 页签/分类 | detail |
| `total_shares` | 总股本 | 2.26825e+09 |

### `yjfp_daily`

- **路径：** `/v1/yjfp/daily`
- **类型：** http
- **说明：** 业绩分配日
- **签名：** `pro.yjfp_daily(*, date=None, **opts)`

**用法**

- 基本调用

```python
pro.yjfp_daily(date='2026-08-31')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.yjfp_daily(date='2026-08-31', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.yjfp_daily(date='2026-08-31', as_dataframe=False)
```

**数据样例**

| `assign_progress` | `basic_eps` | `bd10_close_adjchrate` | `bonus_it_ratio` | `bonus_ratio` | `bvps` | `code` | `d10_close_adjchrate` | `d30_close_adjchrate` | `dividend_ratio` | `equity_record_date` | `ex_dividend_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 董事会决议通过 | 0.58 |  |  |  | 18.1553 | 600482 |  |  | 0.00332347 |  |  |
| 董事会决议通过 | 0.19 |  |  |  | 4.68426 | 688548 |  |  | 0.00272727 |  |  |
| 董事会决议通过 | 0.5 |  |  |  | 5.00652 | 605016 |  |  | 0.00347383 |  |  |
| 实施分配 | 0.66 | 1.64403 |  |  | 6.89226 | 601058 |  |  | 0.0105485 | 2026-09-10 | 2026-09-11 |
| 董事会决议通过 | 0.23 |  |  |  | 5.14101 | 603949 |  |  | 0.014245 |  |  |

（共 16 行，表中展示前 5 行、前 12/30 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `assign_progress` | 分红进度 | 董事会决议通过 |
| `basic_eps` | 基本每股收益 | 0.58 |
| `bd10_close_adjchrate` | 除权前10日复权涨跌幅 |  |
| `bonus_it_ratio` | 送转所得税比例 |  |
| `bonus_ratio` | 送转比例 |  |
| `bvps` | 每股净资产 | 18.1553 |
| `code` | 代码 | 600482 |
| `d10_close_adjchrate` | 近10日复权涨跌幅 |  |
| `d30_close_adjchrate` | 近30日复权涨跌幅 |  |
| `dividend_ratio` | 股息率 | 0.00332347 |
| `equity_record_date` | 股权登记日 |  |
| `ex_dividend_date` | 除权除息日 |  |
| `ex_dividend_days` | 除权天数 | -2.91219e+06 |
| `impl_plan_profile` | 实施方案概况 | 10派1.1569元(含税) |
| `is_kcb` | 是否科创板 |  |
| `it_ratio` | 所得税比例 |  |
| `market_type` | 市场类型 | 069001001001 |
| `name` | 名称 | 中国动力 |
| `notice_date` | 公告日 | 2026-08-31 |
| `per_capital_reserve` | 每股资本公积 | 12.2552 |
| `per_unassign_profit` | 每股未分配利润 | 4.37547 |
| `plan_notice_date` | 预案公告日 | 2026-08-31 |
| `pnp_yoy_ratio` | 归母净利润同比 | 42.7393 |
| `pretax_bonus_rmb` | 税前红利（元） | 1.1569 |
| `publish_date` | 公告日 | 2026-08-31 |
| `report_date` | 报告期 | 2026-06-30 |
| `status` | 状态 | plan |
| `symbol` | 标的代码 | 600482.SS |
| `tab` | 页签/分类 | detail |
| `total_shares` | 总股本 | 2.26825e+09 |

### `yjfp_stock`

- **路径：** `/v1/yjfp/stock`
- **类型：** http
- **说明：** 个股业绩分配
- **签名：** `pro.yjfp_stock(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.yjfp_stock(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.yjfp_stock(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.yjfp_stock(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.yjfp_stock(ks_code='sh600519')
```

**数据样例**

| `assign_progress` | `basic_eps` | `bd10_close_adjchrate` | `bonus_it_ratio` | `bonus_ratio` | `bvps` | `code` | `d10_close_adjchrate` | `d30_close_adjchrate` | `dividend_ratio` | `equity_record_date` | `ex_dividend_date` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 实施分配 | 65.66 | -4.9989 |  |  | 195.355 | 600519 | -2.29101 | 12.0303 | 0.0231204 | 2026-06-25 | 2026-06-26 |
| 预披露 | 35.57 |  |  |  | 200.99 | 600519 | -2.29101 |  |  |  |  |
| 实施分配 | 51.53 | 0.492984 |  |  | 204.641 | 600519 | 2.22837 | 4.60426 | 0.0167414 | 2025-12-18 | 2025-12-19 |
| 实施分配 | 68.64 | -2.98243 |  |  | 185.565 | 600519 | -0.187395 | 0.165493 | 0.0192728 | 2025-06-25 | 2025-06-26 |
| 实施分配 | 48.42 | 2.64792 |  |  | 189.229 | 600519 | -6.34484 | -6.83311 | 0.0153977 | 2024-12-19 | 2024-12-20 |

（共 20 行，表中展示前 5 行、前 12/30 列）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `assign_progress` | 分红进度 | 实施分配 |
| `basic_eps` | 基本每股收益 | 65.66 |
| `bd10_close_adjchrate` | 除权前10日复权涨跌幅 | -4.9989 |
| `bonus_it_ratio` | 送转所得税比例 |  |
| `bonus_ratio` | 送转比例 |  |
| `bvps` | 每股净资产 | 195.355 |
| `code` | 代码 | 600519 |
| `d10_close_adjchrate` | 近10日复权涨跌幅 | -2.29101 |
| `d30_close_adjchrate` | 近30日复权涨跌幅 | 12.0303 |
| `dividend_ratio` | 股息率 | 0.0231204 |
| `equity_record_date` | 股权登记日 | 2026-06-25 |
| `ex_dividend_date` | 除权除息日 | 2026-06-26 |
| `ex_dividend_days` | 除权天数 | 76 |
| `impl_plan_profile` | 实施方案概况 | 10派280.2423元(含税) |
| `is_kcb` | 是否科创板 |  |
| `it_ratio` | 所得税比例 |  |
| `market_type` | 市场类型 | 069001001001 |
| `name` | 名称 | 贵州茅台 |
| `notice_date` | 公告日 | 2026-06-22 |
| `per_capital_reserve` | 每股资本公积 | 0.00125939 |
| `per_unassign_profit` | 每股未分配利润 | 153.246 |
| `plan_notice_date` | 预案公告日 | 2026-04-17 |
| `pnp_yoy_ratio` | 归母净利润同比 | -4.53225 |
| `pretax_bonus_rmb` | 税前红利（元） | 280.242 |
| `publish_date` | 公告日 | 2026-04-17 |
| `report_date` | 报告期 | 2025-12-31 |
| `status` | 状态 | implemented |
| `symbol` | 标的代码 | 600519.SS |
| `tab` | 页签/分类 | detail |
| `total_shares` | 总股本 | 1.25008e+09 |

### `yjfp_tabs`

- **路径：** `/v1/yjfp/tabs`
- **类型：** http
- **说明：** 业绩分配分类页签
- **签名：** `pro.yjfp_tabs(**opts)`

**用法**

- 基本调用

```python
pro.yjfp_tabs()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.yjfp_tabs(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.yjfp_tabs(as_dataframe=False)
```

**数据样例**

| `available` | `date_field` | `label` | `type` |
| --- | --- | --- | --- |
| True | plan_notice_date | 分红送配明细 | detail |
| True | report_date | 报告期列表 | report_dates |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `available` | 是否可用 | True |
| `date_field` | 日期字段名 | plan_notice_date |
| `label` | 标签 | 分红送配明细 |
| `type` | 类型 | detail |

## 目录

### `catalog_nodes_page`

- **路径：** `/v1/catalog/nodes`
- **类型：** http
- **说明：** 目录翻页（offset/limit）

**用法**

- offset=0 then 5

```python
(pro.catalog_nodes(limit=5, offset=0), pro.catalog_nodes(limit=5, offset=5))
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
(pro.catalog_nodes(limit=5, offset=0), pro.catalog_nodes(limit=5, offset=5), raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
(pro.catalog_nodes(limit=5, offset=0), pro.catalog_nodes(limit=5, offset=5), as_dataframe=False)
```

**数据样例**

| `category` | `is_leaf` | `market` | `member_count` | `name` | `node` | `parent_node` | `path` | `updated_at` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | False | A股 | 0 | A股 | hsgs |  | A股 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 902 | 广东省 | diyu_440000 | diyu | A股/地域板块/广东省 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 754 | 浙江省 | diyu_330000 | diyu | A股/地域板块/浙江省 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 735 | 江苏省 | diyu_320000 | diyu | A股/地域板块/江苏省 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 479 | 北京市 | diyu_110000 | diyu | A股/地域板块/北京市 | 2026-09-09 14:25:52 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `category` | 分类 |  |
| `is_leaf` | 是否叶子节点 | False |
| `market` | 市场 | A股 |
| `member_count` | 成分数量 | 0 |
| `name` | 名称 | A股 |
| `node` | 目录节点 | hsgs |
| `parent_node` | 父节点 |  |
| `path` | 路径 | A股 |
| `updated_at` | 更新时间 | 2026-09-09 14:25:52 |

### `catalog_nodes`

- **路径：** `/v1/catalog/nodes`
- **类型：** http
- **说明：** 目录节点
- **签名：** `pro.catalog_nodes(*, market=None, category=None, q=None, keyword=None, parent=None, leaves=None, limit=None, offset=None, **opts)`

**用法**

- 基本调用

```python
pro.catalog_nodes(limit=10)
```

**进阶用法**

- 进阶参数组合

```python
pro.catalog_nodes(q='银行', leaves=True)
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_nodes(limit=10, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_nodes(limit=10, as_dataframe=False)
```

- 指定市场（如 `SS` / `SZ`）

```python
pro.catalog_nodes(limit=10, market='SS')
```

- 榜单分类（如 `industry` / `concept`）

```python
pro.catalog_nodes(limit=10, category='industry')
```

- 关键词搜索

```python
pro.catalog_nodes(limit=10, keyword='茅台')
```

- 偏移

```python
pro.catalog_nodes(limit=10, offset=0)
```

**数据样例**

| `category` | `is_leaf` | `market` | `member_count` | `name` | `node` | `parent_node` | `path` | `updated_at` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | False | A股 | 0 | A股 | hsgs |  | A股 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 902 | 广东省 | diyu_440000 | diyu | A股/地域板块/广东省 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 754 | 浙江省 | diyu_330000 | diyu | A股/地域板块/浙江省 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 735 | 江苏省 | diyu_320000 | diyu | A股/地域板块/江苏省 | 2026-09-09 14:25:52 |
| 地域板块 | True | A股 | 479 | 北京市 | diyu_110000 | diyu | A股/地域板块/北京市 | 2026-09-09 14:25:52 |

（共 10 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `category` | 分类 |  |
| `is_leaf` | 是否叶子节点 | False |
| `market` | 市场 | A股 |
| `member_count` | 成分数量 | 0 |
| `name` | 名称 | A股 |
| `node` | 目录节点 | hsgs |
| `parent_node` | 父节点 |  |
| `path` | 路径 | A股 |
| `updated_at` | 更新时间 | 2026-09-09 14:25:52 |

### `catalog_node`

- **路径：** `/v1/catalog/nodes/hsgs`
- **类型：** http
- **说明：** 单节点
- **签名：** `pro.catalog_node(node, **opts)`

**用法**

- 基本调用

```python
pro.catalog_node('hsgs')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_node('hsgs', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_node('hsgs', as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `category` |  |
| `is_leaf` | False |
| `market` | A股 |
| `member_count` | 0 |
| `name` | A股 |
| `node` | hsgs |
| `parent_node` |  |
| `path` | A股 |
| `updated_at` | 2026-09-09 14:25:52 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `category` | 分类 |  |
| `is_leaf` | 是否叶子节点 | False |
| `market` | 市场 | A股 |
| `member_count` | 成分数量 | 0 |
| `name` | 名称 | A股 |
| `node` | 目录节点 | hsgs |
| `parent_node` | 父节点 |  |
| `path` | 路径 | A股 |
| `updated_at` | 更新时间 | 2026-09-09 14:25:52 |

### `catalog_node_children`

- **路径：** `/v1/catalog/nodes/hsgs/children`
- **类型：** http
- **说明：** 子节点
- **签名：** `pro.catalog_node_children(node, **opts)`

**用法**

- 基本调用

```python
pro.catalog_node_children('hsgs')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_node_children('hsgs', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_node_children('hsgs', as_dataframe=False)
```

**数据样例**


**`children` 展开（9 条）**

| `category` | `is_leaf` | `market` | `member_count` | `name` | `node` | `parent_node` | `path` | `updated_at` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 地域板块 | False | A股 | 0 | 地域板块 | diyu | hsgs | A股/地域板块 | 2026-09-09 14:25:52 |
| 行业 | False | A股 | 0 | 新浪行业 | sinahy | hsgs | A股/行业 | 2026-09-09 14:25:52 |
| 概念板块 | False | A股 | 0 | 概念板块 | gainianbankuai | hsgs | A股/概念板块 | 2026-09-09 14:25:52 |
| 热门概念 | False | A股 | 0 | 热门概念 | ch_gn | hsgs | A股/热门概念 | 2026-09-09 14:25:52 |
| 申万一级 | False | A股 | 0 | 申万一级 | sw1_hy | hsgs | A股/申万一级 | 2026-09-09 14:25:52 |

（共 9 行，表中展示前 5 行）

**`node` 展开**

| 字段 | 值 |
|------|-----|
| `category` |  |
| `is_leaf` | False |
| `market` | A股 |
| `member_count` | 0 |
| `name` | A股 |
| `node` | hsgs |
| `parent_node` |  |
| `path` | A股 |
| `updated_at` | 2026-09-09 14:25:52 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `children` | 子节点 | [9 项，见下方展开] |
| `node` | 目录节点 | {9 字段，见下方展开} |
| `children.category` | 子节点 → 分类 | 地域板块 |
| `children.is_leaf` | 子节点 → 是否叶子节点 | False |
| `children.market` | 子节点 → 市场 | A股 |
| `children.member_count` | 子节点 → 成分数量 | 0 |
| `children.name` | 子节点 → 名称 | 地域板块 |
| `children.node` | 子节点 → 目录节点 | diyu |
| `children.parent_node` | 子节点 → 父节点 | hsgs |
| `children.path` | 子节点 → 路径 | A股/地域板块 |
| `children.updated_at` | 子节点 → 更新时间 | 2026-09-09 14:25:52 |
| `node.category` | 目录节点 → 分类 |  |
| `node.is_leaf` | 目录节点 → 是否叶子节点 | False |
| `node.market` | 目录节点 → 市场 | A股 |
| `node.member_count` | 目录节点 → 成分数量 | 0 |
| `node.name` | 目录节点 → 名称 | A股 |
| `node.node` | 目录节点 → 目录节点 | hsgs |
| `node.parent_node` | 目录节点 → 父节点 |  |
| `node.path` | 目录节点 → 路径 | A股 |
| `node.updated_at` | 目录节点 → 更新时间 | 2026-09-09 14:25:52 |

### `catalog_node_members`

- **路径：** `/v1/catalog/nodes/hangye_ZA01/members`
- **类型：** http
- **说明：** 节点成分
- **签名：** `pro.catalog_node_members(node, *, limit=None, offset=None, **opts)`

**用法**

- 基本调用

```python
pro.catalog_node_members('hangye_ZA01', limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_node_members('hangye_ZA01', limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_node_members('hangye_ZA01', limit=5, as_dataframe=False)
```

- 偏移

```python
pro.catalog_node_members('hangye_ZA01', limit=5, offset=0)
```

**数据样例**


**`members` 展开（5 条）**

| `code` | `name` | `node` | `symbol` |
| --- | --- | --- | --- |
| 000713 | 国投丰乐 | hangye_ZA01 | 000713.SZ |
| 000998 | 隆平高科 | hangye_ZA01 | 000998.SZ |
| 002041 | 登海种业 | hangye_ZA01 | 002041.SZ |
| 002772 | 众兴菌业 | hangye_ZA01 | 002772.SZ |
| 300087 | ST荃银 | hangye_ZA01 | 300087.SZ |

**`node` 展开**

| 字段 | 值 |
|------|-----|
| `category` | 证监会行业 |
| `is_leaf` | True |
| `market` | A股 |
| `member_count` | 15 |
| `name` | 农业 |
| `node` | hangye_ZA01 |
| `parent_node` | hangye_ZA |
| `path` | A股/证监会行业/农、林、牧、渔业/农业 |
| `updated_at` | 2026-09-09 14:25:52 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `members` | 成分 | [5 项，见下方展开] |
| `node` | 目录节点 | {9 字段，见下方展开} |
| `members.code` | 成分 → 代码 | 000713 |
| `members.name` | 成分 → 名称 | 国投丰乐 |
| `members.node` | 成分 → 目录节点 | hangye_ZA01 |
| `members.symbol` | 成分 → 标的代码 | 000713.SZ |
| `node.category` | 目录节点 → 分类 | 证监会行业 |
| `node.is_leaf` | 目录节点 → 是否叶子节点 | True |
| `node.market` | 目录节点 → 市场 | A股 |
| `node.member_count` | 目录节点 → 成分数量 | 15 |
| `node.name` | 目录节点 → 名称 | 农业 |
| `node.node` | 目录节点 → 目录节点 | hangye_ZA01 |
| `node.parent_node` | 目录节点 → 父节点 | hangye_ZA |
| `node.path` | 目录节点 → 路径 | A股/证监会行业/农、林、牧、渔业/农业 |
| `node.updated_at` | 目录节点 → 更新时间 | 2026-09-09 14:25:52 |

### `catalog_plates`

- **路径：** `/v1/catalog/plates`
- **类型：** http
- **说明：** 板块目录
- **签名：** `pro.catalog_plates(*, type=None, q=None, **opts)`

**用法**

- 基本调用

```python
pro.catalog_plates()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_plates(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_plates(as_dataframe=False)
```

- 搜索词别名

```python
pro.catalog_plates(q='章盟主')
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `limit_up_count` | `member_count` | `name` | `plate_id` | `rank` | `reason` | `rise_count` | `types` | `updated_at` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0676407 | 0 | -5.72583e+07 | 1 | 4 | 黄酒 | 38053809 | 1 |  | 4 | ["industry"] | 2026-09-09 14:25:52 |
| 0.0541749 | 1 | 6.80559e+08 | 1 | 8 | 白糖 | 22431937 | 2 |  | 7 | ["industry"] | 2026-09-09 14:25:52 |
| 0.0360682 | 0 | 9.39463e+08 | 1 | 10 | 有色 · 锑 | 18963793 | 3 |  | 10 | ["industry"] | 2026-09-09 14:25:52 |
| 0.0330637 | 2 | 8.80144e+08 | 2 | 24 | 航运 | 17627122 | 4 | 沙特—中国VLCC航线日收益较一年前上涨超过10倍 | 22 | ["industry"] | 2026-09-09 14:25:52 |
| 0.0310457 | 3 | 3.83127e+08 | 1 | 17 | 培育钻石 | 43539673 | 5 |  | 14 | ["concept"] | 2026-09-09 14:25:52 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.0676407 |
| `fall_count` | 下跌家数 | 0 |
| `fund_flow` | 资金流向 | -5.72583e+07 |
| `limit_up_count` | 涨停家数 | 1 |
| `member_count` | 成分数量 | 4 |
| `name` | 名称 | 黄酒 |
| `plate_id` | 板块编号 | 38053809 |
| `rank` | 排名 | 1 |
| `reason` | 涨停/异动原因 |  |
| `rise_count` | 上涨家数 | 4 |
| `types` | 字段 `types` | ["industry"] |
| `updated_at` | 更新时间 | 2026-09-09 14:25:52 |

### `catalog_plate_members`

- **路径：** `/v1/catalog/plates/38053809/members`
- **类型：** http
- **说明：** 板块成分
- **签名：** `pro.catalog_plate_members(plate_id, *, include_desc=None, **opts)`

**用法**

- 基本调用

```python
pro.catalog_plate_members(38053809)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_plate_members(38053809, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_plate_members(38053809, as_dataframe=False)
```

**数据样例**


**`members` 展开（4 条）**

| `core_flag` | `industry_leader` | `is_new` | `sort_order` | `symbol` |
| --- | --- | --- | --- | --- |
| 100 | False | False | 0 | 600059.SS |
| nan | False | False | 1 | 600382.SS |
| 100 | False | False | 2 | 600616.SS |
| 100 | False | False | 3 | 601579.SS |

**`plate` 展开**

| 字段 | 值 |
|------|-----|
| `change_percent` | 0.0676407 |
| `fall_count` | 0 |
| `fund_flow` | -5.72583e+07 |
| `limit_up_count` | 1 |
| `member_count` | 4 |
| `name` | 黄酒 |
| `plate_id` | 38053809 |
| `rank` | 1 |
| `reason` |  |
| `rise_count` | 4 |
| `types` | ["industry"] |
| `updated_at` | 2026-09-09 14:25:52 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `members` | 成分 | [4 项，见下方展开] |
| `plate` | 板块 | {12 字段，见下方展开} |
| `members.core_flag` | 成分 → 核心标记 | 100 |
| `members.industry_leader` | 成分 → 行业龙头 | False |
| `members.is_new` | 成分 → 是否新股/新条 | False |
| `members.sort_order` | 成分 → 排序方向 | 0 |
| `members.symbol` | 成分 → 标的代码 | 600059.SS |
| `plate.change_percent` | 板块 → 涨跌幅（%） | 0.0676407 |
| `plate.fall_count` | 板块 → 下跌家数 | 0 |
| `plate.fund_flow` | 板块 → 资金流向 | -5.72583e+07 |
| `plate.limit_up_count` | 板块 → 涨停家数 | 1 |
| `plate.member_count` | 板块 → 成分数量 | 4 |
| `plate.name` | 板块 → 名称 | 黄酒 |
| `plate.plate_id` | 板块 → 板块编号 | 38053809 |
| `plate.rank` | 板块 → 排名 | 1 |
| `plate.reason` | 板块 → 涨停/异动原因 |  |
| `plate.rise_count` | 板块 → 上涨家数 | 4 |
| `plate.types` | 板块 → 字段 `types` | ["industry"] |
| `plate.updated_at` | 板块 → 更新时间 | 2026-09-09 14:25:52 |

### `catalog_indices`

- **路径：** `/v1/catalog/indices`
- **类型：** http
- **说明：** 指数目录
- **签名：** `pro.catalog_indices(**opts)`

**用法**

- 基本调用

```python
pro.catalog_indices()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_indices(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_indices(as_dataframe=False)
```

**数据样例**

| `active_member_count` | `code` | `name` | `total_member_count` | `updated_at` |
| --- | --- | --- | --- | --- |
| 5311 | 399317 | 国证A指 | 6120 | 2026-09-09 14:25:52 |
| 5195 | 801003 | 申万Ａ指 | 5298 | 2026-09-09 14:25:52 |
| 5173 | 930903 | 中证A股 | 5726 | 2026-09-09 14:25:52 |
| 5173 | H20903 | 中证A股全收益 | 5724 | 2026-09-09 14:25:52 |
| 5173 | N20903 | 中证A股净收益 | 5722 | 2026-09-09 14:25:52 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `active_member_count` | 活跃成分数 | 5311 |
| `code` | 代码 | 399317 |
| `name` | 名称 | 国证A指 |
| `total_member_count` | 成分总数 | 6120 |
| `updated_at` | 更新时间 | 2026-09-09 14:25:52 |

### `catalog_index_members`

- **路径：** `/v1/catalog/indices/399317/members`
- **类型：** http
- **说明：** 指数成分
- **签名：** `pro.catalog_index_members(code, **opts)`

**用法**

- 基本调用

```python
pro.catalog_index_members('399317')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_index_members('399317', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_index_members('399317', as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `code` | 399317 |

**`members` 展开（20 条）**

| `enter_date` | `exit_date` | `index_code` | `index_name` | `is_active` | `name` | `symbol` |
| --- | --- | --- | --- | --- | --- | --- |
| 1900-01-01 |  | 399317 | 巨潮A指 | True | 平安银行 | 000001.SZ |
| 1900-01-01 |  | 399317 | 巨潮A指 | True | 万科A | 000002.SZ |
| 1900-01-01 |  | 399317 | 巨潮A指 | True | 深振业A | 000006.SZ |
| 1900-01-01 |  | 399317 | 巨潮A指 | True | 全新好 | 000007.SZ |
| 2024-07-02 |  | 399317 | 国证A指 | True | 全新好 | 000007.SZ |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `code` | 代码 | 399317 |
| `members` | 成分 | [20 项，见下方展开] |
| `members.enter_date` | 成分 → 入选日期 | 1900-01-01 |
| `members.exit_date` | 成分 → 剔除日期 |  |
| `members.index_code` | 成分 → 指数代码 | 399317 |
| `members.index_name` | 成分 → 指数名称 | 巨潮A指 |
| `members.is_active` | 成分 → 是否有效 | True |
| `members.name` | 成分 → 名称 | 平安银行 |
| `members.symbol` | 成分 → 标的代码 | 000001.SZ |

### `catalog_stock`

- **路径：** `/v1/catalog/stocks/600519.SS`
- **类型：** http
- **说明：** 个股目录条目
- **签名：** `pro.catalog_stock(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.catalog_stock(symbol='600519.SH')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.catalog_stock(ks_code='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.catalog_stock(symbol='600519.SH', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.catalog_stock(symbol='600519.SH', as_dataframe=False)
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `symbol` | 600519.SS |

**`indices` 展开（20 条）**

| `code` | `enter_date` | `exit_date` | `is_active` | `name` |
| --- | --- | --- | --- | --- |
| 000001 | 2001-08-27 |  | True | 上证指数 |
| 000001CNY01 | 2020-10-09 |  | True | 上证指数全收益 |
| 000002 | 2001-08-27 |  | True | A股指数 |
| 000004 |  |  | True | 工业指数 |
| 000010 | 2002-07-01 |  | True | 上证180 |

（共 20 行，表中展示前 5 行）

**`nodes` 展开（20 条）**

| `category` | `is_leaf` | `market` | `member_count` | `name` | `node` | `parent_node` | `path` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 地域板块 | True | A股 | 34 | 贵州省 | diyu_520000 | diyu | A股/地域板块/贵州省 |
| 行业 | True | A股 | 33 | 酿酒行业 | new_ljhy | sinahy | A股/行业/酿酒行业 |
| 概念板块 | True | A股 | 100 | QFII重仓 | gn_QFIIzc | gainianbankuai | A股/概念板块/QFII重仓 |
| 概念板块 | True | A股 | 38 | 白酒概念 | gn_bjgn | gainianbankuai | A股/概念板块/白酒概念 |
| 概念板块 | True | A股 | 100 | 保险重仓 | gn_bxzc | gainianbankuai | A股/概念板块/保险重仓 |

（共 20 行，表中展示前 5 行）

**`plates` 展开（4 条）**

| `industry_leader` | `member_count` | `name` | `plate_id` | `sort_order` | `types` |
| --- | --- | --- | --- | --- | --- |
| False | 113 | 高价股 | 13011026 | 83 | ["style"] |
| False | 77 | 白马股 | 24364114 | 43 | ["style"] |
| False | 95 | 大消费 | 6346009 | 93 | ["style"] |
| True | 37 | 白酒 | 16961441 | 13 | ["industry"] |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `indices` | 指数列表 | [20 项，见下方展开] |
| `nodes` | 节点列表 | [20 项，见下方展开] |
| `plates` | 板块列表 | [4 项，见下方展开] |
| `symbol` | 标的代码 | 600519.SS |
| `indices.code` | 指数列表 → 代码 | 000001 |
| `indices.enter_date` | 指数列表 → 入选日期 | 2001-08-27 |
| `indices.exit_date` | 指数列表 → 剔除日期 |  |
| `indices.is_active` | 指数列表 → 是否有效 | True |
| `indices.name` | 指数列表 → 名称 | 上证指数 |
| `nodes.category` | 节点列表 → 分类 | 地域板块 |
| `nodes.is_leaf` | 节点列表 → 是否叶子节点 | True |
| `nodes.market` | 节点列表 → 市场 | A股 |
| `nodes.member_count` | 节点列表 → 成分数量 | 34 |
| `nodes.name` | 节点列表 → 名称 | 贵州省 |
| `nodes.node` | 节点列表 → 目录节点 | diyu_520000 |
| `nodes.parent_node` | 节点列表 → 父节点 | diyu |
| `nodes.path` | 节点列表 → 路径 | A股/地域板块/贵州省 |
| `plates.industry_leader` | 板块列表 → 行业龙头 | False |
| `plates.member_count` | 板块列表 → 成分数量 | 113 |
| `plates.name` | 板块列表 → 名称 | 高价股 |
| `plates.plate_id` | 板块列表 → 板块编号 | 13011026 |
| `plates.sort_order` | 板块列表 → 排序方向 | 83 |
| `plates.types` | 板块列表 → 字段 `types` | ["style"] |

## 债券族（bond / convertible / treasury / enterprise）

### `bond`

- **路径：** `/v1/bond`
- **类型：** http
- **说明：** 债券查询
- **签名：** `pro.bond(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.bond(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bond(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `bond_profile`

- **路径：** `/v1/bond/profile`
- **类型：** http
- **说明：** 债券档案
- **签名：** `pro.bond_profile(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.bond_profile(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_profile(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_profile(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bond_profile(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `bonds`

- **路径：** `/v1/bonds`
- **类型：** http
- **说明：** 债券列表
- **签名：** `pro.bonds(*, keyword=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.bonds(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bonds(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bonds(limit=5, as_dataframe=False)
```

- 关键词搜索

```python
pro.bonds(limit=5, keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `bond_boards`

- **路径：** `/v1/bond/boards`
- **类型：** http
- **说明：** 债券板块列表
- **签名：** `pro.bond_boards(**opts)`

**用法**

- 基本调用

```python
pro.bond_boards()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_boards(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_boards(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `bond_board`

- **路径：** `/v1/bond/boards/default`
- **类型：** http
- **说明：** 债券单板块详情
- **签名：** `pro.bond_board(board, **opts)`

**用法**

- 基本调用

```python
pro.bond_board('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_board('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_board('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `bond_board_members`

- **路径：** `/v1/bond/boards/default/members`
- **类型：** http
- **说明：** 债券板块成分
- **签名：** `pro.bond_board_members(board, **opts)`

**用法**

- 基本调用

```python
pro.bond_board_members('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_board_members('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_board_members('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `bond_realtime`

- **路径：** `/v1/bond/realtime`
- **类型：** http
- **说明：** 债券实时行情
- **签名：** `pro.bond_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.bond_realtime(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_realtime(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_realtime(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bond_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `bond_trend`

- **路径：** `/v1/bond/trend`
- **类型：** http
- **说明：** 债券分时
- **签名：** `pro.bond_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.bond_trend(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_trend(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_trend(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bond_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.bond_trend(symbol='600519.SS', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `bond_kline`

- **路径：** `/v1/bond/kline`
- **类型：** http
- **说明：** 债券K线
- **签名：** `pro.bond_kline(symbol=None, *, ks_code=None, **opts)`
- **介绍：** 兼容别名；可转债请用 `convertible_kline`（/v2）。

**用法**

- 基本调用

```python
pro.bond_kline(
    symbol='600519.SS', period=86400, count=2
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.bond_kline(
    symbol='600519.SS', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.bond_kline(
    symbol='600519.SS', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.bond_kline(
    ks_code='sh600519', period=86400, count=2
)
```

**数据样例**

暂无可用样例：无样例

### `convertible`

- **路径：** `/v1/convertible`
- **类型：** http
- **说明：** 可转债查询
- **签名：** `pro.convertible(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.convertible(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.convertible(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `convertible_profile`

- **路径：** `/v1/convertible/profile`
- **类型：** http
- **说明：** 可转债档案
- **签名：** `pro.convertible_profile(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.convertible_profile(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_profile(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_profile(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.convertible_profile(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `convertibles`

- **路径：** `/v1/convertibles`
- **类型：** http
- **说明：** 可转债列表
- **签名：** `pro.convertibles(*, keyword=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.convertibles(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertibles(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertibles(limit=5, as_dataframe=False)
```

- 关键词搜索

```python
pro.convertibles(limit=5, keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `convertible_boards`

- **路径：** `/v1/convertible/boards`
- **类型：** http
- **说明：** 可转债板块列表
- **签名：** `pro.convertible_boards(**opts)`

**用法**

- 基本调用

```python
pro.convertible_boards()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_boards(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_boards(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `convertible_board`

- **路径：** `/v1/convertible/boards/default`
- **类型：** http
- **说明：** 可转债单板块详情
- **签名：** `pro.convertible_board(board, **opts)`

**用法**

- 基本调用

```python
pro.convertible_board('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_board('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_board('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `convertible_board_members`

- **路径：** `/v1/convertible/boards/default/members`
- **类型：** http
- **说明：** 可转债板块成分
- **签名：** `pro.convertible_board_members(board, **opts)`

**用法**

- 基本调用

```python
pro.convertible_board_members('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_board_members('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_board_members('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `convertible_realtime`

- **路径：** `/v1/convertible/realtime`
- **类型：** http
- **说明：** 可转债实时行情
- **签名：** `pro.convertible_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.convertible_realtime(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_realtime(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_realtime(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.convertible_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `convertible_trend`

- **路径：** `/v1/convertible/trend`
- **类型：** http
- **说明：** 可转债分时
- **签名：** `pro.convertible_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.convertible_trend(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_trend(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_trend(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.convertible_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.convertible_trend(symbol='600519.SS', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `convertible_kline`

- **路径：** `/v2/convertible/kline`
- **类型：** http
- **说明：** 可转债K线
- **签名：** `pro.convertible_kline(symbol=None, *, ks_code=None, **opts)`
- **介绍：** 可转债 K 线 `GET /v2/convertible/kline`。

**用法**

- 基本调用

```python
pro.convertible_kline(
    symbol='600519.SS', period=86400, count=2
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_kline(
    symbol='600519.SS', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_kline(
    symbol='600519.SS', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.convertible_kline(
    ks_code='sh600519', period=86400, count=2
)
```

**数据样例**

暂无可用样例：无样例

### `convertible_auction`

- **路径：** `/v1/convertible/auction`
- **类型：** http
- **说明：** 可转债竞价
- **签名：** `pro.convertible_auction(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.convertible_auction(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_auction(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_auction(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.convertible_auction(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `convertible_auction_v2`

- **路径：** `/v2/convertible/auction`
- **类型：** http
- **说明：** 可转债竞价紧凑格式（一般用 all=True 拉全市场）
- **签名：** `pro.convertible_auction_v2(symbol=None, *, ks_code=None, all=None, **opts)`
- **介绍：** 可转债竞价 compact `GET /v2/convertible/auction`。

**用法**

- 全市场（推荐）

```python
pro.convertible_auction_v2(all=True)
```

**进阶用法**

- 指定标的

```python
pro.convertible_auction_v2(symbol='600519.SS')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.convertible_auction_v2(all=True, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.convertible_auction_v2(all=True, as_dataframe=False)
```

- 保留紧凑格式原始结构（`expand_compact_rows=False`）

```python
pro.convertible_auction_v2(all=True, expand_compact_rows=False)
```

**数据样例**

暂无可用样例：无样例

### `treasury`

- **路径：** `/v1/treasury`
- **类型：** http
- **说明：** 国债查询
- **签名：** `pro.treasury(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.treasury(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.treasury(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `treasury_profile`

- **路径：** `/v1/treasury/profile`
- **类型：** http
- **说明：** 国债档案
- **签名：** `pro.treasury_profile(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.treasury_profile(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_profile(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_profile(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.treasury_profile(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `treasuries`

- **路径：** `/v1/treasuries`
- **类型：** http
- **说明：** 国债列表
- **签名：** `pro.treasuries(*, keyword=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.treasuries(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasuries(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasuries(limit=5, as_dataframe=False)
```

- 关键词搜索

```python
pro.treasuries(limit=5, keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `treasury_boards`

- **路径：** `/v1/treasury/boards`
- **类型：** http
- **说明：** 国债板块列表
- **签名：** `pro.treasury_boards(**opts)`

**用法**

- 基本调用

```python
pro.treasury_boards()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_boards(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_boards(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `treasury_board`

- **路径：** `/v1/treasury/boards/default`
- **类型：** http
- **说明：** 国债单板块详情
- **签名：** `pro.treasury_board(board, **opts)`

**用法**

- 基本调用

```python
pro.treasury_board('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_board('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_board('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `treasury_board_members`

- **路径：** `/v1/treasury/boards/default/members`
- **类型：** http
- **说明：** 国债板块成分
- **签名：** `pro.treasury_board_members(board, **opts)`

**用法**

- 基本调用

```python
pro.treasury_board_members('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_board_members('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_board_members('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `treasury_realtime`

- **路径：** `/v1/treasury/realtime`
- **类型：** http
- **说明：** 国债实时行情
- **签名：** `pro.treasury_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.treasury_realtime(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_realtime(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_realtime(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.treasury_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `treasury_trend`

- **路径：** `/v1/treasury/trend`
- **类型：** http
- **说明：** 国债分时
- **签名：** `pro.treasury_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.treasury_trend(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_trend(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_trend(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.treasury_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.treasury_trend(symbol='600519.SS', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `treasury_kline`

- **路径：** `/v1/treasury/kline`
- **类型：** http
- **说明：** 国债K线
- **签名：** `pro.treasury_kline(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.treasury_kline(
    symbol='600519.SS', period=86400, count=2
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.treasury_kline(
    symbol='600519.SS', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.treasury_kline(
    symbol='600519.SS', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.treasury_kline(
    ks_code='sh600519', period=86400, count=2
)
```

**数据样例**

暂无可用样例：无样例

### `enterprise`

- **路径：** `/v1/enterprise`
- **类型：** http
- **说明：** 企业债查询
- **签名：** `pro.enterprise(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.enterprise(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.enterprise(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `enterprise_profile`

- **路径：** `/v1/enterprise/profile`
- **类型：** http
- **说明：** 企业债档案
- **签名：** `pro.enterprise_profile(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.enterprise_profile(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_profile(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_profile(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.enterprise_profile(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `enterprises`

- **路径：** `/v1/enterprises`
- **类型：** http
- **说明：** 企业债列表
- **签名：** `pro.enterprises(*, keyword=None, limit=None, **opts)`

**用法**

- 基本调用

```python
pro.enterprises(limit=5)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprises(limit=5, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprises(limit=5, as_dataframe=False)
```

- 关键词搜索

```python
pro.enterprises(limit=5, keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `enterprise_boards`

- **路径：** `/v1/enterprise/boards`
- **类型：** http
- **说明：** 企业债板块列表
- **签名：** `pro.enterprise_boards(**opts)`

**用法**

- 基本调用

```python
pro.enterprise_boards()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_boards(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_boards(as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `enterprise_board`

- **路径：** `/v1/enterprise/boards/default`
- **类型：** http
- **说明：** 企业债单板块详情
- **签名：** `pro.enterprise_board(board, **opts)`

**用法**

- 基本调用

```python
pro.enterprise_board('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_board('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_board('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `enterprise_board_members`

- **路径：** `/v1/enterprise/boards/default/members`
- **类型：** http
- **说明：** 企业债板块成分
- **签名：** `pro.enterprise_board_members(board, **opts)`

**用法**

- 基本调用

```python
pro.enterprise_board_members('default')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_board_members('default', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_board_members('default', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `enterprise_realtime`

- **路径：** `/v1/enterprise/realtime`
- **类型：** http
- **说明：** 企业债实时行情
- **签名：** `pro.enterprise_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.enterprise_realtime(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_realtime(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_realtime(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.enterprise_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `enterprise_trend`

- **路径：** `/v1/enterprise/trend`
- **类型：** http
- **说明：** 企业债分时
- **签名：** `pro.enterprise_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.enterprise_trend(symbol='600519.SS')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_trend(symbol='600519.SS', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_trend(symbol='600519.SS', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.enterprise_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.enterprise_trend(symbol='600519.SS', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `enterprise_kline`

- **路径：** `/v1/enterprise/kline`
- **类型：** http
- **说明：** 企业债K线
- **签名：** `pro.enterprise_kline(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.enterprise_kline(
    symbol='600519.SS', period=86400, count=2
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.enterprise_kline(
    symbol='600519.SS', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.enterprise_kline(
    symbol='600519.SS', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.enterprise_kline(
    ks_code='sh600519', period=86400, count=2
)
```

**数据样例**

暂无可用样例：无样例

## 扩展市场（贵金属 / 期货 / 全球 / 美股 / 港股 / 板块）

### `metal_realtime`

- **路径：** `/v1/metal/realtime`
- **类型：** http
- **说明：** 贵金属实时
- **签名：** `pro.metal_realtime(symbol=None, *, symbols=None, ks_code=None, **opts)`
- **介绍：** 贵金属实时 `GET /v1/metal/realtime`（`symbol` / `symbols`）。

**用法**

- 基本调用

```python
pro.metal_realtime()
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.metal_realtime(symbols='XAUUSD')
```

**进阶用法**

- 进阶参数组合

```python
pro.metal_realtime(symbol='XAUUSD')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.metal_realtime(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.metal_realtime(as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.metal_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `metal_kline`

- **路径：** `/v2/metal/kline`
- **类型：** http
- **说明：** 贵金属K线
- **签名：** `pro.metal_kline(symbol=None, *, ks_code=None, period=None, count=None, timestamp=None, **opts)`
- **介绍：** 贵金属 K 线 `GET /v2/metal/kline`。

**用法**

- 基本调用

```python
pro.metal_kline(symbol='XAUUSD', period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.metal_kline(symbol='XAUUSD', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.metal_kline(symbol='XAUUSD', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.metal_kline(ks_code='sh600519', period=86400, count=2)
```

- 翻页游标（请求参数为秒）

```python
pro.metal_kline(symbol='XAUUSD', period=86400, count=2, timestamp=1700000000)
```

**数据样例**

暂无可用样例：无样例

### `metal_physical_brands`

- **路径：** `/v1/metal/physical/brands`
- **类型：** http
- **说明：** 实物金品牌
- **签名：** `pro.metal_physical_brands(*, keyword=None, **opts)`

**用法**

- 基本调用

```python
pro.metal_physical_brands()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.metal_physical_brands(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.metal_physical_brands(as_dataframe=False)
```

- 关键词搜索

```python
pro.metal_physical_brands(keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `metal_physical_products`

- **路径：** `/v1/metal/physical/products`
- **类型：** http
- **说明：** 实物金产品
- **签名：** `pro.metal_physical_products(*, brand=None, keyword=None, **opts)`

**用法**

- 基本调用

```python
pro.metal_physical_products()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.metal_physical_products(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.metal_physical_products(as_dataframe=False)
```

- 关键词搜索

```python
pro.metal_physical_products(keyword='茅台')
```

**数据样例**

暂无可用样例：无样例

### `metal_physical_prices`

- **路径：** `/v1/metal/physical/prices`
- **类型：** http
- **说明：** 实物金报价
- **签名：** `pro.metal_physical_prices(*, date=None, brand=None, product=None, start_date=None, end_date=None, **opts)`

**用法**

- 基本调用

```python
pro.metal_physical_prices()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.metal_physical_prices(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.metal_physical_prices(as_dataframe=False)
```

- 指定交易日

```python
pro.metal_physical_prices(date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `futures_realtime`

- **路径：** `/v1/futures/realtime`
- **类型：** http
- **说明：** 期货实时
- **签名：** `pro.futures_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.futures_realtime()
```

**进阶用法**

- 进阶参数组合

```python
pro.futures_realtime(symbol='rb2501')
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.futures_realtime(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.futures_realtime(as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.futures_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `futures_kline`

- **路径：** `/v2/futures/kline`
- **类型：** http
- **说明：** 期货K线
- **签名：** `pro.futures_kline(symbol=None, *, ks_code=None, period=None, count=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.futures_kline(symbol='rb2501', period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.futures_kline(symbol='rb2501', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.futures_kline(symbol='rb2501', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.futures_kline(ks_code='sh600519', period=86400, count=2)
```

- 翻页游标（请求参数为秒）

```python
pro.futures_kline(symbol='rb2501', period=86400, count=2, timestamp=1700000000)
```

**数据样例**

暂无可用样例：无样例

### `futures_stream`

- **路径：** `/v1/futures/stream`
- **类型：** sse
- **说明：** 期货推流
- **签名：** `pro.futures_stream(**opts)`
- **介绍：** 国内期货推送 SSE `GET /v1/futures/stream`。

**用法**

- futures_stream

```python
next(iter(pro.futures_stream()))
```

**数据样例**

暂无可用样例：无样例

### `futures_v2_realtime`

- **路径：** `/v1/futures-v2/realtime`
- **类型：** http
- **说明：** 期货二代实时
- **签名：** `pro.futures_v2_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.futures_v2_realtime()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.futures_v2_realtime(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.futures_v2_realtime(as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.futures_v2_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `futures_v2_trend`

- **路径：** `/v1/futures-v2/trend`
- **类型：** http
- **说明：** 期货二代分时
- **签名：** `pro.futures_v2_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.futures_v2_trend(symbol='rb2501')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.futures_v2_trend(symbol='rb2501', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.futures_v2_trend(symbol='rb2501', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.futures_v2_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.futures_v2_trend(symbol='rb2501', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `futures_v2_kline`

- **路径：** `/v2/futures-v2/kline`
- **类型：** http
- **说明：** 期货二代K线
- **签名：** `pro.futures_v2_kline(symbol=None, *, ks_code=None, period=None, count=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.futures_v2_kline(symbol='rb2501', period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.futures_v2_kline(symbol='rb2501', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.futures_v2_kline(symbol='rb2501', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.futures_v2_kline(ks_code='sh600519', period=86400, count=2)
```

- 翻页游标（请求参数为秒）

```python
pro.futures_v2_kline(symbol='rb2501', period=86400, count=2, timestamp=1700000000)
```

**数据样例**

暂无可用样例：无样例

### `futures_v2_stream`

- **路径：** `/v1/futures-v2/stream`
- **类型：** sse
- **说明：** 期货二代推流
- **签名：** `pro.futures_v2_stream(**opts)`

**用法**

- futures_v2_stream

```python
next(iter(pro.futures_v2_stream()))
```

**数据样例**

暂无可用样例：无样例

### `global_index_realtime`

- **路径：** `/v1/global-index/realtime`
- **类型：** http
- **说明：** 全球指数实时
- **签名：** `pro.global_index_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.global_index_realtime(symbol='DJI')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.global_index_realtime(symbol='DJI', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.global_index_realtime(symbol='DJI', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.global_index_realtime(ks_code='sh600519')
```

**数据样例**

| `change` | `change_pct` | `high` | `low` | `name` | `open` | `prev_close` | `price` | `symbol` | `timestamp` | `volume` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -333.02 | -0.642105 | 51846.8 | 51522.1 | 道琼斯工业平均指数 | 51771.4 | 51863.7 | 51530.7 | DJI.GI | 1790182269000 | 1.9608e+08 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change` | 涨跌额 | -333.02 |
| `change_pct` | 涨跌幅 | -0.642105 |
| `high` | 最高价 | 51846.8 |
| `low` | 最低价 | 51522.1 |
| `name` | 名称 | 道琼斯工业平均指数 |
| `open` | 开盘价 | 51771.4 |
| `prev_close` | 昨收 | 51863.7 |
| `price` | 最新价 | 51530.7 |
| `symbol` | 标的代码 | DJI.GI |
| `timestamp` | 时间戳（毫秒） | 1790182269000 |
| `volume` | 成交量 | 1.9608e+08 |

### `global_index_trend`

- **路径：** `/v1/global-index/trend`
- **类型：** http
- **说明：** 全球指数分时
- **签名：** `pro.global_index_trend(symbol=None, *, ks_code=None, date=None, **opts)`

**用法**

- 基本调用

```python
pro.global_index_trend(symbol='DJI')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.global_index_trend(symbol='DJI', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.global_index_trend(symbol='DJI', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.global_index_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.global_index_trend(symbol='DJI', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `global_index_kline`

- **路径：** `/v2/global-index/kline`
- **类型：** http
- **说明：** 全球指数K线
- **签名：** `pro.global_index_kline(symbol=None, *, ks_code=None, period=None, count=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.global_index_kline(symbol='DJI', period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.global_index_kline(symbol='DJI', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.global_index_kline(symbol='DJI', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.global_index_kline(ks_code='sh600519', period=86400, count=2)
```

- 翻页游标（请求参数为秒）

```python
pro.global_index_kline(symbol='DJI', period=86400, count=2, timestamp=1700000000)
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DJI.GI | 20260921 | 1790006400000 | 52301.9 | 52319 | 51726.1 | 51863.7 | 4.4315e+08 | 0 |
| DJI.GI | 20260922 | 1790092800000 | 51771.4 | 51846.8 | 51522.1 | 51541.2 | 1.95856e+08 | 0 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | DJI.GI |
| `date` | 交易日 | 20260921 |
| `timestamp` | 时间戳（毫秒） | 1790006400000 |
| `open` | 开盘价 | 52301.9 |
| `high` | 最高价 | 52319 |
| `low` | 最低价 | 51726.1 |
| `close` | 收盘价 / 最新价 | 51863.7 |
| `volume` | 成交量 | 4.4315e+08 |
| `amount` | 成交额 | 0 |

### `global_bond_realtime`

- **路径：** `/v1/global-bond/realtime`
- **类型：** http
- **说明：** 全球债券实时
- **签名：** `pro.global_bond_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.global_bond_realtime(symbol='US10Y')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.global_bond_realtime(symbol='US10Y', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.global_bond_realtime(symbol='US10Y', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.global_bond_realtime(ks_code='sh600519')
```

**数据样例**

暂无可用样例：无样例

### `global_bond_kline`

- **路径：** `/v2/global-bond/kline`
- **类型：** http
- **说明：** 全球债券K线
- **签名：** `pro.global_bond_kline(symbol=None, *, ks_code=None, period=None, count=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.global_bond_kline(symbol='US10Y', period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.global_bond_kline(symbol='US10Y', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.global_bond_kline(symbol='US10Y', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.global_bond_kline(ks_code='sh600519', period=86400, count=2)
```

- 翻页游标（请求参数为秒）

```python
pro.global_bond_kline(symbol='US10Y', period=86400, count=2, timestamp=1700000000)
```

**数据样例**

暂无可用样例：无样例

### `usstock_realtime`

- **路径：** `/v1/usstock/realtime`
- **类型：** http
- **说明：** 美股实时
- **签名：** `pro.usstock_realtime(symbol=None, *, ks_code=None, **opts)`

**用法**

- 基本调用

```python
pro.usstock_realtime(symbol='AAPL')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.usstock_realtime(ks_code='AAPL.US')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.usstock_realtime(symbol='AAPL', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.usstock_realtime(symbol='AAPL', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `usstock_trend`

- **路径：** `/v1/usstock/trend`
- **类型：** http
- **说明：** 美股分时
- **签名：** `pro.usstock_trend(symbol=None, *, ks_code=None, date=None, day=None, **opts)`

**用法**

- 基本调用

```python
pro.usstock_trend(symbol='AAPL.US')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.usstock_trend(symbol='AAPL.US', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.usstock_trend(symbol='AAPL.US', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.usstock_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.usstock_trend(symbol='AAPL.US', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `usstock_kline`

- **路径：** `/v2/usstock/kline`
- **类型：** http
- **说明：** 美股K线
- **签名：** `pro.usstock_kline(symbol=None, *, ks_code=None, period=None, adjust_type=None, count=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.usstock_kline(symbol='AAPL.US', period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.usstock_kline(symbol='AAPL.US', period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.usstock_kline(symbol='AAPL.US', period=86400, count=2, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.usstock_kline(ks_code='sh600519', period=86400, count=2)
```

- 复权类型

```python
pro.usstock_kline(symbol='AAPL.US', period=86400, count=2, adjust_type='forward')
```

- 翻页游标（请求参数为秒）

```python
pro.usstock_kline(symbol='AAPL.US', period=86400, count=2, timestamp=1700000000)
```

**数据样例**

暂无可用样例：无样例

### `hkstock_realtime`

- **路径：** `/v1/hkstock/realtime`
- **类型：** http
- **说明：** 港股实时
- **签名：** `pro.hkstock_realtime(symbol=None, *, ks_code=None, **opts)`
- **介绍：** 港股实时 `GET /v1/hkstock/realtime`（scope `hkstock_realtime`）。

**用法**

- 基本调用

```python
pro.hkstock_realtime(symbol='00700')
```

- 参数别名（`ks_code` / `symbols` / `tradedate` / `q` 等）

```python
pro.hkstock_realtime(ks_code='HK00700')
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hkstock_realtime(symbol='00700', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hkstock_realtime(symbol='00700', as_dataframe=False)
```

**数据样例**

暂无可用样例：无样例

### `hkstock_trend`

- **路径：** `/v1/hkstock/trend`
- **类型：** http
- **说明：** 港股分时
- **签名：** `pro.hkstock_trend(symbol=None, *, ks_code=None, date=None, day=None, **opts)`
- **介绍：** 港股分时 `GET /v1/hkstock/trend`；可选 `day=1|5`。

**用法**

- 基本调用

```python
pro.hkstock_trend(symbol='00700.HK')
```

**进阶用法**

- 进阶参数组合

```python
pro.hkstock_trend(symbol='00700.HK', day=5)
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hkstock_trend(symbol='00700.HK', raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hkstock_trend(symbol='00700.HK', as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.hkstock_trend(ks_code='sh600519')
```

- 指定交易日

```python
pro.hkstock_trend(symbol='00700.HK', date='20250102')
```

**数据样例**

暂无可用样例：无样例

### `hkstock_kline`

- **路径：** `/v2/hkstock/kline`
- **类型：** http
- **说明：** 港股K线
- **签名：** `pro.hkstock_kline(symbol=None, *, ks_code=None, period=None, adjust_type=None, count=None, timestamp=None, **opts)`
- **介绍：** 港股 K 线 `GET /v2/hkstock/kline`。暂仅 `adjust_type=none`；`count`≤1800。

**用法**

- 基本调用

```python
pro.hkstock_kline(
    symbol='00700.HK', period=86400, count=2, adjust_type='none',
)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.hkstock_kline(
    symbol='00700.HK', period=86400, count=2, adjust_type='none',, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.hkstock_kline(
    symbol='00700.HK', period=86400, count=2, adjust_type='none',, as_dataframe=False)
```

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
pro.hkstock_kline(
    ks_code='sh600519', period=86400, count=2, adjust_type='none',
)
```

- 翻页游标（请求参数为秒）

```python
pro.hkstock_kline(
    symbol='00700.HK', period=86400, count=2, adjust_type='none',, timestamp=1700000000)
```

**数据样例**

暂无可用样例：无样例

### `plate_realtime`

- **路径：** `/v1/plate/realtime`
- **类型：** http
- **说明：** 板块实时
- **签名：** `pro.plate_realtime(plate_id=None, **opts)`

**用法**

- 基本调用

```python
pro.plate_realtime(plate_id=38053809)
```

**进阶用法**

- 进阶参数组合

```python
pro.plate_realtime(plate_id=[38053809, 1])
```

- 返回完整 JSON 信封（`raw=True`）

```python
pro.plate_realtime(plate_id=38053809, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.plate_realtime(plate_id=38053809, as_dataframe=False)
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `limit_up_count` | `name` | `plate_id` | `rank` | `rise_count` | `stay_count` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.021241 | 2 | -8.45347e+06 | 0 | 黄酒 | 38053809 | 0 | 2 | 0 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.021241 |
| `fall_count` | 下跌家数 | 2 |
| `fund_flow` | 资金流向 | -8.45347e+06 |
| `limit_up_count` | 涨停家数 | 0 |
| `name` | 名称 | 黄酒 |
| `plate_id` | 板块编号 | 38053809 |
| `rank` | 排名 | 0 |
| `rise_count` | 上涨家数 | 2 |
| `stay_count` | 封板维持次数 | 0 |

### `plate_trend`

- **路径：** `/v1/plate/trend`
- **类型：** http
- **说明：** 板块分时
- **签名：** `pro.plate_trend(plate_id, *, date=None, **opts)`

**用法**

- 基本调用

```python
pro.plate_trend(38053809)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.plate_trend(38053809, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.plate_trend(38053809, as_dataframe=False)
```

- 指定交易日

```python
pro.plate_trend(38053809, date='20250102')
```

**数据样例**

| 字段 | 值 |
|------|-----|
| `date` | 20260923 |
| `plate_id` | 38053809 |
| `pre_close` | 1527.6 |
| `total` | 246 |

**`data` 展开（20 条）**

| `change_percent` | `price` | `timestamp` |
| --- | --- | --- |
| 0.000446 | 1528.28 | 1790126700000 |
| 0.000446 | 1528.28 | 1790126760000 |
| 0.000446 | 1528.28 | 1790126820000 |
| 0.000446 | 1528.28 | 1790126880000 |
| 0.000446 | 1528.28 | 1790126940000 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `data` | 业务数据（可展开） | [20 项，见下方展开] |
| `date` | 交易日 | 20260923 |
| `plate_id` | 板块编号 | 38053809 |
| `pre_close` | 昨收 | 1527.6 |
| `total` | 总数 | 246 |
| `data.change_percent` | 业务数据（可展开） → 涨跌幅（%） | 0.000446 |
| `data.price` | 业务数据（可展开） → 最新价 | 1528.28 |
| `data.timestamp` | 业务数据（可展开） → 时间戳（毫秒） | 1790126700000 |

### `plate_kline`

- **路径：** `/v2/plate/kline`
- **类型：** http
- **说明：** 板块K线
- **签名：** `pro.plate_kline(plate_id, *, period=None, count=None, timestamp=None, **opts)`

**用法**

- 基本调用

```python
pro.plate_kline(38053809, period=86400, count=2)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.plate_kline(38053809, period=86400, count=2, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.plate_kline(38053809, period=86400, count=2, as_dataframe=False)
```

- 翻页游标（请求参数为秒）

```python
pro.plate_kline(38053809, period=86400, count=2, timestamp=1700000000)
```

**数据样例**

| `symbol` | `date` | `timestamp` | `open` | `high` | `low` | `close` | `volume` | `amount` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 38053809 | 20260922 | 1790035200000 | 1513.39 | 1595 | 1508.96 | 1527.6 | 0 | 0 |
| 38053809 | 20260923 | 1790121600000 | 1528.21 | 1680.36 | 1528.21 | 1559.99 | 0 | 0 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `symbol` | 标的代码 | 38053809 |
| `date` | 交易日 | 20260922 |
| `timestamp` | 时间戳（毫秒） | 1790035200000 |
| `open` | 开盘价 | 1513.39 |
| `high` | 最高价 | 1595 |
| `low` | 最低价 | 1508.96 |
| `close` | 收盘价 / 最新价 | 1527.6 |
| `volume` | 成交量 | 0 |
| `amount` | 成交额 | 0 |

### `plate_moneyflow`

- **路径：** `/v1/plate/moneyflow`
- **类型：** http
- **说明：** 板块资金流
- **签名：** `pro.plate_moneyflow(plate_id, **opts)`

**用法**

- 基本调用

```python
pro.plate_moneyflow(38053809)
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.plate_moneyflow(38053809, raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.plate_moneyflow(38053809, as_dataframe=False)
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `limit_up_count` | `name` | `plate_id` | `rank` | `rise_count` | `stay_count` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.021241 | 2 | -8.45347e+06 | 0 | 黄酒 | 38053809 | 0 | 2 | 0 |

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.021241 |
| `fall_count` | 下跌家数 | 2 |
| `fund_flow` | 资金流向 | -8.45347e+06 |
| `limit_up_count` | 涨停家数 | 0 |
| `name` | 名称 | 黄酒 |
| `plate_id` | 板块编号 | 38053809 |
| `rank` | 排名 | 0 |
| `rise_count` | 上涨家数 | 2 |
| `stay_count` | 封板维持次数 | 0 |

### `plate_moneyflow_ranking`

- **路径：** `/v1/plate/moneyflow/ranking`
- **类型：** http
- **说明：** 板块资金榜
- **签名：** `pro.plate_moneyflow_ranking(**opts)`

**用法**

- 基本调用

```python
pro.plate_moneyflow_ranking()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.plate_moneyflow_ranking(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.plate_moneyflow_ranking(as_dataframe=False)
```

**数据样例**

| `change_percent` | `fall_count` | `fund_flow` | `limit_up_count` | `name` | `plate_id` | `rise_count` |
| --- | --- | --- | --- | --- | --- | --- |
| 0.011859 | 144 | 9.33807e+09 | 4 | 半导体 | 16844702 | 231 |
| 0.019055 | 33 | 6.69502e+09 | 4 | PCB板 | 19426649 | 85 |
| 0.007731 | 154 | 4.35913e+09 | 3 | 国产芯片 | 31765737 | 156 |
| 0.011161 | 15 | 3.72421e+09 | 0 | 中芯国际概念股 | 65767826 | 37 |
| -0.002718 | 247 | 3.11993e+09 | 1 | 医药 | 25638417 | 121 |

（共 20 行，表中展示前 5 行）

**字段说明**

| 字段 | 含义 | 样例值 |
|------|------|--------|
| `change_percent` | 涨跌幅（%） | 0.011859 |
| `fall_count` | 下跌家数 | 144 |
| `fund_flow` | 资金流向 | 9.33807e+09 |
| `limit_up_count` | 涨停家数 | 4 |
| `name` | 名称 | 半导体 |
| `plate_id` | 板块编号 | 16844702 |
| `rise_count` | 上涨家数 | 231 |

## WebSocket / Level2

### `realtime_ws_url`

- **路径：** `/v1/realtime/ws`
- **类型：** ws
- **说明：** 逐笔行情连接地址（仅生成地址）
- **签名：** `pro.realtime_ws_url(symbol=None, *, ks_code=None)`

**用法**

- realtime_ws_url

```python
pro.realtime_ws_url(symbol='600519.SS')
```

- ks_code

```python
pro.realtime_ws_url(ks_code='600519.SH')
```

**数据样例**

暂无可用样例：无样例

### `futures_ws_url`

- **路径：** `/v1/futures/ws`
- **类型：** ws
- **说明：** 期货行情连接地址（仅生成地址）
- **签名：** `pro.futures_ws_url(**query)`

**用法**

- futures_ws_url

```python
pro.futures_ws_url()
```

**数据样例**

暂无可用样例：无样例

### `futures_v2_ws_url`

- **路径：** `/v1/futures-v2/ws`
- **类型：** ws
- **说明：** 期货二代行情连接地址（仅生成地址）
- **签名：** `pro.futures_v2_ws_url(**query)`

**用法**

- futures_v2_ws_url

```python
pro.futures_v2_ws_url()
```

**数据样例**

暂无可用样例：无样例

### `realtime_ws`

- **路径：** `/v1/realtime/ws`
- **类型：** ws
- **说明：** 逐笔行情订阅
- **签名：** `pro.realtime_ws(symbol=None, *, ks_code=None, timeout=None)`
- **介绍：** 沪深京个股 Tick WebSocket `/v1/realtime/ws`。

**用法**

- recv one

```python
_ws_one(pro.realtime_ws(symbol='600519.SS', timeout=10))
```

**进阶用法**

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
_ws_one(pro.realtime_ws(ks_code='sh600519', timeout=10))
```

**数据样例**

暂无可用样例：无样例

### `futures_ws`

- **路径：** `/v1/futures/ws`
- **类型：** ws
- **说明：** 期货行情订阅
- **签名：** `pro.futures_ws(symbol=None, *, exchange=None, timeout=None, **query)`
- **介绍：** 国内期货 WebSocket `/v1/futures/ws`。

**用法**

- futures_ws

```python
_ws_one(pro.futures_ws(symbol='rb2501', timeout=10))
```

**数据样例**

暂无可用样例：无样例

### `futures_v2_ws`

- **路径：** `/v1/futures-v2/ws`
- **类型：** ws
- **说明：** 期货二代行情订阅
- **签名：** `pro.futures_v2_ws(symbol=None, *, exchange=None, timeout=None, **query)`
- **介绍：** 国内期货 V2 WebSocket `/v1/futures-v2/ws`。

**用法**

- futures_v2_ws

```python
_ws_one(pro.futures_v2_ws(symbol='rb2501', timeout=10))
```

**数据样例**

暂无可用样例：无样例

### `level2`

- **路径：** `pro.level2`
- **类型：** local
- **说明：** Level2 行情（depth / orders / trades / entrust）
- **签名：** `pro.level2(symbol=None, *, ks_code=None, channels=None, binary=None, bind=None, dump='none', run_for=None, download=True)`
- **介绍：** Level2 行情订阅。

**用法**

- depth+trades+entrust

```python
_l2_one(p)
```

**进阶用法**

- 用 `ks_code` 传标的（与 `symbol` 等价，只向上游发 `symbol`）

```python
_l2_one(p, ks_code='sh600519')
```

- Level2 频道（含逐笔委托）

```python
_l2_one(p, channels='depth,trades,entrust')
```

**数据样例**

暂无可用样例：无样例

## Client 核心

### `refresh_limits`

- **路径：** `/v1/me`
- **类型：** helper
- **说明：** 刷新限额缓存
- **签名：** `pro.refresh_limits()`
- **介绍：** Force `GET /v1/me` and replace the cached snapshot.

**用法**

- refresh_limits

```python
pro.refresh_limits()
```

**进阶用法**

- 返回完整 JSON 信封（`raw=True`）

```python
pro.refresh_limits(raw=True)
```

- 返回 list / dict，不转 DataFrame

```python
pro.refresh_limits(as_dataframe=False)
```

**数据样例**

```text
LimitsSnapshot(raw={'account': {'discount_label': '限时特惠', 'discount_percent': 43, 'enabled': True, 'expires_at': '2026-10-21T00:30:23', 'name': 'l2-local', 'original_price': 699.0, 'original_price_dis
```

### `get_escape`

- **路径：** `/v1/health`
- **类型：** helper
- **说明：** 通用请求

**用法**

```python
pro.get_escape(...)
```

**数据样例**

暂无可用样例：无样例

