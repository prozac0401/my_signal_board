"""
app.py  –  Streamlit 대시보드 (금·주식·통화 + 금리·10Y 추가)
────────────────────────────────────────────
* 데이터 소스: fetch_data.py 가 생성한 data/all_data.csv (일간)
* 탭 구성
  1) 금 가격        – XAU/USD, KRW 환산, MA20
  2) KODEX200        – ETF 가격, MA20
  3) M2 통화량·YoY   – M2_D, 전년동월 대비 %, 3M SMA
  4) 환율            – USD/KRW, DXY 동시 시각화
  5) 금리·10Y (NEW) – 기준금리 & 10년물, 3M SMA
  6) Signal          – (사용자 정의 신호)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

# ── 설정 ──────────────────────────────────────
st.set_page_config(page_title="Macro & Market Dashboard", layout="wide")
DATA_PATH = Path("data/all_data.csv")

# ── 데이터 로드 ───────────────────────────────
@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
    df.index.name = "Date"
    return df

view = load_data()

# ── 유틸: 카드 렌더러 ─────────────────────────
COL = {1: "#d62728", 0: "#6c757d", -1: "#1f77b4"}  # 빨강·회색·파랑

def card(label: str, value: float, code: int = 0) -> str:
    color = COL.get(code, "#6c757d")
    return f"""<div style='border-left:6px solid {color}; padding:0.5rem 0.75rem; margin-right:1rem'>
                <span style='font-size:0.8rem; color:#888'>{label}</span><br>
                <span style='font-size:1.4rem; font-weight:600'>{value:,.2f}</span>
              </div>"""

# ── 탭 구성 ────────────────────────────────────
tab_gold, tab_kdx, tab_m2, tab_fx, tab_rate, tab_sig = st.tabs(
    ["금 가격", "KODEX 200", "M2 통화량·YoY", "환율", "금리·10Y", "Signal"]
)

# 1) 금 가격 탭 --------------------------------------------------------------
with tab_gold:
    if {"Gold", "FX"}.issubset(view.columns):
        g = view[["Gold", "FX"]].copy()
        g["Gold_KRWg"] = g.Gold * g.FX / 31.1035  # 1oz = 31.1035g
        g = g[["Gold_KRWg"]].assign(MA20=lambda x: x.Gold_KRWg.rolling(20).mean())
        fig = px.line(g, y=g.columns, title="Gold Price (KRW/gram)")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(card("Gold (KRW/g)", g.Gold_KRWg.iloc[-1]), unsafe_allow_html=True)
    else:
        st.info("Gold 또는 FX 데이터가 없습니다.")

# 2) KODEX200 탭 ------------------------------------------------------------
with tab_kdx:
    if "KODEX200" in view.columns:
        k = view[["KODEX200"]].assign(MA20=lambda x: x.KODEX200.rolling(20).mean())
        fig = px.line(k, y=k.columns, title="KODEX 200 ETF")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(card("KODEX200", k.KODEX200.iloc[-1]), unsafe_allow_html=True)
    else:
        st.info("KODEX200 데이터가 없습니다.")

# 3) M2 탭 -------------------------------------------------------------------
with tab_m2:
    if "M2_D" in view.columns:
        m = view[["M2_D"]].copy()
        m["YoY%"] = m.M2_D.pct_change(252) * 100
        m["YoY_MA3"] = m["YoY%"].rolling(63).mean()
        fig = px.line(m, y=["YoY%", "YoY_MA3"], title="M2 YoY % (3M SMA)")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(card("M2 YoY%", m["YoY%"].iloc[-1]), unsafe_allow_html=True)
    else:
        st.info("M2 데이터가 없습니다.")

# 4) 환율 탭 ------------------------------------------------------------------
with tab_fx:
    if {"FX", "DXY"}.issubset(view.columns):
        f = view[["FX", "DXY"]]
        fig = px.line(f, y=f.columns, title="USD/KRW & DXY")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(card("USD/KRW", f.FX.iloc[-1]), unsafe_allow_html=True)
    else:
        st.info("FX 또는 DXY 데이터가 없습니다.")

# 5) 금리·10Y 탭 (NEW) -------------------------------------------------------
with tab_rate:
    if {"Rate", "Bond10"}.issubset(view.columns):
        r = view[["Rate", "Bond10"]].copy()
        r["Rate_MA3"]   = r.Rate.rolling(3).mean()
        r["Bond10_MA3"] = r.Bond10.rolling(3).mean()
        fig = px.line(
            r,
            y=["Rate", "Rate_MA3", "Bond10", "Bond10_MA3"],
            title="🇰🇷 기준금리 vs 10년물 국채수익률 · 3M SMA",
            labels={"value": "%", "variable": ""},
        )
        st.plotly_chart(fig, use_container_width=True)
        col1, col2 = st.columns(2)
        col1.markdown(card("기준금리 (%)",  r.Rate.iloc[-1]),   unsafe_allow_html=True)
        col2.markdown(card("10Y 수익률 (%)", r.Bond10.iloc[-1]), unsafe_allow_html=True)
    else:
        st.info("Rate 또는 Bond10 데이터가 없습니다.")

# 6) Signal 탭 (placeholder) --------------------------------------------------
with tab_sig:
    st.write("Signal 탭은 추후 구현 예정입니다.")
