# KlineShare Python SDK

官方 Python 客户端，调用 [KlineShare](https://klineshare.cn) 行情 API：实时 / 分时 / K 线、涨停与资金流、债券与扩展市场、推流与 Level2。

## 安装

```bash
pip install klineshare
pip install "klineshare[pandas]"   # 结果转 DataFrame（推荐）
pip install "klineshare[ws]"       # WebSocket
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

也可用环境变量（不必再 `set_api_key`）：

```bash
export KLINESHARE_API_KEY=tg_your_key
# 可选：入口地址（默认 https://data.klineshare.cn）
# export KLINESHARE_BASE_URL=https://data.klineshare.cn
```

```python
pro = ks.pro_api()
```

查看当前 Key 的权限与限额：

```python
print(pro.me())
print(pro.limits.summary())
```

## 常用示例

### K 线 / 实时

```python
bars = pro.kline(symbol="600519.SS", period=86400, count=100)
quote = pro.realtime(symbol="600519.SS")
trend = pro.trend(symbol="600519.SS")
```

### 全市场快照

```python
quotes = pro.realtime_v2(all=True, market="SS")
auction = pro.auction_v2(all=True, market="SS")
mk = pro.market_kline_v2(all=True, market="SS", period=60, count=2)
moneyflow = pro.moneyflow_live(all=True)
```

### 返回形态

默认解包接口里的 `data`；列表尽量转成 pandas DataFrame。

```python
rows = pro.kline(symbol="600519.SS", period=86400, count=10, as_dataframe=False)
envelope = pro.kline(symbol="600519.SS", period=86400, count=10, raw=True)
```

### 翻页

请求参数 `timestamp` 为**秒**。可直接用上一页最早一根的毫秒 `timestamp`（SDK 会自动换算）：

```python
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

标准后缀：`600519.SS` / `000001.SZ` / `920000.BJ` / `AAPL.US` / `00700.HK`。

| 输入 | 发出请求时 |
|------|------------|
| `600519.SH` | `600519.SS` |
| `sh600519` | `600519.SS` |
| `600519` | `600519.SS`（按首位推断） |
| `ks_code=` | 与 `symbol=` 相同规则 |

请按资产选对应方法：个股 `kline`，指数 `index_kline`，ETF `etf_kline`，北交所 `bj_kline` 等。

## 限额说明

SDK 默认 `limits="enforce"`：按 `pro.me()` 的套餐在本地裁切 `count`、校验标的数，并做简单的每分钟请求节流，减少无效调用与 429。调试可设 `limits="off"`。

若账号分配了专属入口，响应中的 `api_base` 会被自动跟随（可用 `pro.api_base` 查看）。

## 更多文档

- **完整用法与全接口参考：** [docs/API_USAGE.md](docs/API_USAGE.md)
- API 契约：https://data.klineshare.cn （或 `pro.docs_md()` / `pro.llms_full_txt()`）
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

## License

MIT
