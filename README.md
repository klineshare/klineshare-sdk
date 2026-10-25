# KlineShare Python SDK

官方 Python 客户端，对接 [KlineShare](https://klineshare.cn) **A 股 / 北交所 / 指数 / ETF / 可转债 / 债券 / 期货 / 贵金属 / 美股 / 港股** 行情数据 API。

覆盖：**实时行情、分时、多周期 K 线、集合竞价、全市场 compact 快照、涨停跌停、龙虎榜、游资、资金流向、停复牌、财务与公司资料、板块目录、WebSocket Tick、Level2 十档/逐笔** 等。适合量化研究、行情监控、选股看板与数据中台接入。

完整参数与样例见 [docs/API_USAGE.md](docs/API_USAGE.md)。

## 安装

```bash
pip install klineshare
pip install "klineshare[pandas]"   # 结果转 DataFrame（推荐）
pip install "klineshare[ws]"       # WebSocket Tick
```

## 快速开始

在 [用户中心](https://klineshare.cn) 创建 API Key（形如 `tg_...`）：

```python
import klineshare as ks

ks.set_api_key("tg_your_key")
pro = ks.pro_api()

# .SH 会自动规范为接口使用的 .SS
df = pro.kline(symbol="600519.SH", period=86400, adjust_type="forward", count=100)
quote = pro.realtime(symbol="600519.SH")
print(df)
print(quote)
```

也可用环境变量：

```bash
export KLINESHARE_API_KEY=tg_your_key
# 可选：export KLINESHARE_BASE_URL=https://data.klineshare.cn
```

```python
pro = ks.pro_api()
print(pro.me())              # 当前 Key 权限与限额
print(pro.limits.summary())
```

## 能力概览

| 能力域 | 能做什么 |
|--------|----------|
| **A 股行情** | 个股实时、分时、K 线、复权参数；沪深全市场 `realtime_v2` / `auction_v2` / `market_kline_v2` |
| **指数 / ETF** | 指数与基金实时、分时、K 线、资料检索 |
| **北交所** | 北交所分时、K 线（实时也可走通用 `realtime`） |
| **债券 / 可转债** | 国债、企业债、可转债查询与行情；可转债集合竞价与全市场 compact |
| **专题数据** | 涨停/破板/跌停池、连板天梯、异动与快讯、龙虎榜、游资、个股与板块资金流 |
| **扩展市场** | 贵金属、期货（含 SSE/WS）、全球指数与债券、美股、港股、A 股板块行情 |
| **目录与资料** | 股票/公司/财务、停复牌、增发配股、业绩分配、板块与指数成分目录 |
| **推流** | WebSocket Tick、期货推流、Level2（depth / orders / trades / entrust） |

---

## 接口与能力清单

方法名贴近 REST 路径。下表为 SDK 公开能力索引（SEO / 检索用）；调用细节见 [API_USAGE.md](docs/API_USAGE.md)。

### 账号与健康

| 方法 | 能力 | 路径 |
|------|------|------|
| `health` | 服务健康检查 | `/v1/health` |
| `me` | 当前密钥权限与限额 | `/v1/me` |
| `refresh_limits` | 刷新限额缓存 | `/v1/me` |

### A 股行情与资料

| 方法 | 能力 | 路径 |
|------|------|------|
| `realtime` | 个股实时行情（可批量，含北交所） | `/v1/realtime` |
| `realtime_v2` | 全市场紧凑实时（`all=True`） | `/v2/realtime` |
| `auction` | 集合竞价分时 | `/v1/auction` |
| `auction_v2` | 全市场集合竞价 compact | `/v2/auction` |
| `market_kline_v2` | 全市场近端分钟 K compact | `/v2/market-kline` |
| `trend` | 个股分时走势 | `/v1/trend` |
| `kline` / `iter_kline` | 个股多周期 K 线 / 向更早翻页 | `/v2/kline` |
| `adjust_params` | 复权参数序列（推荐） | `/v1/adjust-params` |
| `exrights` | 除权除息 | `/v1/exrights` |
| `adjust_factors` | 复权因子 | `/v1/adjust-factors` |
| `stock` / `stocks` | 个股资料 / 股票列表搜索 | `/v1/stock` · `/v1/stocks` |
| `corp` | 上市公司资料 | `/v1/corp` |
| `finance_report` | 财务报表 | `/v1/finance/report` |
| `calendar` | 交易日历 | `/v1/calendar` |

### 北交所 · 指数 · ETF

| 方法 | 能力 | 路径 |
|------|------|------|
| `bj_trend` / `bj_kline` | 北交所分时 / K 线 | `/v1/bj/trend` · `/v1/bj/kline` |
| `index_realtime` / `index_trend` / `index_kline` | 指数实时 / 分时 / K 线 | `/v1/index/*` · `/v2/index/kline` |
| `etf` / `etfs` | 基金资料 / 列表 | `/v1/etf` · `/v1/etfs` |
| `etf_realtime` / `etf_trend` / `etf_kline` | 基金实时 / 分时 / K 线 | `/v1/etf/*` · `/v2/etf/kline` |

### 债券 · 可转债 · 国债 · 企业债

每类均提供：查询、档案、列表、板块、成分、实时、分时、K 线。

| 前缀 | 代表方法 | 路径前缀 |
|------|----------|----------|
| 普通债券 | `bond` · `bonds` · `bond_realtime` · `bond_trend` · `bond_kline` · `bond_boards*` | `/v1/bond*` |
| 可转债 | `convertible*` · `convertible_auction` · `convertible_auction_v2` · `convertible_kline` | `/v1/convertible*` · `/v2/convertible/*` |
| 国债 | `treasury*` · `treasuries` · `treasury_realtime` · `treasury_kline` | `/v1/treasury*` |
| 企业债 | `enterprise*` · `enterprises` · `enterprise_realtime` · `enterprise_kline` | `/v1/enterprise*` |

### 涨停 · 异动 · 龙虎榜 · 游资

| 方法 | 能力 | 路径 |
|------|------|------|
| `limit_up` | 涨停池 | `/v1/limit-up` |
| `limit_up_break` | 破板池 | `/v1/limit-up/break` |
| `limit_down` | 跌停池 | `/v1/limit-up/limit-down` |
| `yesterday_limit_up` | 昨日涨停 | `/v1/limit-up/yesterday` |
| `limit_up_ladder` | 连板天梯 | `/v1/limit-up/ladder` |
| `limit_up_plates_trending` / `_industry` / `_concept` / `_style` | 涨停板块热度 | `/v1/limit-up/plates/*` |
| `abnormal_events` / `abnormal_events_stream` | 异动事件 / SSE 推流 | `/v1/abnormal-events*` |
| `market_flash_stream` | 行情快讯 SSE | `/v1/market-flash/stream` |
| `lhb` / `lhb_daily` / `lhb_stock` / `lhb_dates` / `lhb_stats` | 龙虎榜查询与统计 | `/v1/lhb*` |
| `hot_money` / `hot_money_seat` / `hot_money_detail` / `hot_money_stats` | 游资名录与席位 | `/v1/hot-money*` |

### 资金流向

| 方法 | 能力 | 路径 |
|------|------|------|
| `moneyflow_live` | 实时个股资金流（单票 / 批量 / `all=True` 全市场） | `/v1/moneyflow/live` |
| `moneyflow_daily_trend` / `moneyflow_stage` / `moneyflow_distribution` | 日趋势 / 阶段 / 分布 | `/v1/moneyflow/*` |
| `moneyflow_ranking_boards` / `_stocks` / `_snapshot` | 板块与个股资金榜 | `/v1/moneyflow/ranking/*` |
| `moneyflow_ranking_stocks_net` / `_main` / `_retail` | 净流入 / 主力 / 散户榜 | `/v1/moneyflow/ranking/stocks/*` |
| `moneyflow_ranking_live_stocks` | 实时个股资金排名 | `/v1/moneyflow/ranking/live/stocks` |
| `plate_moneyflow` / `plate_moneyflow_ranking` | 板块资金流 / 榜单 | `/v1/plate/moneyflow*` |

### 停复牌 · 增发配股 · 业绩分配

| 方法 | 能力 | 路径 |
|------|------|------|
| `suspend` / `suspend_daily` / `suspend_dates` / `suspend_stock` | 停复牌 | `/v1/suspend*` |
| `zfpg` / `zfpg_daily` / `zfpg_stock` / `zfpg_tabs` | 增发配股 | `/v1/zfpg*` |
| `yjfp` / `yjfp_daily` / `yjfp_stock` / `yjfp_tabs` | 业绩分配 | `/v1/yjfp*` |

### 板块 · 目录

| 方法 | 能力 | 路径 |
|------|------|------|
| `plate_realtime` / `plate_trend` / `plate_kline` | 板块实时 / 分时 / K 线 | `/v1/plate/*` · `/v2/plate/kline` |
| `catalog_nodes` / `catalog_node` / `catalog_node_children` / `catalog_node_members` | 目录树与成分 | `/v1/catalog/nodes*` |
| `catalog_plates` / `catalog_plate_members` | 板块目录与成分 | `/v1/catalog/plates*` |
| `catalog_indices` / `catalog_index_members` | 指数目录与成分 | `/v1/catalog/indices*` |
| `catalog_stock` | 个股目录条目 | `/v1/catalog/stocks/{symbol}` |

### 贵金属 · 期货 · 全球 · 美股 · 港股

| 方法 | 能力 | 路径 |
|------|------|------|
| `metal_realtime` / `metal_kline` | 贵金属实时 / K 线 | `/v1/metal/realtime` · `/v2/metal/kline` |
| `metal_physical_brands` / `_products` / `_prices` | 实物金品牌 / 产品 / 报价 | `/v1/metal/physical/*` |
| `futures_realtime` / `futures_kline` / `futures_stream` | 期货实时 / K 线 / SSE | `/v1/futures*` · `/v2/futures/kline` |
| `futures_v2_realtime` / `_trend` / `_kline` / `_stream` | 期货二代行情与推流 | `/v1/futures-v2*` · `/v2/futures-v2/kline` |
| `global_index_realtime` / `_trend` / `_kline` | 全球指数 | `/v1/global-index*` · `/v2/global-index/kline` |
| `global_bond_realtime` / `_kline` | 国际债券 | `/v1/global-bond*` · `/v2/global-bond/kline` |
| `usstock_realtime` / `_trend` / `_kline` | 美股行情 | `/v1/usstock*` · `/v2/usstock/kline` |
| `hkstock_realtime` / `_trend` / `_kline` | 港股行情 | `/v1/hkstock*` · `/v2/hkstock/kline` |

### 公开元数据与文档

| 方法 | 能力 | 路径 |
|------|------|------|
| `public_catalog` | 套餐档位与 scope 目录 | `/public/v1/catalog` |
| `public_indices` / `public_metals` / `public_futures` / `public_futures_v2` | 指数 / 贵金属 / 期货公开清单 | `/public/v1/*` |
| `public_global_indices` / `public_global_bonds` / `public_usstocks` | 全球指数债券 / 美股清单 | `/public/v1/*` |
| `corp_schema` / `finance_schema` / `etf_schema` / `bond_schema` / `moneyflow_schema` | 字段结构说明 | `/public/v1/*/schema` |
| `moneyflow_ranking_catalog` / `moneyflow_ranking_live_catalog` / `moneyflow_live_catalog` | 资金流相关目录 | `/public/v1/moneyflow/*` |
| `docs_md` / `llms_txt` / `llms_full_txt` | 接口 Markdown / LLM 文档 | `/public/v1/docs.md` 等 |

### WebSocket · Level2 · 通用请求

| 方法 | 能力 | 路径 |
|------|------|------|
| `realtime_ws` / `realtime_ws_url` | A 股 Tick WebSocket | `/v1/realtime/ws` |
| `futures_ws` / `futures_v2_ws`（及对应 `*_url`） | 期货行情 WebSocket | `/v1/futures/ws` · `/v1/futures-v2/ws` |
| `level2` | Level2：depth / orders / trades / entrust | 经公开 `ks-live` 下发 |
| `get` / `stream` | 任意 REST / SSE 逃生舱 | 自定义 path |

---

## 常用示例

### K 线 / 实时 / 分时

```python
bars = pro.kline(symbol="600519.SS", period=86400, count=100)
quote = pro.realtime(symbol="600519.SS")
trend = pro.trend(symbol="600519.SS")
```

### 全市场 compact 快照

```python
quotes = pro.realtime_v2(all=True, market="SS")
auction = pro.auction_v2(all=True, market="SS")
mk = pro.market_kline_v2(all=True, market="SS", period=60, count=2)
moneyflow = pro.moneyflow_live(all=True)
```

### 返回形态与翻页

默认解包 `data`；列表尽量转 DataFrame。`raw=True` 返回完整 JSON 信封。

```python
rows = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)
envelope = pro.kline(symbol="600519.SS", period=86400, count=10, raw=True)

for page in pro.iter_kline(symbol="600519.SS", period=86400, count=100, max_pages=5):
    print(len(page))
```

### WebSocket / Level2

```bash
pip install "klineshare[ws]"
```

```python
with pro.realtime_ws(symbol="600519.SS") as feed:
    for msg in feed:
        if msg.get("type") == "tick":
            print(msg)
            break

with pro.level2(symbol="600519.SS", channels="depth,trades,entrust") as feed:
    for msg in feed:
        print(msg)
        break
```

## 标的代码

标准后缀：`600519.SS`（沪）/ `000001.SZ`（深）/ `920000.BJ`（北交所）/ `AAPL.US` / `00700.HK`。

| 输入 | 发出请求时 |
|------|------------|
| `600519.SH` | `600519.SS` |
| `sh600519` | `600519.SS` |
| `600519` | `600519.SS`（按首位推断） |
| `ks_code=` | 与 `symbol=` 相同规则 |

个股 / 指数 / ETF / 北交所 / 债券请走对应方法，例如指数用 `index_kline`，ETF 用 `etf_kline`。

## 限额说明

默认 `limits="enforce"`：按 `pro.me()` 套餐在本地裁切 `count`、校验标的数，并做每分钟请求节流，减少无效调用与 429。调试可 `limits="off"`。账号若分配了专属入口，会自动跟随响应中的 `api_base`。

## 更多文档

- **全接口用法与进阶样例：** [docs/API_USAGE.md](docs/API_USAGE.md)
- 在线 API 契约：https://data.klineshare.cn （或 `pro.docs_md()` / `pro.llms_full_txt()`）
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

## License

MIT
