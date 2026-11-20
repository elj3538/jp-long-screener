"""yfinanceから日本株（.T）の株価・財務・決算データを取得しキャッシュするモジュール。"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import certifi
import pandas as pd


def _ensure_ascii_ca_bundle() -> None:
    src = certifi.where()
    try:
        src.encode("ascii")
        return
    except UnicodeEncodeError:
        pass
    dst = Path(tempfile.gettempdir()) / "agy_cacert.pem"
    if not dst.exists() or dst.stat().st_size != Path(src).stat().st_size:
        shutil.copyfile(src, dst)
    os.environ["CURL_CA_BUNDLE"] = str(dst)
    os.environ["SSL_CERT_FILE"] = str(dst)


_ensure_ascii_ca_bundle()

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _extract_series(df: pd.DataFrame | None, candidates: list[str], limit: int = 5) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    row_name = next((name for name in candidates if name in df.index), None)
    if row_name is None:
        return []
    series = df.loc[row_name]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[0]
    cols = sorted(df.columns, key=lambda c: str(c), reverse=True)[:limit]
    result: list[dict[str, Any]] = []
    for col in cols:
        val = _safe_float(series.get(col))
        if val is not None:
            date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
            result.append({"date": date_str, "value": val})
    return result


def _calc_returns_and_technicals(hist: pd.DataFrame | None) -> dict[str, Any]:
    empty = {
        "latest_close": None,
        "latest_date": None,
        "returns": {"D": None, "W": None, "M": None, "3M": None, "6M": None, "9M": None, "Y": None},
        "rsi14": None,
        "macd": None,
        "yearly_prices": {},
        "price_series_weekly": [],
    }
    if hist is None or hist.empty or "Close" not in hist.columns:
        return empty
    close = hist["Close"].dropna()
    if close.empty:
        return empty

    latest_close = _safe_float(close.iloc[-1])
    latest_date = close.index[-1].strftime("%Y-%m-%d") if hasattr(close.index[-1], "strftime") else str(close.index[-1])[:10]

    offsets = {"D": 1, "W": 5, "M": 21, "3M": 63, "6M": 126, "9M": 189, "Y": 252}
    returns: dict[str, float | None] = {}
    n = len(close)
    for label, offset in offsets.items():
        if n > offset and latest_close is not None:
            prev = _safe_float(close.iloc[-1 - offset])
            returns[label] = round((latest_close / prev - 1.0) * 100.0, 2) if (prev and prev > 0) else None
        else:
            returns[label] = None

    rsi14 = None
    if n >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        lg, ll = _safe_float(gain.iloc[-1]), _safe_float(loss.iloc[-1])
        if lg is not None and ll is not None:
            rsi14 = 100.0 if ll == 0 else round(100.0 - (100.0 / (1.0 + lg / ll)), 2)

    macd_val = None
    if n >= 35:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        mv = _safe_float((ema12 - ema26).iloc[-1])
        macd_val = round(mv, 2) if mv is not None else None

    yearly_prices: dict[str, dict[str, float]] = {}
    if hasattr(close.index, "year"):
        for yr, grp in close.groupby(close.index.year):
            yearly_prices[str(yr)] = {
                "min": round(float(grp.min()), 1),
                "max": round(float(grp.max()), 1),
                "avg": round(float(grp.mean()), 1),
            }

    weekly_pts: list[dict[str, Any]] = []
    tail = close.iloc[-504:] if n > 504 else close
    step = max(1, len(tail) // 90)
    for idx in range(0, len(tail), step):
        dt = tail.index[idx]
        d_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        v = _safe_float(tail.iloc[idx])
        if v is not None:
            weekly_pts.append({"date": d_str, "close": round(v, 1)})
    if latest_close is not None and (not weekly_pts or weekly_pts[-1]["date"] != latest_date):
        weekly_pts.append({"date": latest_date, "close": round(latest_close, 1)})

    return {
        "latest_close": round(latest_close, 1) if latest_close is not None else None,
        "latest_date": latest_date,
        "returns": returns,
        "rsi14": rsi14,
        "macd": macd_val,
        "yearly_prices": yearly_prices,
        "price_series_weekly": weekly_pts,
    }


def fetch_stock_data(
    constituent: dict[str, Any],
    cache_dir: Path,
    use_cache: bool = True,
    max_cache_age_hours: float = 20.0,
    sleep_sec: float = 0.2,
) -> dict[str, Any] | None:
    """1銘柄分の日本株データをyfinanceから取得（またはキャッシュ読込）する。"""
    yf_symbol = constituent["yf_symbol"]
    stock_cache_dir = cache_dir / "stocks"
    stock_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = stock_cache_dir / f"{constituent['code']}.json"

    if use_cache and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        if age_hours <= max_cache_age_hours:
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    for attempt in range(4):
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info or {}
            hist = ticker.history(period="5y", interval="1d", auto_adjust=True)
            tech = _calc_returns_and_technicals(hist)

            inc = ticker.income_stmt
            q_inc = ticker.quarterly_income_stmt
            bs = ticker.balance_sheet
            cf = ticker.cashflow

            cur_price = (
                _safe_float(info.get("currentPrice"))
                or _safe_float(info.get("regularMarketPrice"))
                or tech["latest_close"]
            )
            div_rate = _safe_float(info.get("dividendRate"))
            fwd_yield = None
            if div_rate and div_rate > 0 and cur_price and cur_price > 0:
                fwd_yield = round(div_rate / cur_price * 100.0, 2)
            else:
                raw_dy = _safe_float(info.get("dividendYield"))
                if raw_dy is not None and raw_dy > 0:
                    fwd_yield = round(raw_dy * 100.0 if raw_dy < 0.35 else raw_dy, 2)
            if fwd_yield is not None and fwd_yield > 20.0:
                fwd_yield = None

            data: dict[str, Any] = {
                "code": constituent["code"],
                "yf_symbol": yf_symbol,
                "name": constituent["name"],
                "sector33": constituent["sector33"],
                "sector_group": constituent["sector_group"],
                "scale": constituent.get("scale", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "price": {
                    "current": cur_price,
                    "latest_date": tech["latest_date"],
                    "market_cap": _safe_float(info.get("marketCap")),
                    "enterprise_value": _safe_float(info.get("enterpriseValue")),
                    "returns": tech["returns"],
                    "rsi14": tech["rsi14"],
                    "macd": tech["macd"],
                    "yearly_prices": tech["yearly_prices"],
                    "price_series_weekly": tech["price_series_weekly"],
                },
                "valuation": {
                    "trailing_pe": _safe_float(info.get("trailingPE")),
                    "forward_pe": _safe_float(info.get("forwardPE")),
                    "price_to_book": _safe_float(info.get("priceToBook")),
                    "dividend_yield": fwd_yield,
                    "dividend_rate": div_rate,
                    "trailing_eps": _safe_float(info.get("trailingEps")),
                    "forward_eps": _safe_float(info.get("forwardEps")),
                    "roe_info": _safe_float(info.get("returnOnEquity")),
                    "roa_info": _safe_float(info.get("returnOnAssets")),
                },
                "analyst": {
                    "num_opinions": info.get("numberOfAnalystOpinions"),
                    "target_mean_price": _safe_float(info.get("targetMeanPrice")),
                    "recommendation_mean": _safe_float(info.get("recommendationMean")),
                },
                "financials": {
                    "revenue": _extract_series(inc, ["Total Revenue", "Operating Revenue"]),
                    "operating_income": _extract_series(inc, ["Operating Income", "EBIT"]),
                    "ebit": _extract_series(inc, ["EBIT", "Operating Income"]),
                    "pretax_income": _extract_series(inc, ["Pretax Income"]),
                    "net_income": _extract_series(inc, ["Net Income", "Net Income Common Stockholders"]),
                    "eps": _extract_series(inc, ["Diluted EPS", "Basic EPS"]),
                    "interest_expense": _extract_series(inc, ["Interest Expense", "Interest Expense Non Operating"]),
                },
                "quarterly": {
                    "revenue": _extract_series(q_inc, ["Total Revenue", "Operating Revenue"], limit=6),
                    "operating_income": _extract_series(q_inc, ["Operating Income", "EBIT"], limit=6),
                    "net_income": _extract_series(q_inc, ["Net Income", "Net Income Common Stockholders"], limit=6),
                },
                "balance_sheet": {
                    "total_debt": _extract_series(bs, ["Total Debt", "Long Term Debt And Capital Lease Obligation"]),
                    "cash": _extract_series(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
                    "equity": _extract_series(bs, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]),
                    "total_assets": _extract_series(bs, ["Total Assets"]),
                },
                "cashflow": {
                    "operating_cf": _extract_series(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
                    "capex": _extract_series(cf, ["Capital Expenditure"]),
                    "free_cf": _extract_series(cf, ["Free Cash Flow"]),
                    "dividends_paid": _extract_series(cf, ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
                },
                "summary": info.get("longBusinessSummary", ""),
            }

            cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            return data
        except Exception as exc:
            msg = str(exc)
            if "Too Many Requests" in msg or "Rate limited" in msg or "429" in msg:
                wait_s = 8.0 * (attempt + 1)
                logger.warning("%s レート制限 (attempt %d): %.0f秒待機", yf_symbol, attempt + 1, wait_s)
                time.sleep(wait_s)
            else:
                logger.warning("%s の取得に失敗 (attempt %d): %s", yf_symbol, attempt + 1, exc)
                time.sleep(1.5)

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
