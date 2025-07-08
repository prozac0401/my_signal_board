import pandas as pd, streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# ── 1. 데이터 로드 & 전처리 ────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035
if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS": "KODEX200"}, inplace=True)

vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ── 2. 기간 선택 ───────────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]

# ── 3. 신호 계산 (20·50MA 교차) ────────────────
def ma_signal(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    diff = ma20 - ma50
    signal = diff.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
    return signal

sig_gold  = ma_signal(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
sig_kdx   = ma_signal(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
sig_fx    = ma_signal(view["FX"])        if "FX"        in view else pd.Series()

SIG_COLOR = {1: "#0B6623", -1: "#8B0000", 0: "#808080"}
SIG_TEXT  = {1: "비중↑",   -1: "비중↓",    0: "유지"}

def last_sig(sig_series):
    return sig_series.iloc[-1] if not sig_series.empty else 0

# ── 4. 카드 컴포넌트 (좌·중·우 영역) ───────────
def make_card(title, value, sig_series, fmt):
    sig_code = last_sig(sig_series)
    label, color = SIG_TEXT[sig_code], SIG_COLOR[sig_code]
    fig = go.Figure()
    # 왼쪽: 자산명
    fig.add_annotation(x=0.01, y=0.5, xanchor="left",
                       text=f"<b>{title}</b>", showarrow=False,
                       font=dict(size=18, color="white"))
    # 중앙: 값
    txt_val = f"{value:,.0f}" if fmt==",.0f" else f"{value:,.2f}"
    fig.add_annotation(x=0.5, y=0.5, text=txt_val,
                       showarrow=False, font=dict(size=36, color="white"))
    # 오른쪽: 신호 & 날짜
    date_txt = sig_series.index[-1].strftime("%Y-%m-%d") if not sig_series.empty else "-"
    fig.add_annotation(x=0.99, y=0.5, xanchor="right",
                       text=f"{label}<br><span style='font-size:12px'>{date_txt}</span>",
                       showarrow=False, font=dict(size=16, color="white"))
    fig.update_layout(height=210, paper_bgcolor=color,
                      margin=dict(l=10, r=10, t=10, b=10))
    return fig

# ── 5. 세로줄 그리기용 함수 ────────────────────
def signal_vlines(sig_series):
    changes = sig_series[sig_series.shift(1) != sig_series]
    lines = []
    for date, code in changes.items():
        lines.append(dict(type="line",
                          x0=date, x1=date, yref="paper", y0=0, y1=1,
                          line=dict(color=SIG_COLOR[code], width=2, dash="dot")))
    return lines

# ── 6. 대시보드 UI ────────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

c1, c2, c3 = st.columns(3)
if "Gold_KRWg" in view:
    c1.plotly_chart(make_card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], sig_gold, ",.0f"),
                    use_container_width=True)
if "KODEX200" in view:
    c2.plotly_chart(make_card("KODEX 200",   view["KODEX200"].iloc[-1],  sig_kdx,  ",.0f"),
                    use_container_width=True)
if "FX" in view:
    c3.plotly_chart(make_card("USD/KRW",     view["FX"].iloc[-1],        sig_fx,   ",.2f"),
                    use_container_width=True)

tab_price, tab_macro, tab_fx, tab_sig = st.tabs(["가격", "거시·거래량", "환율", "Signal"])

with tab_price:
    pc = [c for c in ["Gold_KRWg","KODEX200"] if c in view.columns]
    if pc:
        fig = px.line(view[pc], title="Gold (원/g) · KODEX 200")
        # 세로선
        for ln in signal_vlines(sig_gold):  fig.add_shape(ln)
        for ln in signal_vlines(sig_kdx):   fig.add_shape(ln)
        st.plotly_chart(fig, use_container_width=True)

with tab_macro:
    mc = [c for c in ["Rate","M2","DXY","Bond10"] if c in view.columns]
    if mc:
        st.plotly_chart(px.line(view[mc], title="거시 지표"), use_container_width=True)
    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 거래량"), use_container_width=True)

with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx = view[["FX"]].copy()
        fx["MA20"], fx["MA50"] = fx["FX"].rolling(20).mean(), fx["FX"].rolling(50).mean()
        fig_fx = px.line(fx, title="USD/KRW & MA20·50")
        for ln in signal_vlines(sig_fx): fig_fx.add_shape(ln)
        st.plotly_chart(fig_fx, use_container_width=True)
    elif "DXY" in view:
        st.plotly_chart(px.line(view[["DXY"]], title="DXY 달러지수"), use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

with tab_sig:
    st.write("### 20·50일 이동평균 교차 신호")
    st.table(pd.Series({
        "Gold":     SIG_TEXT[last_sig(sig_gold)],
        "KODEX200": SIG_TEXT[last_sig(sig_kdx)],
        "USD/KRW":  SIG_TEXT[last_sig(sig_fx)],
    }, name=f"({sig_dt})").to_frame())

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance  |  Signals = 20/50 MA crossing")
