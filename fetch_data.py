"""
자동 데이터 수집 · 결측치 제거 · CSV 저장 스크립트
────────────────────────────────────────────
• 한국은행 ECOS → 금리 · CPI · M2 · 환율
• Yahoo Finance → KODEX 200
• KRX 정보데이터 → 금 현물 (1g)
"""

import os, io, datetime as dt, requests, pandas as pd, yfinance as yf
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
ECOS_KEY = os.getenv("ECOS_KEY")
if not ECOS_KEY:
    raise EnvironmentError("❌ ECOS_KEY not found in env / secrets")

def ecos_series(stat_code: str, freq: str, start: str, end: str) -> pd.DataFrame:
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/"
           f"{ECOS_KEY}/json/kr/1/1000/{stat_code}/{freq}/{start}/{end}")
    resp = requests.get(url, timeout=30)
    data = resp.json()

    if "StatisticSearch" not in data:            # ← 오류 응답
        err = data.get("RESULT", {})
        raise RuntimeError(f"ECOS error {err.get('CODE')}: {err.get('MESSAGE')}")

    rows = data["StatisticSearch"]["row"]
    df = (pd.DataFrame(rows)[["TIME", "DATA_VALUE"]]
          .rename(columns={"TIME": "date", "DATA_VALUE": stat_code}))
    df["date"] = pd.to_datetime(df["date"])
    df[stat_code] = pd.to_numeric(df[stat_code], errors="coerce")
    return df.set_index("date")

def fetch_krx_gold() -> pd.DataFrame:
    """KRX 금 현물 (1g) 전기간 시세 CSV 다운로드"""
    sess = requests.Session()
    otp = sess.post(
        "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd",
        data={
            "name": "fileDown",
            "filetype": "csv",
            "url": "MDC0201060201",  # 금시장 시세
        },
        timeout=30,
    ).text
    csv = sess.post(
        "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd",
        data={"code": otp},
        timeout=30,
    ).content
    df = (pd.read_csv(io.BytesIO(csv), encoding="euc-kr")
            .rename(columns={"일자": "date", "종가": "KRX_GOLD"})
            .assign(date=lambda _df: pd.to_datetime(_df["date"]))
            .loc[:, ["date", "KRX_GOLD"]]
            .sort_values("date")
            .set_index("date"))
    return df

def main():
    today = dt.datetime.today().strftime("%Y%m%d")

    # 거시 지표
    rate = ecos_series("722Y001", "M", "200901", today)   # 기준금리
    cpi  = ecos_series("901Y010", "M", "200901", today)   # CPI y/y
    m2   = ecos_series("060Y002", "M", "200901", today)   # M2 y/y
    fx   = ecos_series("731Y001", "M", "200901", today)   # 환율

    macro = rate.join([cpi, m2, fx], how="outer")
    macro["real_rate"] = macro["722Y001"] - macro["901Y010"]

    # 자산 가격
    kodex = (yf.download("069500.KS", start="2009-01-01")["Adj Close"]
                .rename("KODEX200").to_frame())
    kodex.index = kodex.index.tz_localize(None)

    gold = fetch_krx_gold()

    df_all = (macro.join([kodex, gold], how="outer")
                    .sort_index()
                    .ffill()
                    .dropna())

    out_path = Path("data")
    out_path.mkdir(exist_ok=True)
    csv_file = out_path / "all_data.csv"
    df_all.to_csv(csv_file)
    print(f"✔  Saved {len(df_all):,} rows → {csv_file}")

if __name__ == "__main__":
    main()
