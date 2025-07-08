# app.py – Streamlit Dashboard (date-range selectable)
# ────────────────────────────────────────────────────
import pandas as pd
import streamlit as st
import plotly.express as px

# 1) 데이터 로드 ────────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])          # ↤ 2008 이후로 기본 절단

# Gold → 원/g 환산
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# ETF 열 이름 통일
etf = "KODEX200" if "KODEX200" in df.columns else "069500.KS"
if etf != "KODEX200" and etf in df.columns:
    df.rename(columns={etf: "KODEX200"}, inplace=True)

# 거래량 열 목록
vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# 2) 날짜 범위 슬라이더 ────────────────────────
min_date, max_date = df.index.min(), df.index.max()
date_range = st.slider(
    "표시할 기간 선택",
    min_value=min_date.date(),
    max_value=max_date.date(),
    value=(min_date.date(), max_date.date()),
    format="YYYY-MM-DD",
)
start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
view = df.loc[start:end]

# 3) 간단 신호 (20/50 MA) ───────────────────────
def cross(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    if ma20.isna().iloc[-1] or ma50.isna().iloc[-1]:
        return "⚫"
    prev, curr = ma20.sub(ma50).iloc[-2], ma20.sub(ma50).iloc[-1]
    return "🟢" if prev < 0 < curr else "🔴" if prev > 0 > curr else "⚫"

sig_gold = cross(view["Gold_KRWg"]) if "Gold_KRWg" in view else "⚫"

# 4) 대시보드 ──────────────────────────────────
st.set_page_config(page_title="Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량 대시보드")

m1, m2, m3 = st.columns(3)
if "Gold_KRWg" in view:
    m1.metric("Gold (원/g)", f"{view['Gold_KRWg'].iloc[-1]:,.0f}", sig_gold)
if "KODEX200" in view:
    m2.metric("KODEX 200",   f"{view['KODEX200'].iloc[-1]:,.0f}")
if "FX" in view:
    m3.metric("USD/KRW",     f"{view['FX'].iloc[-1]:,.2f}")

tab_price, tab_macro = st.tabs(["가격 추이", "거시·거래량"])

with tab_price:
    cols = [c for c in ["Gold_KRWg", "KODEX200"] if c in view.columns]
    if cols:
        st.plotly_chart(px.line(view[cols], title="Gold (원/g) · KODEX 200"), use_container_width=True)

with tab_macro:
    macro_cols = [c for c in ["FX", "M2"] if c in view.columns]
    if macro_cols:
        st.plotly_chart(px.line(view[macro_cols], title="거시 지표 (FX · M2)"), use_container_width=True)

    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 월별 거래량"), use_container_width=True)
    else:
        st.info("수원 거래량 데이터가 아직 없습니다 (K-REB 서버 차단 등).")

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance  |  © 2025")
