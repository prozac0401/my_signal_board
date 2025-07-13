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
✓ M2_US    : 미국 M2 Money Stock (FRED M2SL, 월 → 일 선형보간)
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
MOLIT_KEY = os.getenv("MOLIT_KEY", "")  # 국토부 미분양주택 현황
RONE_KEY = os.getenv("RONE_KEY", "")    # 부동산원 R-ONE API Key
RTMS_AREA = os.getenv("RTMS_AREA", "")   # 부동산 지수 조회 지역 코드(콤마구분)
DIR = Path("data"); DIR.mkdir(exist_ok=True)

# FRED 시리즈 ID 상수화
RATE_FRED_ID = "INTDSRKRM193N"     # Bank of Korea Base Rate (monthly)
BOND10_FRED_ID = "IRLTLT01KRM156N"  # 10‑Year Korea Gov Bond Yield (monthly)
US_RATE_ID = "FEDFUNDS"            # Federal Funds Rate (monthly)
US_BOND10_ID = "GS10"              # 10‑Year Treasury Constant Maturity (monthly)
CPI_FRED_ID = "CPIAUCSL"           # CPI All Items (monthly)
CORECPI_FRED_ID = "CPILFESL"       # Core CPI (monthly)

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


def fetch_rone_price_index(kind: str, areas: List[str]) -> pd.DataFrame:
    """R-ONE 주택가격지수(kinds="sale" or "rent")"""
    if not RONE_KEY or not areas:
        return pd.DataFrame()

    base = "https://r-one.co.kr/idxsvc/getAptPriceIndex"
    frames = []
    end = dt.date.today().strftime("%Y%m")
    for cd in areas:
        try:
            resp = requests.get(
                base,
                params={
                    "serviceKey": RONE_KEY,
                    "areaCode": cd,
                    "indexGubun": kind,
                    "startMonth": "200601",
                    "endMonth": end,
                },
                timeout=30,
            )
            resp.raise_for_status()
            items = resp.json().get("response", {}).get("body", {}).get("items", [])
            df = pd.DataFrame(items)
            if df.empty:
                continue
            df.index = pd.to_datetime(df["baseYm"], format="%Y%m")
            df = df[["idx"]].astype(float).rename(columns={"idx": f"{kind}_{cd}"})
            frames.append(df)
        except Exception as e:  # pragma: no cover - 네트워크 오류 대비
            print("R-ONE fetch failed", cd, e)
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()


def fetch_unsold_house_status() -> pd.Series:
    """국토부 미분양주택 현황"""
    if not MOLIT_KEY:
        return pd.Series(dtype=float, name="Unsold")

    url = "https://apis.data.go.kr/B552555/unsoldHouseStatus/getUnsoldHouseStatus"
    end = dt.date.today().strftime("%Y%m")
    try:
        resp = requests.get(
            url,
            params={
                "serviceKey": MOLIT_KEY,
                "startYm": "200601",
                "endYm": end,
                "numOfRows": 1000,
                "pageNo": 1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("response", {}).get("body", {}).get("items", [])
        df = pd.DataFrame(items)
        if df.empty:
            return pd.Series(dtype=float, name="Unsold")
        df.index = pd.to_datetime(df["ym"], format="%Y%m")
        ser = df["unsoldHouseCnt"].astype(float)
        ser.name = "Unsold"
        return ser
    except Exception as e:  # pragma: no cover - API 오류 대비
        print("Unsold house fetch failed", e)
        return pd.Series(dtype=float, name="Unsold")


def fetch_buy_index() -> pd.Series:
    """주간 매수우위지수 (부동산원 주간동향)"""
    url = "https://www.reb.or.kr/r-one/report.do?cmd=weeklyTrend"
    try:
        html = requests.get(url, timeout=30).text
        tables = pd.read_html(html)
        df = tables[0]
        df.columns = [c.strip() for c in df.columns]
        if "날짜" in df.columns:
            df.index = pd.to_datetime(df["날짜"])
        elif "주차" in df.columns:
            df.index = pd.to_datetime(df["주차"])
        else:
            df.index = pd.to_datetime(df.iloc[:, 0])
        ser = df.iloc[:, 1].astype(float)
        ser.name = "BuyIndex"
        return ser.sort_index()
    except Exception as e:  # pragma: no cover - 스크래핑 오류 대비
        print("Buy index fetch failed", e)
        return pd.Series(dtype=float, name="BuyIndex")


# ── 1. 원시 시리즈 수집 ──────────────────────────
fx   = fred("DEXKOUS");                     fx.name  = "FX";        save("FX_raw", fx)

gold = pd.read_csv(
    io.StringIO(requests.get("https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2").text),
    sep=";", engine="python",
)
gold = gold[gold.Close != "-"][["Date", "Close"]].set_index("Date").astype(float).squeeze()
gold.index = pd.to_datetime(gold.index);    gold.name = "Gold";     save("Gold_raw", gold)

# Gold 원화 환산 (원/그램)
gold_krwg = (gold * fx / 31.1035).rename("Gold_KRWg")
save("Gold_KRWg", gold_krwg)

dxy  = fred("DTWEXM");                      dxy.name = "DXY";       save("DXY_raw", dxy)

# --- 기준금리 & 국채 10Y (FRED) ------------------------------------------------
rate = fred(RATE_FRED_ID, freq="m", start="1964-01-01").rename("Rate"); save("Rate_month", rate)
bond10 = fred(BOND10_FRED_ID, freq="m", start="2000-01-01").rename("Bond10"); save("Bond10_month", bond10)

# --- 연준 기준금리 & 미국 10Y -----------------------------------------------
us_rate = fred(US_RATE_ID, freq="m", start="2000-01-01").rename("Rate_US")
save("RateUS_month", us_rate)
us_bond10 = fred(US_BOND10_ID, freq="m", start="2000-01-01").rename("Bond10_US")
save("Bond10US_month", us_bond10)

# --- 물가 (FRED) --------------------------------------------------------------
cpi = fred(CPI_FRED_ID, freq="m", start="2000-01-01").rename("CPI")
save("CPI_month", cpi)
core_cpi = fred(CORECPI_FRED_ID, freq="m", start="2000-01-01").rename("CoreCPI")
save("CoreCPI_month", core_cpi)

# Real Rate = 정책금리 - CPI YoY
cpi_yoy = cpi.pct_change(12) * 100
real_rate = (rate - cpi_yoy).rename("RealRate")
save("RealRate_month", real_rate)

# --- 미국 M2 (FRED) ------------------------------------------------------------
m2_us = fred("M2SL", freq="m", start="2008-01-01").rename("M2_US")
save("M2_US_month", m2_us)

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

# --- 부동산 지수 --------------------------------------------------------------
areas = [a.strip() for a in RTMS_AREA.split(',') if a.strip()]
idx_sale = fetch_rone_price_index("sale", areas)
if not idx_sale.empty:
    save("RTMS_sale", idx_sale)
idx_rent = fetch_rone_price_index("rent", areas)
if not idx_rent.empty:
    save("RTMS_rent", idx_rent)

unsold = fetch_unsold_house_status()
if not unsold.empty:
    save("Unsold", unsold)

buy_idx = fetch_buy_index()
if not buy_idx.empty:
    save("BuyIndex", buy_idx)

# ── 2. 월→일 변환 ──────────────────────────────
rate_d = rate.resample("D").ffill()
bond10_d = bond10.resample("D").ffill()
us_rate_d = us_rate.resample("D").ffill()
us_bond10_d = us_bond10.resample("D").ffill()
m2_d = m2.resample("D").interpolate("linear").rename("M2_D"); save("M2_daily", m2_d)
m2_us_d = m2_us.resample("D").interpolate("linear").rename("M2_US_D"); save("M2_US_daily", m2_us_d)
cpi_d = cpi.resample("D").ffill().rename("CPI_D"); save("CPI_daily", cpi_d)
core_cpi_d = core_cpi.resample("D").ffill().rename("CoreCPI_D"); save("CoreCPI_daily", core_cpi_d)
real_rate_d = real_rate.resample("D").ffill().rename("RealRate_D"); save("RealRate_daily", real_rate_d)

if not idx_sale.empty:
    idx_sale_d = idx_sale.resample("D").ffill()
else:
    idx_sale_d = pd.DataFrame()
if not idx_rent.empty:
    idx_rent_d = idx_rent.resample("D").ffill()
else:
    idx_rent_d = pd.DataFrame()
if not unsold.empty:
    unsold_d = unsold.resample("D").ffill()
else:
    unsold_d = pd.Series(dtype=float, name="Unsold")
if not buy_idx.empty:
    buy_idx_d = buy_idx.resample("D").ffill()
else:
    buy_idx_d = pd.Series(dtype=float, name="BuyIndex")

# 금리 스프레드(10Y - 정책금리) 5일 평균
spread5d = (bond10_d - rate_d).rolling(5).mean().rename("Spread5D")
save("Spread5D", spread5d)

# ── 3. 통합 & 저장 ─────────────────────────────
all_df = (
    pd.concat(
        [
            fx,
            gold,
            gold_krwg,
            dxy,
            rate_d,
            bond10_d,
            us_rate_d,
            us_bond10_d,
            spread5d,
            m2_d,
            m2_us_d,
            cpi_d,
            core_cpi_d,
            real_rate_d,
            idx_sale_d,
            idx_rent_d,
            unsold_d,
            buy_idx_d,
            sp500,
            kodex,
            btc,
        ],
        axis=1,
    )
      .sort_index()
      .ffill()
)

save("all_data", all_df)
print(all_df.tail())
