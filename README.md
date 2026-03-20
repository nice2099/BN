## Crypto 数据采集 + Excel 导出

一个可直接运行的轻量脚本：
- Binance：价格与 24h 成交额
- CoinGecko：市值
- 标准化后导出为 Excel

### 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python crypto_data_pipeline.py --config config.yaml
```

输出文件默认在 `output/crypto.xlsx`。

你可以在配置文件中通过 `amount_unit_divisor` 配置市值与成交额的单位换算系数，默认值是 `1000000`（百万）。

### 数据标准化字段

> `volume_24h_musd` 与 `market_cap_musd` 默认单位均为 **百万美元（M USD）**，可通过 `amount_unit_divisor` 调整。

```json
{
  "symbol": "BTCUSDT",
  "price": 65000,
  "volume_24h_musd": 1000,
  "market_cap_musd": 1200000,
  "timestamp": 1710000000
}
```

### 调度建议

- 每 1 分钟：价格与成交额（Binance）
- 每 1 小时：市值（CoinGecko）

可先用 cron / Airflow / APScheduler 接入。
