"""
fetch_data.py  –  거시·자산 데이터 수집
────────────────────────────────────────
수집 항목
 • FX        : USD/KRW (FRED DEXKOUS, 일)
 • Gold      : XAU/USD (Stooq, 일)
 • DXY       : 달러지수 (FRED DTWEXM, 일)
 • 기준금리  : 722Y001 (월)
 • 10y 국채  : IRLTLT01KRM156N (월)
 • M2        : 101Y003 ▷ 060Y002 ▷ LDT_MA001_A (월)  → 일 보간(M2_D)
 • KODEX200  : 069500.KS (일)
출력
 • data/all_data.csv  (모든 열 일 빈도, ffill)
"""

import os, io, datetime as dt, requests, pandas as pd, yfinance as yf
from pathlib import Path
from dotenv import load_dotenv

# ── 환경 설정 ────────────────────────────────
load_dotenv()
FRED_KEY = os.getenv("FRED_KEY", "").strip()
ECOS_KEY = os.getenv("ECOS_KEY", "").strip()
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)

def save(name, ser_or_df):
    ser_or_df.to_csv(DATA_DIR / f"{name}.csv")
    print(f"✔ {name:12s} {len(ser_or_df):6,d}")

# ── 헬퍼 ─────────────────────────────────────
def fred(series_id, freq="d", start="2008-01-01"):
    url = (f"https://api.stlouisfed.org/fred/series/observations?"
           f"series_id={series_id}&api_key={FRED_KEY}&file_type=json"
           f"&frequency={freq}&observation_start={start}")
    obs = requests.get(url, timeout=30).json().get("observations", [])
    ser = pd.Series({o["date"]: float(o["value"]) for o in obs if o["value"] != "."},
                    name=series_id)
    ser.index = pd.to_datetime(ser.index); return ser

def ecos(code, **flt):
    end = dt.date.today().strftime("%Y%m")
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/10000/{code}/M/200801/{end}"
    rows = requests.get(url, timeout=30).json().get("StatisticSearch", {}).get("row", [])
    if flt: k, v = next(iter(flt.items())); rows = [r for r in rows if r.get(k)==v]
    ser = pd.Series({r["TIME"]: float(r["DATA_VALUE"]) for r in rows})
    ser.index = pd.to_datetime(ser.index, format="%Y%m"); return ser

# ── 1. 원시 시리즈 수집 ───────────────────────
fx     = fred("DEXKOUS", "d");                  save("Raw_FX", fx)
gold   = pd.read_csv(io.StringIO(requests.get("https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2").text),
                     sep=";", engine="python")
gold   = gold[gold.Close!="-"][["Date","Close"]].set_index("Date").astype(float).squeeze()
gold.index = pd.to_datetime(gold.index); gold.name="Gold";            save("Raw_Gold", gold)

dxy    = fred("DTWEXM", "d");                   save("Raw_DXY", dxy)
rate   = ecos("722Y001");                       save("Raw_Rate", rate)

m2     = ecos("101Y003", ITEM_CODE1="BBHS00") or ecos("060Y002") or ecos("LDT_MA001_A", ITM_ID="A")
m2.name="M2";                                   save("Raw_M2_monthly", m2)

bond10 = fred("IRLTLT01KRM156N", "m");          save("Raw_Bond10", bond10)

kodex  = yf.download("069500.KS", start="2008-01-01", auto_adjust=False)["Adj Close"]
kodex.name="KODEX200"; kodex.index = kodex.index.tz_localize(None);   save("Raw_KODEX200", kodex)

# ── 2. 월→일 보간 / 리샘플 ────────────────────
rate_d   = rate.resample("D").ffill()
bond10_d = bond10.resample("D").ffill()

# M2 일 보간
m2_d = (
    m2.resample("D").interpolate("linear")
    .rename("M2_D")
)
save("Raw_M2_daily", m2_d)

# ── 3. 통합 & 저장 ───────────────────────────
df_all = (
    pd.concat([fx, gold, dxy, rate_d, m2_d, bond10_d, kodex], axis=1)
      .sort_index()
      .ffill()
)
save("all_data", df_all)
print(df_all.tail())
