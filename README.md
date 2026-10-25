# KlineShare Python SDK

官方 Python SDK，调用 [KlineShare](https://klineshare.cn) 行情 API（实时、分时、K 线、涨停专题、资金流向等）。

## 安装

```bash
pip install -e .
# 可选：结果直接转成 DataFrame
pip install -e ".[pandas]"
```

发布到 PyPI 后：

```bash
pip install klineshare
pip install klineshare[pandas]
```

## 快速开始

在用户中心创建 API Key（形如 `tg_...`），然后：

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

也可用环境变量（不必 `set_api_key`）：

- `KLINESHARE_API_KEY`
- `KLINESHARE_BASE_URL`（默认 `https://data.klineshare.cn`，用作入口；有分配节点时会被 `api_base` 覆盖）

```python
pro = ks.pro_api()  # 从环境变量读 API Key
pro = ks.Client(api_key="tg_xxx", base_url="https://data.klineshare.cn")
```

默认开启客户端限额（`limits="enforce"`）：首次业务请求前会 `GET /v1/me`，按套餐裁切 `count`、拒绝超额 symbol / 试用耗尽，并做本地 RPM 门闩。若响应含 `api_base`（账号分配的请求根地址），SDK **自动切到该地址**（`follow_api_base=True`，可用 `pro.api_base` 查看）。

错节点 / 会话中途换节点：

| 场景 | SDK 行为 |
|------|----------|
| HTTP / SSE **建连** | `403` + `api_base` → 切入口并重试一次 |
| WS **建连** | 首帧 `type=error` 且 `message` 含 `api_base=` → 切入口并重连一次 |
| Level2 **新建** | 建连前先同步 `/v1/me` 的 `api_base` |
| 已建立的 SSE / WS / Level2 **推流中** | **不会**中途热切换；连接断开或收不到数据后需业务侧重开 |

调试可 `limits="off"` / `follow_api_base=False`；只裁切并记录建议用 `limits="advise"`（见 `pro.limit_advice`）。详见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

```python
pro = ks.pro_api(limits="enforce", on_rate_limit="wait", kline_batch="auto")
pro.refresh_limits()
print(pro.limits.summary())  # max_count / RPM / max_realtime_symbols …
# 日线多标的且 n×count 过大时，客户端可按标的拆请求（默认阈值 3000，可调）
bars = pro.kline(symbol=["600519.SS", "000001.SZ", "000002.SZ"], period=86400, count=1500, batch="auto")
```

## 标的代码

KlineShare 标准后缀：`600519.SS` / `000001.SZ` / `920000.BJ` / `AAPL.US` / `00700.HK`。

SDK 会自动规范化常见写法：

| 输入 | 发出请求时 |
|------|------------|
| `600519.SH` | `600519.SS` |
| `sh600519` | `600519.SS` |
| `600519` | `600519.SS`（按首位推断） |
| `00700.HK` / `hk00700` / `700`（`hkstock_*`） | `00700.HK` |
| `ks_code=` 参数 | 与 `symbol=` 相同规则 |

个股 / ETF / 指数 / 北交所 / 债券请走对应方法（与 HTTP 路径一致），例如指数用 `index_kline`，ETF 用 `etf_kline`。

## 常用方法

方法名贴近 REST 路径：

- 行情：`realtime` / `trend` / `kline`（**仅** `/v2/kline`）/ `adjust_params`（推荐）/ `exrights` / `adjust_factors`（不建议）/ `auction` / `auction_v2`
- 北交所：`bj_trend` / `bj_kline`
- 指数：`index_realtime` / `index_trend` / `index_kline`（`/v2/index/kline`）
- ETF：`etf` / `etf_realtime` / `etf_trend` / `etf_kline`（`/v2/etf/kline`）
- 扩展：`metal_*` / `futures*` / `global_index_*` / `global_bond_*` / `usstock_*` / `hkstock_*` / `plate_*`
- 债券：`bond*`（兼容）/ `convertible*` / `treasury*` / `enterprise*`
- 资料：`stock` / `stocks` / `corp` / `finance_report` / `calendar` / `suspend*` / `zfpg*` / `yjfp*`
- 专题：`limit_up*` / `abnormal_events*` / `market_flash_stream` / `lhb_*` / `hot_money*` / `moneyflow_*`
- 目录：`catalog_*`
- 全市场 compact（**主用法 `all=True`**，不是单票）：`realtime_v2` / `auction_v2` / `market_kline_v2` / `convertible_auction_v2`
- 实时个股资金流：`moneyflow_live(all=True)` 或批量 `symbol`（最多 200 只）

```python
# 沪市全市场实时 / 集合竞价 / 近端分钟 K / 实时个股资金流
quotes = pro.realtime_v2(all=True, market="SS")
auction = pro.auction_v2(all=True, market="SS")
mk = pro.market_kline_v2(all=True, market="SS", period=60, count=2)
moneyflow = pro.moneyflow_live(all=True)
```
- 公开元数据：`public_catalog` / `public_indices` / `public_metals` / `public_futures` / `public_futures_v2` / `public_global_indices` / `public_global_bonds` / `public_usstocks` / `*_schema` / `docs_md` / `llms_txt` / `llms_full_txt`
- 通用：`get(path, ...)` / `stream(path, ...)`
- WebSocket（可选依赖）：`realtime_ws` / `futures_ws` / `futures_v2_ws`；也可用 `*_ws_url`
- Level2：`pro.level2(...)`；通道 `depth` / `orders` / `trades` / `entrust`

**不封装**已过时的 ``/v1/kline``、``/v1/index/kline``、``/v1/etf/kline``。

安装 WebSocket 支持：

```bash
pip install "klineshare[ws]"
```

```python
with pro.realtime_ws(symbol="600519.SS") as feed:
    for msg in feed:
        if msg.get("type") == "tick":
            print(msg)
            break
    # 动态订阅
    # feed.sub(symbols=["000001.SZ"], snapshot=True)
```

Level2：

```python
with pro.level2(symbol="600519.SS", channels="depth,trades,entrust") as feed:
    for msg in feed:
        # msg["type"] in ("depth", "orders", "trades", "entrust", ...)
        print(msg)
        break
```

默认返回接口里的 `data`；列表会尽量转成 pandas DataFrame。需要完整 JSON 信封时传 `raw=True`；强制不要 DataFrame 时传 `as_dataframe=False`。

K 线翻页：`timestamp` 参数为**秒**。条内字段 `timestamp` 是毫秒；SDK 若检测到传入毫秒会自动换成秒，可直接用上一页最早一根的 `timestamp` 继续往前翻。

大包默认走 `format=raw`（服务端极限体积分隔串；SDK 仍展开为行 / DataFrame）。传 `format=None` 可改回服务端列式数组。这与 `raw=True`（返回完整 JSON 信封）不同。

```python
bars = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)
envelope = pro.kline(symbol="600519.SS", period=86400, count=10, raw=True)
# 往更早翻页（手动）
older = pro.kline(
    symbol="600519.SS",
    period=86400,
    count=10,
    timestamp=min(b["timestamp"] for b in bars) - 1,
)
# 或自动翻页（每页仍走限额管线）
for page in pro.iter_kline(symbol="600519.SS", period=86400, count=10, max_pages=5):
    print(len(page))
```

资金流板块榜需传 `category`（如 `industry` / `concept` / `csrc_industry`，见 `moneyflow_ranking_catalog()`）。  
实时分页榜：`moneyflow_ranking_live_stocks(offset=0, limit=50, sort="net")`（目录见 `moneyflow_ranking_live_catalog()`）。  
实时按码 / 全市场：`moneyflow_live(symbol="600519.SS")` 或 `moneyflow_live(all=True)`（目录见 `moneyflow_live_catalog()`）。

## 文档

- **使用说明 + 全接口参考（用法 / 进阶用法）：** [docs/API_USAGE.md](docs/API_USAGE.md)
- 接口说明：`https://data.klineshare.cn` 文档站 / `GET /public/v1/llms-full.txt`
- 权限与限额：`pro.me()`

## 开发

维护者约定见 **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**（非终端用户文档）；发布步骤见 **[docs/RELEASE.md](docs/RELEASE.md)**；变更见 **[CHANGELOG.md](CHANGELOG.md)**。

```bash
pip install -e ".[dev]"
pytest
python scripts/check_endpoint_coverage.py --check-gzip
python scripts/gen_api_usage_doc.py          # 在线拉样例并刷新 docs/API_USAGE.md
python scripts/gen_api_usage_doc.py --offline  # 仅用缓存样例
python scripts/gen_api_usage_doc.py --strict   # 必选接口样例失败则非 0 退出
# 真实 Key 冒烟（读环境变量 KLINESHARE_API_KEY）
python scripts/live_smoke.py --quick         # 核心面
python scripts/live_smoke.py                 # 矩阵全量 HTTP
python scripts/live_smoke.py --ws --sse --level2
```

## License

MIT
