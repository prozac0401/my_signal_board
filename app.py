import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# ── 1. 데이터 로드 ────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

# 파생 열
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035
if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS": "KODEX200"}, inplace=True)
vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ── 2. 기간 슬라이더 ──────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")          # ★ 기준일

# ── 3. 신호 계산 (20·50일 MA 교차) ─────────────
def ma_signal(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    diff = ma20 - ma50
    return diff.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)

sig_gold = ma_signal(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
sig_kdx  = ma_signal(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
sig_fx   = ma_signal(view["FX"])        if "FX"        in view else pd.Series()

SIG_C   = {1: "#0B6623", -1: "#8B0000"}        # ↑🟢 , ↓🔴
SIG_TXT = {1: "비중↑",   -1: "비중↓"}

def last_code(s): return s.iloc[-1] if not s.empty else 0

# ── 4. 카드 UI ───────────────────────────────
def card(title, value, code, fmt):
    color = SIG_C.get(code, "#4d4d4d")          # 유지→회색
    fig = go.Figure()
    # 제목·값
    fig.add_annotation(x=0.02, y=0.85, xanchor="left",
                       text=f"<b>{title}</b>", showarrow=False,
                       font=dict(size=16, color="white"))
    fig.add_annotation(x=0.5,  y=0.4, text=f"{value:{fmt}}",
                       showarrow=False, font=dict(size=34, color="white"))
    # 신호 라벨
    if code:
        fig.add_annotation(x=0.98, y=0.85, xanchor="right",
                           text=f"{SIG_TXT[code]}<br>"
                                f"<span style='font-size:12px'>{sig_dt}</span>",
                           showarrow=False, font=dict(size=14, color="white"))
    fig.update_layout(height=190, paper_bgcolor=color,
                      margin=dict(l=8,r=8,t=8,b=8))
    return fig

# ── 5. 세로줄 (유지 제외) ───────────────────────
def vlines(sig_series):
    for dt_, code in sig_series[sig_series.shift(1) != sig_series].items():
        if code:     # 유지(0) skip
            yield dict(type="line", x0=dt_, x1=dt_, yref="paper", y0=0, y1=1,
                       line=dict(color=SIG_C[code], width=2, dash="dot"))

# ── 6. 대시보드 ────────────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view:
    c1.plotly_chart(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1],
                         last_code(sig_gold), ",.0f"), use_container_width=True)
if "KODEX200" in view:
    c2.plotly_chart(card("KODEX 200",   view["KODEX200"].iloc[-1],
                         last_code(sig_kdx), ",.0f"),  use_container_width=True)
if "FX" in view:
    c3.plotly_chart(card("USD/KRW",     view["FX"].iloc[-1],
                         last_code(sig_fx), ",.2f"),   use_container_width=True)

tab_price, tab_macro, tab_fx, tab_sig = st.tabs(["가격", "거시·거래량", "환율", "Signal"])

# 가격 탭
with tab_price:
    cols = [c for c in ["Gold_KRWg","KODEX200"] if c in view.columns]
    if cols:
        fig = px.line(view[cols], title="Gold (원/g) · KODEX 200")
        for ln in vlines(sig_gold): fig.add_shape(ln)
        for ln in vlines(sig_kdx):  fig.add_shape(ln)
        st.plotly_chart(fig, use_container_width=True)

# 거시·거래량 탭
with tab_macro:
    mc = [c for c in ["Rate","M2","DXY","Bond10"] if c in view.columns]
    if mc: st.plotly_chart(px.line(view[mc], title="거시 지표"), use_container_width=True)
    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 거래량"), use_container_width=True)

# 환율 탭
with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx = view[["FX"]].copy()
        fx["MA20"], fx["MA50"] = fx["FX"].rolling(20).mean(), fx["FX"].rolling(50).mean()
        fig_fx = px.line(fx, title="USD/KRW & MA20·50")
        for ln in vlines(sig_fx): fig_fx.add_shape(ln)
        st.plotly_chart(fig_fx, use_container_width=True)
    elif "DXY" in view:
        st.plotly_chart(px.line(view[["DXY"]], title="DXY 달러지수"), use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

# Signal 탭
with tab_sig:
    sigs = {k:v for k,v in {
        "Gold":     SIG_TXT.get(last_code(sig_gold)),
        "KODEX200": SIG_TXT.get(last_code(sig_kdx)),
        "USD/KRW":  SIG_TXT.get(last_code(sig_fx)),
    }.items() if v}
    st.write(f"### 최근 비중 변경 신호 (기준일: {sig_dt})")
    if sigs:
        st.table(pd.Series(sigs, name="Signal").to_frame())
    else:
        st.info("최근 기간에 비중 확대·축소 신호가 없습니다.")

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance — 20/50 MA Cross Signals")
