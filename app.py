import pandas as pd
import streamlit as st
import plotly.express as px

# ── 1. 데이터 로드 ──────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

# 파생 열
if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# ETF 열 → KRX200 대체
if "KRX200" not in df.columns:
    if "KODEX200" in df.columns:
        df.rename(columns={"KODEX200": "KRX200"}, inplace=True)

# ── 2. 기간 슬라이더 ───────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 3. 20·50 MA 신호 계산 ──────────────────────
def ma_sig(series):
    m20, m50 = series.rolling(20).mean(), series.rolling(50).mean()
    diff = m20 - m50
    return diff.apply(lambda x: 1 if x>0 else -1 if x<0 else 0)

sig_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
sig_krx  = ma_sig(view["KRX200"])    if "KRX200"   in view else pd.Series()
sig_fx   = ma_sig(view["FX"])        if "FX"       in view else pd.Series()

def latest(s): return s.iloc[-1] if not s.empty else 0

SIG_C = {1:"#2ecc71", -1:"#e74c3c", 0:"#4d4d4d"}
SIG_T = {1:"비중↑",   -1:"비중↓",   0:"유지"}

# ── 4. 카드 패널 (HTML) ────────────────────────
def card_html(title,val,code):
    color = SIG_C[code]; txt = SIG_T[code]
    vfmt  = f"{val:,.0f}" if val>1_000 else f"{val:,.2f}"
    return f"""
    <div style="background:{color};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{title}</div>
      <div style="font-size:32px;font-weight:700;line-height:1.1;margin:4px 0;">{vfmt}</div>
      <div style="font-size:14px;">{txt} · {sig_dt}</div>
    </div>"""

# ── 5. 세로선 helper ───────────────────────────
def vlines(sig):
    for d,c in sig[sig.shift(1)!=sig].items():
        if c:               # 유지(0) 제외
            yield dict(type="line", x0=d, x1=d, yref="paper", y0=0, y1=1,
                       line=dict(color=SIG_C[c], width=1, dash="dot"), opacity=0.25)

# ── 6. 대시보드 ────────────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

cols = st.columns(3)
if "Gold_KRWg" in view:
    cols[0].markdown(card_html("Gold (원/g)", view["Gold_KRWg"].iloc[-1], latest(sig_gold)),
                     unsafe_allow_html=True)
if "KRX200" in view:
    cols[1].markdown(card_html("KRX 200", view["KRX200"].iloc[-1], latest(sig_krx)),
                     unsafe_allow_html=True)
if "FX" in view:
    cols[2].markdown(card_html("USD/KRW", view["FX"].iloc[-1], latest(sig_fx)),
                     unsafe_allow_html=True)

tab_price, tab_fx, tab_signal = st.tabs(["가격", "환율", "Signal"])

# ── 가격 탭 (Gold / KRX200 개별 그래프) ─────────
with tab_price:
    if "Gold_KRWg" in view.columns:
        fg = px.line(view[["Gold_KRWg"]], title="Gold (원/g)")
        for ln in vlines(sig_gold): fg.add_shape(ln)
        st.plotly_chart(fg, use_container_width=True)

    if "KRX200" in view.columns:
        fk = px.line(view[["KRX200"]], title="KRX 200")
        for ln in vlines(sig_krx): fk.add_shape(ln)
        st.plotly_chart(fk, use_container_width=True)

# ── 환율 탭 ─────────────────────────────────────
with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx = view[["FX"]].assign(MA20=view["FX"].rolling(20).mean(),
                                 MA50=view["FX"].rolling(50).mean())
        ff = px.line(fx, title="USD/KRW 및 이동평균")
        for ln in vlines(sig_fx): ff.add_shape(ln)
        st.plotly_chart(ff, use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

# ── Signal 탭 ───────────────────────────────────
with tab_signal:
    tbl = {k:v for k,v in {
        "Gold": SIG_T[latest(sig_gold)],
        "KRX200": SIG_T[latest(sig_krx)],
        "USD/KRW": SIG_T[latest(sig_fx)]
    }.items() if v!="유지"}
    st.write(f"### 비중 변화 신호 (기준 {sig_dt})")
    st.table(pd.Series(tbl, name="Signal").to_frame() if tbl else pd.Series(dtype=str))

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance — Signals: 20/50 MA cross")
