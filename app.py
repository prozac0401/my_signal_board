import pandas as pd, streamlit as st, plotly.express as px

# ───── 데이터 준비 ─────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

# 변환: Gold 원/g, ETF 열 통일
if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035
if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS":"KODEX200"}, inplace=True)

vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ───── 슬라이더 (기간 선택) ─────
d_min, d_max = df.index.min().date(), df.index.max().date()
date_from, date_to = st.slider("기간 선택", d_min, d_max, (d_min, d_max), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(date_from):pd.to_datetime(date_to)]

# ───── 신호 함수 ─────
def ma_sig(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    if ma20.isna().iloc[-1] or ma50.isna().iloc[-1]: return "·"
    prev, curr = ma20.sub(ma50).iloc[-2], ma20.sub(ma50).iloc[-1]
    return "🟢" if prev < 0 < curr else "🔴" if prev > 0 > curr else "⚫"

signals = {
    "Gold":   ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else "·",
    "KODEX":  ma_sig(view["KODEX200"])  if "KODEX200"  in view else "·",
    "FX":     ma_sig(view["FX"])        if "FX"        in view else "·",
}

# ───── 스트림릿 레이아웃 ─────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

# 메트릭
c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view: c1.metric("Gold (원/g)", f"{view['Gold_KRWg'].iloc[-1]:,.0f}", signals["Gold"])
if "KODEX200" in view:  c2.metric("KODEX 200",   f"{view['KODEX200'].iloc[-1]:,.0f}", signals["KODEX"])
if "FX" in view:        c3.metric("USD/KRW",     f"{view['FX'].iloc[-1]:,.2f}",        signals["FX"])

tab_price, tab_macro, tab_fx, tab_sig = st.tabs(["가격", "거시·거래량", "환율", "Signal"])

with tab_price:
    cols = [c for c in ["Gold_KRWg","KODEX200"] if c in view.columns]
    st.plotly_chart(px.line(view[cols], title="가격 추이"), use_container_width=True)

with tab_macro:
    macro_cols = [c for c in ["Rate","M2","DXY","Bond10"] if c in view.columns]
    if macro_cols:
        st.plotly_chart(px.line(view[macro_cols], title="거시 지표"), use_container_width=True)
    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 거래량"), use_container_width=True)

with tab_fx:
    if "FX" in view:
        fx_df = view[["FX"]].copy()
        fx_df["MA20"] = fx_df["FX"].rolling(20).mean()
        fx_df["MA50"] = fx_df["FX"].rolling(50).mean()
        st.plotly_chart(px.line(fx_df, title="USD/KRW & MA20·50"), use_container_width=True)
    else:
        st.info("FX 데이터 없음")

with tab_sig:
    st.write("### 20·50일 이동평균 교차 신호")
    st.table(pd.Series(signals, name="Signal").to_frame())

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance")
