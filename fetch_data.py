#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_data.py  –  거시·자산 원천 데이터 수집 (v4)
─────────────────────────────────────────────
✓ FX       : USD/KRW (FRED DEXKOUS, 일)
✓ Gold     : XAU/USD (Stooq, 일)
✓ DXY      : 달러지수 (FRED DTWEXM, 일)
✓ Rate     : 한국은행 기준금리 (FRED INTDSRKRM193N, 월 → 일 ffill)
✓ Bond10   : 국채 10년 수익률 (FRED IRLTLT01KRM156N, 월 → 일 ffill)
✓ M2       : 통화량(월) 101Y003 ▷ 060Y002 ▷ LDT_MA001_A → 일 선형보간(M2_D)
✓ SP500    : S&P 500 (^GSPC, 일)
✓ KODEX200 : 069500.KS (일)
결과 → data/all_data.csv  (일 빈도, ffill)
"""

from __future__ import annotations

import os
import io
import datetime as dt
from pathlib import Path
from typing import List

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

# ── 환경 준비 ───────────────────────────────────
load_dotenv()
FRED_KEY = os.getenv("FRED_KEY", "")
ECOS_KEY = os.getenv("ECOS_KEY", "")
DIR = Path("data"); DIR.mkdir(exist_ok=True)

# FRED 시리즈 ID 상수화
RATE_FRED_ID   = "INTDSRKRM193N"    # Bank of Korea Base Rate (monthly)
BOND10_FRED_ID = "IRLTLT01KRM156N"  # 10‑Year Government Bond Yield (monthly)

# ── 공통 유틸 ───────────────────────────────────

def save(name: str, obj: pd.Series | pd.DataFrame) -> None:
    obj.to_csv(DIR / f"{name}.csv")
    print(f"✔ {name:13s} {len(obj):6,d}")


# ── API 래퍼 ────────────────────────────────────

def fred(series: str, *, freq: str = "d", start: str = "2008-01-01") -> pd.Series:
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series}&api_key={FRED_KEY}&file_type=json"
        f"&frequency={freq}&observation_start={start}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    if "observations" not in j:
        raise RuntimeError(f"FRED API Error for {series}: {j}")
    ser = pd.Series(
        {o["date"]: float(o["value"]) for o in j["observations"] if o["value"] != "."},
        name=series,
    )
    ser.index = pd.to_datetime(ser.index)
    return ser


def ecos(code: str, **flt) -> pd.Series:
    end = dt.date.today().strftime("%Y%m")
    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}"
        f"/json/kr/1/10000/{code}/M/200801/{end}"
    )
    rows: List[dict] = (
        requests.get(url, timeout=30)
        .json()
        .get("StatisticSearch", {})
        .get("row", [])
    )
    if flt:
        k, v = next(iter(flt.items()))
        rows = [r for r in rows if r.get(k) == v]
    ser = pd.Series({r["TIME"]: float(r["DATA_VALUE"]) for r in rows})
    ser.index = pd.to_datetime(ser.index, format="%Y%m")
    return ser


def fetch_adj_close(ticker: str, *, start: str = "2008-01-01") -> pd.Series:
    raw = yf.download(ticker, start=start, progress=False, threads=False)
    if raw.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker}")
    raw.index = raw.index.tz_localize(None)

    if isinstance(raw.columns, pd.MultiIndex):
        lvl0 = raw.columns.get_level_values(0)
        if "Adj Close" in lvl0:
            ser = raw["Adj Close"].squeeze()
        else:
            ser = raw["Close"].squeeze()
    else:
        ser = raw["Adj Close"] if "Adj Close" in raw.columns else raw["Close"]

    ser.name = ticker
    return ser


# ── 1. 원시 시리즈 수집 ──────────────────────────
fx   = fred("DEXKOUS");                     fx.name  = "FX";        save("FX_raw", fx)

gold = pd.read_csv(
    io.StringIO(requests.get("https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2").text),
    sep=";", engine="python",
)
gold = gold[gold.Close != "-"][["Date", "Close"]].set_index("Date").astype(float).squeeze()
gold.index = pd.to_datetime(gold.index);    gold.name = "Gold";     save("Gold_raw", gold)

dxy  = fred("DTWEXM");                      dxy.name = "DXY";       save("DXY_raw", dxy)

# --- 기준금리 & 국채 10Y (FRED) ------------------------------------------------
rate   = fred(RATE_FRED_ID, freq="m", start="1964-01-01").rename("Rate");      save("Rate_month", rate)
bond10 = fred(BOND10_FRED_ID, freq="m", start="2000-01-01").rename("Bond10");  save("Bond10_month", bond10)

# --- M2 (순차 폴백) ----------------------------------------------------------
_m2_candidates = [
    ecos("101Y003", ITEM_CODE1="BBHS00"),
    ecos("060Y002"),
    ecos("LDT_MA001_A", ITM_ID="A"),
]

m2 = next((s for s in _m2_candidates if not s.empty), pd.Series(name="M2"))
save("M2_month", m2)

# --- 주가 지수 (Yahoo Finance) ------------------------------------------------
sp500 = fetch_adj_close("^GSPC").rename("SP500");          save("SP500_raw", sp500)
kodex = fetch_adj_close("069500.KS").rename("KODEX200");  save("KODEX200_raw", kodex)
btc   = fetch_adj_close("BTC-USD", start="2014-01-01").rename("Bitcoin"); save("Bitcoin_raw", btc)

# ── 2. 월→일 변환 ──────────────────────────────
rate_d   = rate.resample("D").ffill()
bond10_d = bond10.resample("D").ffill()
m2_d     = m2.resample("D").interpolate("linear").rename("M2_D");          save("M2_daily", m2_d)

# ── 3. 통합 & 저장 ─────────────────────────────
all_df = (
    pd.concat([fx, gold, dxy, rate_d, m2_d, bond10_d, sp500, kodex, btc], axis=1)
      .sort_index()
      .ffill()
)

save("all_data", all_df)
print(all_df.tail())
