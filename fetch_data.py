"""
fetch_data.py · 2025-07
────────────────────────────────────────────────────────
수집·가공 항목
  • FX            : USD/KRW (FRED DEXKOUS, 일)
  • Gold          : XAU/USD (Stooq, 일)
  • DXY           : 달러지수 (FRED DTWEXM, 일)
  • 기준금리      : 한은 722Y001 (월)
  • 10y 국채      : FRED IRLTLT01KRM156N (월)  → 일드갭 계산용
  • M2            : 101Y003 ▷ 060Y002 ▷ LDT_MA001_A (월)
  • 수원 거래량   : K-REB A_AA001_B (월, 장안·권선·팔달·영통)
  • KODEX200      : 069500.KS (일)
결과
  • data/all_data.csv (일 주기, ffill)
"""

import os, io, time, datetime as dt, requests, pandas as pd, yfinance as yf
from pathlib import Path
from dotenv import load_dotenv

# ─────────────────── 환경 ───────────────────
load_dotenv()
FRED_KEY = os.getenv("FRED_KEY", "").strip()
ECOS_KEY = os.getenv("ECOS_KEY", "").strip()
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)

def save(name, obj):
    (obj if isinstance(obj, pd.DataFrame) else obj.to_frame()).to_csv(DATA_DIR / f"{name}.csv")
    print(f"✔ {name:11s} {len(obj):6,d} rows")

# ────────── 1. 헬퍼 ─────────────────────────
def fred(series_id, freq="d", start="2008-01-01"):
    if not FRED_KEY:
        return pd.Series(dtype=float, name=series_id)
    url = ("https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
           f"&frequency={freq}&observation_start={start}")
    obs = requests.get(url, timeout=30).json().get("observations", [])
    ser = pd.Series({o["date"]: float(o["value"]) for o in obs if o["value"] != "."},
                    name=series_id)
    ser.index = pd.to_datetime(ser.index); return ser

def ecos(code, **flt):
    if not ECOS_KEY: return pd.Series(dtype=float)
    end = dt.date.today().strftime("%Y%m")
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/10000/"
           f"{code}/M/200801/{end}")
    rows = requests.get(url, timeout=30).json().get("StatisticSearch", {}).get("row", [])
    if flt: k, v = next(iter(flt.items())); rows = [r for r in rows if r.get(k) == v]
    ser = pd.Series({r["TIME"]: float(r["DATA_VALUE"]) for r in rows if r["DATA_VALUE"] != "."})
    ser.index = pd.to_datetime(ser.index, format="%Y%m"); return ser

# ────────── 2. 수집 ─────────────────────────
fx     = fred("DEXKOUS", "d");         save("Raw_FX", fx)
gold   = fred("DTWEXM",  "d");         # 임시 저장 X (DXY)
dxy    = fred("DTWEXM",  "d");         save("Raw_DXY", dxy)
gold   = pd.read_csv(io.StringIO(requests.get("https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2").text),
                     sep=";", engine="python")
gold = gold[gold.Close != "-"][["Date","Close"]].set_index("Date").astype(float).squeeze()
gold.index = pd.to_datetime(gold.index); gold.name="Gold"; save("Raw_Gold", gold)

rate   = ecos("722Y001");              rate.name="Rate";    save("Raw_Rate", rate)
m2     = ecos("101Y003", ITEM_CODE1="BBHS00") or ecos("060Y002") or ecos("LDT_MA001_A", ITM_ID="A")
m2.name="M2";                          save("Raw_M2", m2)

bond10 = fred("IRLTLT01KRM156N", "m"); bond10.name="Bond10"; save("Raw_Bond10", bond10)

# K-REB 거래량
def kreb_volume():
    try:
        s = requests.Session()
        otp = s.post("https://r-one.korea.kr/comm/fileDn/GenerateOTP.do",
                     data={"filetype":"csv","orgId":"118","tblId":"A_AA001_B",
                           "csvAttrs":"AA001_월별"}, timeout=30).text
        csv = s.post("https://r-one.korea.kr/comm/fileDn/downloadCsvFile.do",
                     data={"otp": otp}, timeout=30).content
        df  = pd.read_csv(io.BytesIO(csv), encoding="euc-kr")
        sub = df[df["시군구코드"].isin([41111,41113,41115,41117])]
        sub["date"] = pd.to_datetime(sub["거래년월"].astype(str)+"01", format="%Y%m%d")
        pv = (sub.pivot(index="date", columns="시군구코드", values="건수")
                .rename(columns={41111:"Vol_장안구",41113:"Vol_권선구",
                                 41115:"Vol_팔달구",41117:"Vol_영통구"}))
        save("Raw_SuwonVol", pv); return pv
    except Exception as e:
        print("⚠ K-REB volume error:", e)
        return pd.DataFrame(index=pd.DatetimeIndex([], name="date"))
vol = kreb_volume()

# ETF
kodex = yf.download("069500.KS", start="2008-01-01", auto_adjust=False)["Adj Close"]
kodex.name = "KODEX200"; kodex.index = kodex.index.tz_localize(None)

# ────────── 3. 통합 & 저장 ──────────────────
# 월→일 보간
rate_d   = rate.resample("D").ffill()
m2_d     = m2.resample("D").ffill()
bond10_d = bond10.resample("D").ffill()
vol_d    = vol.resample("D").ffill() if not vol.empty else vol

df_all = (pd.concat([fx, gold, dxy, rate_d, m2_d, bond10_d, vol_d, kodex], axis=1)
            .sort_index()
            .ffill())

save("all_data", df_all)
print(df_all.tail())
