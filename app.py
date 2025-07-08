import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ── 1. 데이터 로드 ──────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

# 추가 파생열
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035
if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS": "KODEX200"}, inplace=True)
vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ── 2. 기간 선택 슬라이더 ───────────────────────
d_min, d_max = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("기간 선택", d_min, d_max, (d_min, d_max), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_date = view.index[-1].strftime("%Y-%m-%d")  # ★ 신호 계산 기준일

# ── 3. MA 교차 신호 계산 ────────────────────────
def ma_cross(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    if ma20.isna().iloc[-1] or ma50.isna().iloc[-1]:
        return 0
    prev, curr = ma20.sub(ma50).iloc[-2], ma20.sub(ma50).iloc[-1]
    return 1 if prev < 0 < curr else -1 if prev > 0 > curr else 0

sig_map = {1: ("비중↑", "#006400"), -1: ("비중↓", "#8B0000"), 0: ("유지", "#808080")}
sg_gold  = ma_cross(view["Gold_KRWg"]) if "Gold_KRWg" in view else 0
sg_kdx   = ma_cross(view["KODEX200"])  if "KODEX200"  in view else 0
sg_fx    = ma_cross(view["FX"])        if "FX"        in view else 0

# ── 4. 카드 생성 함수 ───────────────────────────
def make_card(title, value, sig_code, fmt):
    label, color = sig_map[sig_code]
    return go.Figure(go.Indicator(
        mode   ="number",
        value  = value,
        number = {"font":{"size":34,"color":"white"}, "valueformat":fmt},
        title  = {"text":f"<span style='font-size:20px'><b>{title}</b>"
                         f"<br>{label}  <span style='font-size:14px'>({sig_date})</span></span>",
                  "font":{"color":"white"}},
        domain = {"x":[0,1],"y":[0,1]}
    )).update_layout(height=200, paper_bgcolor=color,
                     margin=dict(t=25,b=0,l=0,r=0))

# ── 5. 대시보드 레이아웃 ────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

col1, col2, col3 = st.columns(3)
if "Gold_KRWg" in view:
    col1.plotly_chart(make_card("Gold (원/g)",
                                view["Gold_KRWg"].iloc[-1], sg_gold, ",.0f"),
                      use_container_width=True)
if "KODEX200" in view:
    col2.plotly_chart(make_card("KODEX 200",
                                view["KODEX200"].iloc[-1], sg_kdx, ",.0f"),
                      use_container_width=True)
if "FX" in view:
    col3.plotly_chart(make_card("USD/KRW",
                                view["FX"].iloc[-1], sg_fx, ",.2f"),
                      use_container_width=True)

tab_price, tab_macro, tab_fx, tab_sig = st.tabs(
    ["가격", "거시·거래량", "환율", "Signal"])

# 가격 탭
with tab_price:
    pc = [c for c in ["Gold_KRWg","KODEX200"] if c in view.columns]
    if pc:
        st.plotly_chart(px.line(view[pc], title="Gold (원/g) · KODEX 200"), use_container_width=True)

# 거시·거래량 탭
with tab_macro:
    mc = [c for c in ["Rate","M2","DXY","Bond10"] if c in view.columns]
    if mc:
        st.plotly_chart(px.line(view[mc], title="거시 지표"), use_container_width=True)
    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 거래량"), use_container_width=True)

# 환율 탭
with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx_df = view[["FX"]].copy()
        fx_df["MA20"] = fx_df["FX"].rolling(20).mean()
        fx_df["MA50"] = fx_df["FX"].rolling(50).mean()
        st.plotly_chart(px.line(fx_df, title="USD/KRW & MA20·50"), use_container_width=True)
    elif "DXY" in view:
        st.plotly_chart(px.line(view[["DXY"]], title="DXY 달러지수"), use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

# Signal 탭
with tab_sig:
    st.write(f"### 20·50일 이동평균 교차 신호 — 기준일: **{sig_date}**")
    st.table(pd.Series({
        "Gold":     sig_map[sg_gold][0],
        "KODEX200": sig_map[sg_kdx][0],
        "USD/KRW":  sig_map[sg_fx][0],
    }, name="Signal").to_frame())

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance  |  Signals based on 20/50 MA crossing")
