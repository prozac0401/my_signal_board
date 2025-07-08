# fetch_data.py
import os, requests, io, pandas as pd, datetime as dt, yfinance as yf
from dotenv import load_dotenv
load_dotenv()
ECOS_KEY = os.getenv("ECOS_KEY")

# ------------------
# 1) ECOS 헬퍼 함수
# ------------------
def ecos_series(stat_code, freq, start, end):
    """한국은행 ECOS 시계열 호출 → DataFrame(date,value)."""
    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/1000/"
        f"{stat_code}/{freq}/{start}/{end}"
    )
    js = requests.get(url, timeout=30).json()["StatisticSearch"]["row"]
    df = (
        pd.DataFrame(js)[["TIME", "DATA_VALUE"]]
        .rename(columns={"TIME": "date", "DATA_VALUE": stat_code})
    )
    df["date"] = pd.to_datetime(df["date"])
    df[stat_code] = pd.to_numeric(df[stat_code], errors="coerce")
    return df.set_index("date")

today = dt.datetime.today().strftime("%Y%m%d")

# 주요 거시지표 ----------------------------------------------------------
df_rate  = ecos_series("722Y001", "M", "200901", today)  # 기준금리 :contentReference[oaicite:0]{index=0}
df_cpi   = ecos_series("901Y010", "M", "200901", today)  # CPI (전년동월比) :contentReference[oaicite:1]{index=1}
df_m2    = ecos_series("060Y002", "M", "200901", today)  # M2 통화량 YoY :contentReference[oaicite:2]{index=2}
df_fx    = ecos_series("731Y001", "M", "200901", today)  # 원/달러 환율

# 실질금리 계산 ---------------------------------------------------------
df_macro = df_rate.join([df_cpi, df_m2, df_fx], how="outer")
df_macro["real_rate"] = df_macro["722Y001"] - df_macro["901Y010"]

# ------------------
# 2) 자산 가격
# ------------------
# (a) KODEX 200 ETF
kodex = (
    yf.download("069500.KS", start="2009-01-01")["Adj Close"]
    .rename("KODEX200")
    .to_frame()
)
kodex.index = kodex.index.tz_localize(None)

# (b) KRX 금 현물  ─ “개별종목 시세 추이” 스크래핑
def fetch_krx_gold():
    """
    KRX 정보데이터시스템의 OTP → CSV 다운로드 2단계 방식.
    매일 18:00 이후 종가 기준 1g 가격.
    """
    session = requests.Session()
    otp_url = "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
    payload = {
        "mktId": "KS",              # 금시장
        "trdDd": "",                # '' = 전체기간
        "name": "fileDown",
        "url": "MDC0201060201"      # 금시장 시세 서브화면 ID
    }
    otp = session.post(otp_url, data=payload).text
    down_url = "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
    csv_bytes = session.post(down_url, data={"code": otp}).content
    df = pd.read_csv(io.BytesIO(csv_bytes), encoding="euc-kr")
    df = (
        df.rename(columns={"일자": "date", "종가": "KRX_GOLD"})
        .assign(date=lambda _df: pd.to_datetime(_df["date"]))
        .loc[:, ["date", "KRX_GOLD"]]
        .sort_values("date")
        .set_index("date")
    )
    return df

gold = fetch_krx_gold()            # :contentReference[oaicite:3]{index=3}

# ------------------
# 3) 통합 · 결측치 제거
# ------------------
df_all = (
    df_macro.join([kodex, gold], how="outer")
    .sort_index()
    .ffill()
    .dropna()
)

# ------------------
# 4) 저장
# ------------------
OUT = "data/all_data.csv"
os.makedirs("data", exist_ok=True)
df_all.to_csv(OUT, index=True)
print(f"[✔] Saved {len(df_all):,} rows → {OUT}")
