import pandas as pd, streamlit as st, plotly.express as px, plotly.graph_objects as go

# ── 데이터 읽기 ────────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035
if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS":"KODEX200"}, inplace=True)

# ── 슬라이더 & 뷰 ──────────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 신호 계산 (20·50 MA) ───────────────────────
def ma_sig(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    diff = ma20 - ma50
    return diff.apply(lambda x: 1 if x>0 else -1 if x<0 else 0)

sig_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
sig_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
sig_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

SIG_C = {1:"#2ECC71", -1:"#E74C3C"}         # ↑🟢, ↓🔴
SIG_T = {1:"비중↑",   -1:"비중↓"}

def last_code(s): return s.iloc[-1] if not s.empty else 0

# ── 카드(패널) ────────────────────────────────
def signal_panel(label, code):
    if code==0: return None                      # 유지면 카드 자체 제거
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=1, y1=1,
                  fillcolor=SIG_C[code], line=dict(color=SIG_C[code]))
    fig.add_annotation(x=0.5, y=0.5,
                       text=f"<b>{label}</b><br><span style='font-size:14px'>{sig_dt}</span>",
                       showarrow=False, font=dict(size=32, color="white"),
                       xref="paper", yref="paper")
    fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
    fig.update_layout(height=120, margin=dict(l=0,r=0,t=0,b=0))
    return fig

# ── 레이아웃 ───────────────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

panels = []
if "Gold_KRWg" in view: panels.append(signal_panel("Gold",   last_code(sig_gold)))
if "KODEX200" in view:  panels.append(signal_panel("KODEX",  last_code(sig_kdx)))
if "FX" in view:        panels.append(signal_panel("USD/KRW",last_code(sig_fx)))

# 동적 열: 유지(0) 제거 후 남은 패널만
cols = st.columns(len(panels)) if panels else []
for col, pan in zip(cols, panels):
    col.plotly_chart(pan, use_container_width=True)

tab_price, tab_fx, tab_signal = st.tabs(["가격", "환율", "Signal"])

# ── 세로줄 함수 ────────────────────────────────
def vlines(sig_series):
    chg = sig_series[sig_series.shift(1)!=sig_series]
    for date, code in chg.items():
        if code:
            yield dict(type="line", x0=date, x1=date, yref="paper", y0=0, y1=1,
                       line=dict(color=SIG_C[code], width=2, dash="dot"))

# 가격 탭
with tab_price:
    price_cols = [c for c in ["Gold_KRWg","KODEX200"] if c in view.columns]
    if price_cols:
        fig = px.line(view[price_cols], title="Gold (원/g) · KODEX 200")
        for ln in vlines(sig_gold): fig.add_shape(ln)
        for ln in vlines(sig_kdx):  fig.add_shape(ln)
        st.plotly_chart(fig, use_container_width=True)

# 환율 탭
with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx = view[["FX"]].copy()
        fx["MA20"], fx["MA50"] = fx["FX"].rolling(20).mean(), fx["FX"].rolling(50).mean()
        fig_fx = px.line(fx, title="USD/KRW & MA20·50")
        for ln in vlines(sig_fx): fig_fx.add_shape(ln)
        st.plotly_chart(fig_fx, use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

# Signal 탭
with tab_signal:
    sig_tbl = {k:v for k,v in {
        "Gold":  SIG_T.get(last_code(sig_gold)),
        "KODEX": SIG_T.get(last_code(sig_kdx)),
        "USD/KRW": SIG_T.get(last_code(sig_fx)),
    }.items() if v}
    st.write(f"### 비중 변경 신호 (기준일 {sig_dt})")
    if sig_tbl:
        st.table(pd.Series(sig_tbl, name="Signal").to_frame())
    else:
        st.info("해당 구간에 비중 변경 신호가 없습니다.")

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance | Signals = 20/50 MA crossing")
