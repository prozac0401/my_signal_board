"""
fetch_data.py  –  거시·자산 원천 데이터 수집
────────────────────────────────────────────
✓ FX   : USD/KRW (FRED DEXKOUS, 일)
✓ Gold : XAU/USD (Stooq, 일)
✓ DXY  : 달러지수 (FRED DTWEXM, 일)
✓ Rate : 기준금리 722Y001 (월 → 일 ffill)
✓ Bond10 : 10년물 IRLTLT01KRM156N (월 → 일 ffill)
✓ M2   : 통화량(월) 101Y003 ▷ 060Y002 ▷ LDT_MA001_A
         → 일 선형보간(M2_D)
✓ KODEX200 : 069500.KS (일)
결과 → data/all_data.csv  (일 빈도, ffill)
"""

import os, io, datetime as dt, requests, pandas as pd, yfinance as yf
from pathlib import Path
from dotenv import load_dotenv

# ── 준비 ───────────────────────────────────────
load_dotenv()
FRED_KEY = os.getenv("FRED_KEY", "")
ECOS_KEY = os.getenv("ECOS_KEY", "")
DIR = Path("data"); DIR.mkdir(exist_ok=True)

def save(name, obj):
    obj.to_csv(DIR / f"{name}.csv")
    print(f"✔ {name:13s} {len(obj):6,d}")

# ── 헬퍼 ───────────────────────────────────────
def fred(series, freq="d", start="2008-01-01"):
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series}&api_key={FRED_KEY}&file_type=json"
           f"&frequency={freq}&observation_start={start}")
    obs = requests.get(url, timeout=30).json()["observations"]
    s = pd.Series({o["date"]: float(o["value"]) for o in obs if o["value"] != "."},
                  name=series)
    s.index = pd.to_datetime(s.index); return s

def ecos(code, **flt):
    end = dt.date.today().strftime("%Y%m")
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}"
           f"/json/kr/1/10000/{code}/M/200801/{end}")
    rows = requests.get(url, timeout=30).json().get("StatisticSearch", {}).get("row", [])
    if flt:
        k, v = next(iter(flt.items())); rows = [r for r in rows if r.get(k) == v]
    ser = pd.Series({r["TIME"]: float(r["DATA_VALUE"]) for r in rows})
    ser.index = pd.to_datetime(ser.index, format="%Y%m"); return ser

# ── 1. 원시 시리즈 ──────────────────────────────
fx     = fred("DEXKOUS");                      save("FX_raw", fx)
gold   = pd.read_csv(io.StringIO(requests.get(
          "https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2").text),
          sep=";", engine="python")
gold   = gold[gold.Close!="-"][["Date","Close"]].set_index("Date").astype(float).squeeze()
gold.index = pd.to_datetime(gold.index); gold.name="Gold";       save("Gold_raw", gold)

dxy    = fred("DTWEXM");                       save("DXY_raw", dxy)
rate   = ecos("722Y001");                      save("Rate_month", rate)

m2 = (ecos("101Y003", ITEM_CODE1="BBHS00")
      or ecos("060Y002")
      or ecos("LDT_MA001_A", ITM_ID="A"))
m2.name = "M2";                                save("M2_month", m2)

bond10 = fred("IRLTLT01KRM156N", "m");         save("Bond10_month", bond10)

kodex = yf.download("069500.KS", start="2008-01-01")["Adj Close"]
kodex.name = "KODEX200"; kodex.index = kodex.index.tz_localize(None);  save("KODEX200_raw", kodex)

# ── 2. 월→일 변환 ──────────────────────────────
rate_d   = rate.resample("D").ffill()
bond10_d = bond10.resample("D").ffill()
m2_d     = m2.resample("D").interpolate("linear").rename("M2_D");   save("M2_daily", m2_d)

# ── 3. 통합 & 저장 ─────────────────────────────
all_df = (
    pd.concat([fx, gold, dxy, rate_d, m2_d, bond10_d, kodex], axis=1)
      .sort_index()
      .ffill()
)
save("all_data", all_df)
print(all_df.tail())
