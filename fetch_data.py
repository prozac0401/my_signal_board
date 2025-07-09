"""
fetch_data.py – 거시·자산 + 부동산 원천 데이터 수집 (v4)
────────────────────────────────────────────────────────
추가 ✅ R‑ONE Open API / 국토교통부 통계누리 Open API 연동
    1) 주택 매매·전세가격지수 (월‧주)   – STATBL_ID 기준 호출
    2) 미분양주택 현황 (월)              – form_id=2082 style_num=128
    3) 매수(우위)지수 (월‧주)            – STATBL_ID 및 EasyStat 주간 CSV
결과 CSV 예)
    • PriceIdxSale_month.csv   (월)
    • BuyerSentiment_weekly.csv (주)
    • UnsoldHousing_month.csv  (월)
기존 거시 변수들과 동일 폴더(data/)에 저장됩니다.
"""

from __future__ import annotations

import os
import io
import datetime as dt
from pathlib import Path
from typing import List
import logging

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

# ── 환경 준비 ───────────────────────────────────
load_dotenv()
FRED_KEY   = os.getenv("FRED_KEY", "")
ECOS_KEY   = os.getenv("ECOS_KEY", "")
RONE_KEY   = os.getenv("RONE_KEY", "")      # 한국부동산원 Open API
MOLIT_KEY  = os.getenv("MOLIT_KEY", "")     # 국토교통부 통계누리 Open API
DIR = Path("data"); DIR.mkdir(exist_ok=True)

# FRED 시리즈 ID 상수화
RATE_FRED_ID   = "INTDSRKRM193N"    # Bank of Korea Base Rate (monthly)
BOND10_FRED_ID = "IRLTLT01KRM156N"  # 10‑Year Government Bond Yield (monthly)

# ── 공통 유틸 ───────────────────────────────────

def save(name: str, obj: pd.Series | pd.DataFrame) -> None:
    """Save Series/DataFrame to CSV under data/ with simple logging."""
    obj.to_csv(DIR / f"{name}.csv", index=True)
    print(f"✔ {name:25s} {len(obj):6,d}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 기존 API 래퍼 (FRED, ECOS, yfinance) ──────────────────────────

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
        f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/10000/{code}/M/200801/{end}"
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
    ser = (
        raw["Adj Close"].squeeze()
        if "Adj Close" in raw.columns else raw["Close"].squeeze()
    )
    ser.name = ticker
    return ser

# ── NEW: 한국부동산원 R‑ONE Open API 래퍼 ────────────────────────

def rone_series(
    statbl_id: str,
    *,
    dtcycle: str = "MM",       # "MM"=월, "WW"=주
    cls_cd: str | None = None,  # 지역 코드 (None → 전국)
    start: str = "200801",
    end: str | None = None,
) -> pd.DataFrame:
    """Return tidy DataFrame of R-ONE API rows across period range with detailed logging."""
    if not RONE_KEY:
        raise RuntimeError("RONE_KEY missing in environment")
    if end is None:
        end = dt.date.today().strftime("%Y%m" if dtcycle == "MM" else "%Y%U")
    freq_str = "M" if dtcycle == "MM" else "W"
    periods = pd.period_range(start, end, freq=freq_str)
    url = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
    frames: list[pd.DataFrame] = []

    for p in periods:
        wrt = p.strftime("%Y%m") if dtcycle == "MM" else p.strftime("%Y%U")
        params = {
            "KEY": RONE_KEY,
            "Type": "json",
            "STATBL_ID": statbl_id,
            "DTACYCLE_CD": dtcycle,
            "WRTTIME_IDTFR_ID": wrt,
        }
        if cls_cd:
            params["CLS_CD"] = cls_cd
        logger.info("→ GET R-ONE %s %s cls_cd=%s", statbl_id, wrt, cls_cd or "ALL")
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            j = resp.json()
            rows = j["SttsApiTblData"][1]["row"]
            logger.info("  ← %s rows received", len(rows))
            frames.append(pd.DataFrame(rows))
        except Exception as e:
            logger.warning("  ⚠ failed (%s)", e)
            continue

    if not frames:
        logger.warning("No data retrieved for %s", statbl_id)
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df.rename(columns={"DTA_VAL": "value", "CLS_NM": "region"}, inplace=True)
    time_col = "TIME_ID" if "TIME_ID" in df.columns else "TIME"
    df["date"] = pd.to_datetime(
        df[time_col], format="%Y%m" if dtcycle == "MM" else "%Y%W"
    )
    df.set_index("date", inplace=True)
    return df[["region", "value"]]

# ── NEW: 국토부 미분양주택 Open API ────────────────────────────

def molit_unsold(
    start: str = "200801",
    end: str | None = None,
    style_num: int = 128,  # 128 = 시·도별
) -> pd.DataFrame:
    if not MOLIT_KEY:
        raise RuntimeError("MOLIT_KEY missing in environment")
    if end is None:
        end = dt.date.today().strftime("%Y%m")
    url = "https://stat.molit.go.kr/portal/openapi/nationwideStats.do"
    params = {
        "key": MOLIT_KEY,
        "form_id": 2082,  # 미분양현황_종합
        "style_num": style_num,
        "start_dt": start,
        "end_dt": end,
        "format": "json",
    }
    j = requests.get(url, params=params, timeout=30).json()
    rows = j.get("result", {}).get("data", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    date_col = next(c for c in df.columns if c.lower().startswith("yyyy"))
    df["date"] = pd.to_datetime(df[date_col], format="%Y%m")
    df.set_index("date", inplace=True)
    return df

# ── 1. 원시 거시 시리즈 수집 (기존) ──────────────────────────
fx   = fred("DEXKOUS").rename("FX");        save("FX_raw", fx)

gold = pd.read_csv(
    io.StringIO(requests.get("https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2").text),
    sep=";", engine="python",
)
_gold = gold[gold.Close != "-"][["Date", "Close"]].set_index("Date").astype(float).squeeze()
_gold.index = pd.to_datetime(_gold.index); _gold.name = "Gold"; save("Gold_raw", _gold)

dxy  = fred("DTWEXM").rename("DXY");       save("DXY_raw", dxy)

rate   = fred(RATE_FRED_ID, freq="m", start="1964-01-01").rename("Rate");   save("Rate_month", rate)
bond10 = fred(BOND10_FRED_ID, freq="m", start="2000-01-01").rename("Bond10"); save("Bond10_month", bond10)

_m2_candidates = [
    ecos("101Y003", ITEM_CODE1="BBHS00"),
    ecos("060Y002"),
    ecos("LDT_MA001_A", ITM_ID="A"),
]
M2 = next((s for s in _m2_candidates if not s.empty), pd.Series(name="M2")); save("M2_month", M2)

kodex = fetch_adj_close("069500.KS").rename("KODEX200"); save("KODEX200_raw", kodex)

# ── NEW 4. 부동산 지표 수집 ───────────────────────────────
# 4‑1 주택 매매·전세가격지수 (월)
price_sale_m  = rone_series("A_2024_00016")  # 매매지수_아파트
price_rent_m  = rone_series("A_2024_00024")  # 전세지수_아파트
save("PriceIdxSale_month", price_sale_m)
save("PriceIdxRent_month", price_rent_m)

# 4‑2 미분양주택 (월)
unsold_m = molit_unsold()
save("UnsoldHousing_month", unsold_m)

# 4‑3 매수(우위)지수 – 월 & 주
buyer_m = rone_series("A_2024_00076")           # 월
#buyer_w = rone_series("T248163133074619", dtcycle="WW")  # 주
save("BuyerSentiment_month",  buyer_m)
#save("BuyerSentiment_weekly", buyer_w)

# ── 월→일 변환 예시 (거시지표) ────────────────────────────────
rate_d   = rate.resample("D").ffill()
bond10_d = bond10.resample("D").ffill()
M2_d     = M2.resample("D").interpolate("linear").rename("M2_D"); save("M2_daily", M2_d)

# ── 통합 예시 (거시 only) ───────────────────────────────────
all_df = (
    pd.concat([fx, _gold, dxy, rate_d, M2_d, bond10_d, kodex], axis=1)
      .sort_index()
      .ffill()
)
save("all_data", all_df)
print("✅ Fetch completed – last 5 rows:\n", all_df.tail())
