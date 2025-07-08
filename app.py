"""
app.py – Streamlit  Dashboard  (2025‑07)
──────────────────────────────────────────
• 주요 메트릭 : Gold (원/g 환산), KODEX200, USD/KRW
• 가격 탭    : Gold·KODEX 라인 차트
• 거시 탭    : FX·M2 라인, 수원4구 거래량 라인
• 간단 신호  : 20일‑50일 골든/데드 크로스 (Gold_KRWg)
"""

import pandas as pd, streamlit as st, plotly.express as px

CSV = "data/all_data.csv"

# ───── 데이터 로드 ─────
df = pd.read_csv(CSV, index_col=0, parse_dates=True).ffill()

# Gold → 원/g 환산 (1oz = 31.1035 g)
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# ───── 간단 트리거(골든/데드 크로스) ─────
def gold_signal(series):
    ma20 = series.rolling(20).mean()
    ma50 = series.rolling(50).mean()
    prev, curr = (ma20 - ma50).iloc[-2], (ma20 - ma50).iloc[-1]
    if pd.isna(prev) or pd.isna(curr):
        return "⚫"
    return "🟢" if prev < 0 and curr > 0 else "🔴" if prev > 0 and curr < 0 else "⚫"

sig_gold = gold_signal(df["Gold_KRWg"]) if "Gold_KRWg" in df else "⚫"

# ───── UI ─────
st.set_page_config(page_title="Macro + Suwon Dashboard", layout="wide")
st.title("📊 거시·자산·수원 거래량 대시보드")

m1, m2, m3 = st.columns(3)
m1.metric("Gold (원/g)",  f"{df['Gold_KRWg'].iloc[-1]:,.0f}", sig_gold)
m2.metric("KODEX 200",    f"{df['KODEX200'].iloc[-1]:,.0f}")
m3.metric("USD/KRW",      f"{df['FX'].iloc[-1]:,.2f}")

tab1, tab2 = st.tabs(["가격 추이", "거시·거래량"])

with tab1:
    fig = px.line(df[["Gold_KRWg", "KODEX200"]],
                  title="Gold (원/g) · KODEX200 추이")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    cols_to_plot = [c for c in ["FX", "M2"] if c in df.columns]
    if cols_to_plot:
        fig2 = px.line(df[cols_to_plot], title="거시 지표 (FX · M2)")
        st.plotly_chart(fig2, use_container_width=True)

    vol_cols = [c for c in df.columns if c.startswith("Vol_")]
    if vol_cols:
        fig3 = px.line(df[vol_cols], title="수원 4구 월별 거래량")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("K‑REB 거래량 데이터가 아직 없습니다 (서버 차단 등).")

st.caption("데이터: FRED · Stooq · ECOS · 부동산원 · Yahoo Finance")
