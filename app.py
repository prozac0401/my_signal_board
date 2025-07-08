# app.py
import streamlit as st, pandas as pd
import plotly.express as px

CSV_PATH = "data/all_data.csv"
df = pd.read_csv(CSV_PATH, parse_dates=["date"]).set_index("date")

# -------- 신호 계산 함수 --------
def compute_signals(d):
    sig = {}
    # 금
    sig["gold_buy"]  = (d["real_rate"].iloc[-1] < 0) and (d["real_rate"].iloc[-2] >= 0)
    sig["gold_sell"] = (d["real_rate"].iloc[-1] > 0) and (d["real_rate"].iloc[-2] <= 0)
    # ETF
    m2_yoy  = d["060Y002"].pct_change(12).iloc[-1]*100
    pbr     = 1.15  # ← 외부 밸류 DB 연동 권장, 예시는 임시 상수
    sig["etf_buy"]  = (m2_yoy > 0) and (pbr < 1.0)
    sig["etf_sell"] = (m2_yoy < 0) and (pbr > 1.2)
    # 부동산 (거래·미분양 DB 연동 필요, 예시는 더미)
    sig["rea_buy"]  = False
    sig["rea_sell"] = False
    return sig

signals = compute_signals(df)

# -------- Streamlit UI ----------
st.set_page_config(layout="wide")
st.title("📈 거시지표 기반 신호판 대시보드")

col1, col2, col3 = st.columns(3)
def lamp(flag): return "🟢" if flag else "🔴"

col1.metric("KRX 금",  f"{df['KRX_GOLD'].iloc[-1]:,.0f}₩/g", lamp(signals['gold_buy']))
col2.metric("KODEX 200", f"{df['KODEX200'].iloc[-1]:,.0f}₩",   lamp(signals['etf_buy']))
col3.metric("경기남부 부동산", "—",                              lamp(signals['rea_buy']))

# 가격 추이
tab1, tab2 = st.tabs(["금·ETF", "거시지표"])
with tab1:
    fig = px.line(df[["KRX_GOLD", "KODEX200"]], title="자산 가격 추이")
    st.plotly_chart(fig, use_container_width=True)
with tab2:
    fig2 = px.line(df[["real_rate", "060Y002", "731Y001"]], title="거시 변수")
    st.plotly_chart(fig2, use_container_width=True)

st.caption("데이터: 한국은행 ECOS, KRX 정보데이터시스템, Yahoo Finance") 
