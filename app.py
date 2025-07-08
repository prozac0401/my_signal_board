import pandas as pd
import streamlit as st
import plotly.express as px

# ── 1. 데이터 로드 ──────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

# Gold → 원/g
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# ETF 열 통일
if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS": "KODEX200"}, inplace=True)

vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ── 2. 날짜 슬라이더 ────────────────────────
start_def, end_def = df.index.min(), df.index.max()
d_from, d_to = st.slider(
    "기간 선택", min_value=start_def.date(), max_value=end_def.date(),
    value=(start_def.date(), end_def.date()), format="YYYY-MM-DD"
)
view = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]

# ── 3. 신호 계산 ────────────────────────────
def ma_cross_signal(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    if ma20.isna().iloc[-1] or ma50.isna().iloc[-1]:
        return "·"
    prev, curr = ma20.sub(ma50).iloc[-2], ma20.sub(ma50).iloc[-1]
    return "🟢" if prev < 0 < curr else "🔴" if prev > 0 > curr else "⚫"

signals = {
    "Gold (원/g)":  ma_cross_signal(view["Gold_KRWg"])  if "Gold_KRWg" in view else "·",
    "KODEX 200":    ma_cross_signal(view["KODEX200"])   if "KODEX200"   in view else "·",
    "USD/KRW":      ma_cross_signal(view["FX"])         if "FX"         in view else "·",
}

# ── 4. 대시보드 ─────────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량 대시보드")

# 메트릭 카드
m1, m2, m3 = st.columns(3)
if "Gold_KRWg" in view:
    m1.metric("Gold (원/g)", f"{view['Gold_KRWg'].iloc[-1]:,.0f}", signals["Gold (원/g)"])
if "KODEX200" in view:
    m2.metric("KODEX 200",   f"{view['KODEX200'].iloc[-1]:,.0f}", signals["KODEX 200"])
if "FX" in view:
    m3.metric("USD/KRW",     f"{view['FX'].iloc[-1]:,.2f}",       signals["USD/KRW"])

tab_price, tab_macro, tab_fx, tab_signal = st.tabs(
    ["가격 추이", "거시·거래량", "환율(FX)", "Signal"])

# 가격 탭
with tab_price:
    cols = [c for c in ["Gold_KRWg", "KODEX200"] if c in view.columns]
    if cols:
        st.plotly_chart(px.line(view[cols], title="Gold (원/g) · KODEX 200"), use_container_width=True)

# 거시·거래량 탭
with tab_macro:
    if {"FX","M2"}.intersection(view.columns):
        st.plotly_chart(px.line(view[[c for c in ["FX","M2"] if c in view.columns]],
                         title="거시 지표"), use_container_width=True)
    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 월별 거래량"), use_container_width=True)

# FX 전용 탭
with tab_fx:
    if "FX" in view:
        fx_plot = view["FX"].to_frame()
        fx_plot["MA20"] = fx_plot["FX"].rolling(20).mean()
        fx_plot["MA50"] = fx_plot["FX"].rolling(50).mean()
        st.plotly_chart(px.line(fx_plot, title="USD/KRW 및 이동평균"), use_container_width=True)
    else:
        st.warning("환율 데이터가 없습니다.")

# Signal 탭
with tab_signal:
    st.write("### 단기 추세 신호 (20일 vs 50일 MA)")
    st.table(pd.Series(signals, name="신호").to_frame())

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance  |  © 2025")
