import os, io, datetime as dt, time, requests, pandas as pd, yfinance as yf
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
FRED_KEY  = os.getenv("FRED_KEY", "").strip()
ECOS_KEY  = os.getenv("ECOS_KEY", "").strip()
DATA_DIR  = Path("data"); DATA_DIR.mkdir(exist_ok=True)
START_DATE = "2008-01-01"

def save_csv(name, obj):
    (obj if isinstance(obj, pd.DataFrame) else obj.to_frame())\
        .to_csv(DATA_DIR / f"{name}.csv")

# ---------- 1 FX ----------
def fetch_fx():
    if not FRED_KEY: return pd.Series(name="FX", dtype=float)
    url = ("https://api.stlouisfed.org/fred/series/observations"
           f"?series_id=DEXKOUS&api_key={FRED_KEY}&file_type=json&observation_start={START_DATE}")
    j = requests.get(url, timeout=30).json()
    s = pd.Series({o["date"]: float(o["value"]) for o in j["observations"] if o["value"] != "."},
                  name="FX")
    s.index = pd.to_datetime(s.index); save_csv("Raw_FX", s); return s

# ---------- 2 Gold ----------
def fetch_gold():
    txt = requests.get("https://stooq.com/q/d/l/?s=xauusd&c=2008&f=sd2", timeout=30).text.strip()
    delim = ";" if ";" in txt.splitlines()[0] else ","
    vals = [l.split(delim) for l in txt.splitlines()[1:]]
    s = pd.Series({d: float(p) for d, _, _, _, p, *_ in vals if p and p != "-"}, name="Gold")
    s.index = pd.to_datetime(s.index); save_csv("Raw_Gold", s); return s

# ---------- 3 M2 ----------
def ecos_series(code, **flt):
    if not ECOS_KEY: return pd.Series(dtype=float)
    end = dt.date.today().strftime("%Y%m")
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/10000/"
           f"{code}/M/200801/{end}")
    j = requests.get(url, timeout=30).json()
    rows = j.get("StatisticSearch", {}).get("row", [])
    if flt: k, v = next(iter(flt.items())); rows = [r for r in rows if r.get(k) == v]
    ser = pd.Series({r["TIME"]: float(r["DATA_VALUE"]) for r in rows if r["DATA_VALUE"] != "."})
    ser.index = pd.to_datetime(ser.index, format="%Y%m"); return ser

def fetch_m2():
    m2 = ecos_series("101Y003", ITEM_CODE1="BBHS00")
    if m2.empty: m2 = ecos_series("060Y002")
    if m2.empty: m2 = ecos_series("LDT_MA001_A", ITM_ID="A")
    m2.name = "M2"; save_csv("Raw_M2", m2); return m2

# ---------- 4 수원 거래량 ----------
def fetch_kreb_volume():
    try:
        sess = requests.Session()
        otp = sess.post(
            "https://r-one.korea.kr/comm/fileDn/GenerateOTP.do",
            data={"filetype":"csv","orgId":"118","tblId":"A_AA001_B","csvAttrs":"AA001_월별"},
            timeout=30).text
        csv = sess.post(
            "https://r-one.korea.kr/comm/fileDn/downloadCsvFile.do",
            data={"otp": otp}, timeout=30).content
        df = pd.read_csv(io.BytesIO(csv), encoding="euc-kr")
        sub = df[df["시군구코드"].isin([41111,41113,41115,41117])]
        sub["date"] = pd.to_datetime(sub["거래년월"].astype(str)+"01", format="%Y%m%d")
        piv = (sub.pivot(index="date", columns="시군구코드", values="건수")
                  .rename(columns={41111:"Vol_장안구",41113:"Vol_권선구",
                                   41115:"Vol_팔달구",41117:"Vol_영통구"}))
        save_csv("Raw_SuwonVol", piv); return piv
    except Exception as e:
        print("⚠ K‑REB volume error:", e)
        # 반환을 '날짜 Index가 있는' 빈 DF로
        empty = pd.DataFrame(index=pd.DatetimeIndex([], name="date"))
        return empty

# ---------- 5 KODEX 200 ----------
def fetch_kodex():
    k = yf.download("069500.KS", start=START_DATE, auto_adjust=False)["Adj Close"]
    k.index = k.index.tz_localize(None); k.name = "KODEX200"; return k

# ---------- MAIN ----------
def main():
    fx, gold = fetch_fx(), fetch_gold()
    m2       = fetch_m2().resample("D").ffill()
    vol_df   = fetch_kreb_volume()
    if not vol_df.empty: vol_df = vol_df.resample("D").ffill()
    kodex    = fetch_kodex()

    df_all = (pd.concat([fx, gold, m2, vol_df, kodex], axis=1)
                 .sort_index()
                 .ffill())

    save_csv("all_data", df_all)
    print(df_all.tail())

if __name__ == "__main__":
    main()
