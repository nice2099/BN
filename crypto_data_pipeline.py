#!/usr/bin/env python3
"""轻量级加密数据采集 + 标准化 + Excel 导出脚本。

数据源：
- Binance 24hr ticker（价格、成交量）
- CoinGecko markets（市值）
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

BINANCE_24HR_URL = "https://api.binance.com/api/v3/ticker/24hr"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
USD_MILLION = 1_000_000


@dataclass
class AppConfig:
    out_file: str
    vs_currency: str
    quote_asset: str
    fields: list[str]
    min_volume_usdt: float
    top_n: int | None
    timeout_seconds: int


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    return AppConfig(
        out_file=raw.get("out_file", "crypto.xlsx"),
        vs_currency=raw.get("vs_currency", "usd"),
        quote_asset=raw.get("quote_asset", "USDT"),
        fields=raw.get(
            "fields",
            ["symbol", "price", "volume_24h_musd", "market_cap_musd", "timestamp"],
        ),
        min_volume_usdt=float(raw.get("filters", {}).get("min_volume_usdt", 0)),
        top_n=raw.get("filters", {}).get("top_n"),
        timeout_seconds=int(raw.get("timeout_seconds", 10)),
    )


def get_binance_tickers(timeout_seconds: int) -> list[dict[str, Any]]:
    resp = requests.get(BINANCE_24HR_URL, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError("Binance 返回格式异常，应为 list")
    return data


def get_coingecko_market_caps(vs_currency: str, timeout_seconds: int) -> dict[str, float]:
    symbol_to_market_cap: dict[str, float] = {}

    for page in range(1, 5):
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": 250,
            "page": page,
            "sparkline": "false",
        }
        resp = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=timeout_seconds)
        resp.raise_for_status()

        batch = resp.json()
        if not batch:
            break

        for coin in batch:
            symbol = str(coin.get("symbol", "")).upper()
            market_cap = coin.get("market_cap")
            if not symbol or market_cap is None:
                continue
            # 同 symbol 可能对应多个币，这里保留更大市值项。
            symbol_to_market_cap[symbol] = max(float(market_cap), symbol_to_market_cap.get(symbol, 0.0))

        # 轻微限速，避免触发公共 API 频率限制。
        time.sleep(0.2)

    return symbol_to_market_cap


def normalize_rows(
    tickers: list[dict[str, Any]],
    market_cap_map: dict[str, float],
    quote_asset: str,
    min_volume_usdt: float,
) -> list[dict[str, Any]]:
    now_ts = int(time.time())
    rows: list[dict[str, Any]] = []

    for t in tickers:
        symbol = str(t.get("symbol", ""))
        if not symbol.endswith(quote_asset):
            continue

        base_symbol = symbol[: -len(quote_asset)]
        quote_volume = float(t.get("quoteVolume", 0) or 0)
        if quote_volume < min_volume_usdt:
            continue

        rows.append(
            {
                "symbol": symbol,
                "price": float(t.get("lastPrice", 0) or 0),
                "volume_24h_musd": quote_volume / USD_MILLION,
                "market_cap": market_cap_map.get(base_symbol.upper()),
                "timestamp": now_ts,
            }
        )

        if rows[-1]["market_cap"] is not None:
            rows[-1]["market_cap_musd"] = rows[-1]["market_cap"] / USD_MILLION
        else:
            rows[-1]["market_cap_musd"] = None

    return rows


def export_excel(rows: list[dict[str, Any]], fields: list[str], out_file: str, top_n: int | None) -> None:
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=fields)
    else:
        df = df[fields]
        sort_field = "volume_24h_musd" if "volume_24h_musd" in df.columns else "volume_24h"
        df = df.sort_values(by=sort_field, ascending=False)
        if top_n:
            df = df.head(top_n)

    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_file, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="采集 Binance + CoinGecko，并导出 Excel")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))

    tickers = get_binance_tickers(timeout_seconds=cfg.timeout_seconds)
    market_cap_map = get_coingecko_market_caps(vs_currency=cfg.vs_currency, timeout_seconds=cfg.timeout_seconds)
    rows = normalize_rows(
        tickers=tickers,
        market_cap_map=market_cap_map,
        quote_asset=cfg.quote_asset,
        min_volume_usdt=cfg.min_volume_usdt,
    )
    export_excel(rows, cfg.fields, cfg.out_file, cfg.top_n)

    print(f"导出完成：{cfg.out_file}，记录数：{len(rows)}")


if __name__ == "__main__":
    main()
