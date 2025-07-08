import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

CSV_PATH = Path("data/all_data.csv")

# CSV 없으면 fetch_data.py 호출(1회용)
if not CSV_PATH.exists():
    import fetch_data  # noqa: F401 (실행만)

df = pd.read_csv(CSV_PATH, parse_dates=["date"]).set_index("date")

# ───── 신호 계산 ─────
def compute_signals(d: pd.DataFrame) -> dict:
    sig = {}
    # 금
    sig["gold_buy"]  = (d["real_rate"].iloc[-1] < 0) and (d["real_rate"].iloc[-2] >= 0)
    sig["gold_sell"] = (d["real_rate"].iloc[-1] > 0) and (d["real_rate"].iloc[-2] <= 0)
    # ETF (단순 예시, M2 모멘텀)
    m2_mom = d["060Y002"].iloc[-1] - d["060Y002"].iloc[-2]
    sig["etf_buy"]  = m2_mom > 0
    sig["etf_sell"] = m2_mom < 0
    return sig

signals = compute_signals(df)
lamp = lambda x: "🟢" if x else "🔴"

# ───── Streamlit 화면 ─────
st.set_page_config(page_title="Macro Signal Board", layout="wide")
st.title("📈 거시지표 기반 신호판")

col1, col2 = st.columns(2)
col1.metric("KRX 금(₩/g)", f"{df['KRX_GOLD'].iloc[-1]:,.0f}", lamp(signals["gold_buy"]))
col2.metric("KODEX 200(₩)", f"{df['KODEX200'].iloc[-1]:,.0f}", lamp(signals["etf_buy"]))

tab1, tab2 = st.tabs(["가격 추이", "거시 지표"])
with tab1:
    st.plotly_chart(px.line(df[["KRX_GOLD", "KODEX200"]]), use_container_width=True)
with tab2:
    st.plotly_chart(px.line(df[["real_rate", "060Y002", "731Y001"]]), use_container_width=True)

st.caption("데이터: 한국은행 ECOS · KRX · Yahoo Finance")
