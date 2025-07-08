# app.py – Robust ver. ETF 열 이름 자동 대응
import pandas as pd, streamlit as st, plotly.express as px

CSV = "data/all_data.csv"
df = pd.read_csv(CSV, index_col=0, parse_dates=True).ffill()

# ── 1. 열 이름 보정 ──────────────────────────
# Gold USD/oz → 원/g
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# ETF: KODEX 200  (fetch_data가 'KODEX200' 또는 '069500.KS' 둘 중 하나로 저장)
etf_col = "KODEX200" if "KODEX200" in df.columns else "069500.KS" if "069500.KS" in df.columns else None
if etf_col and etf_col != "KODEX200":
    df.rename(columns={etf_col: "KODEX200"}, inplace=True)

# 수원 거래량 열(Vol_) 존재 여부 확인
vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ── 2. 간단 신호 (Gold 20/50 MA 크로스) ─────────
def cross(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    if ma20.isna().iloc[-1] or ma50.isna().iloc[-1]: return "⚫"
    prev, curr = ma20.sub(ma50).iloc[-2], ma20.sub(ma50).iloc[-1]
    return "🟢" if prev < 0 < curr else "🔴" if prev > 0 > curr else "⚫"

sig_gold = cross(df["Gold_KRWg"]) if "Gold_KRWg" in df else "⚫"

# ── 3. Streamlit UI ───────────────────────────
st.set_page_config(page_title="Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량 대시보드")

m1, m2, m3 = st.columns(3)

if "Gold_KRWg" in df:
    m1.metric("Gold (원/g)", f"{df['Gold_KRWg'].iloc[-1]:,.0f}", sig_gold)
if "KODEX200" in df:
    m2.metric("KODEX 200",    f"{df['KODEX200'].iloc[-1]:,.0f}")
if "FX" in df:
    m3.metric("USD/KRW",      f"{df['FX'].iloc[-1]:,.2f}")

tab_price, tab_macro = st.tabs(["가격 추이", "거시·거래량"])

with tab_price:
    price_cols = [c for c in ["Gold_KRWg", "KODEX200"] if c in df.columns]
    if price_cols:
        st.plotly_chart(px.line(df[price_cols], title="Gold (원/g) · KODEX 200"), use_container_width=True)
    else:
        st.info("가격 데이터가 충분하지 않습니다.")

with tab_macro:
    macro_cols = [c for c in ["FX", "M2"] if c in df.columns]
    if macro_cols:
        st.plotly_chart(px.line(df[macro_cols], title="거시 지표 (FX · M2)"), use_container_width=True)

    if vol_cols:
        st.plotly_chart(px.line(df[vol_cols], title="수원 4구 월별 거래량"), use_container_width=True)
    else:
        st.info("수원 거래량 데이터가 아직 없습니다 (K-REB 서버 차단 등).")

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance  |  © 2025")
