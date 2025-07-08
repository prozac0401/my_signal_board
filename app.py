import pandas as pd, streamlit as st, plotly.express as px

# ── 데이터 로드 ─────────────────────────────────
df = (
    pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
      .ffill()
      .loc["2008-01-01":]
)

if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# KODEX200 열 탐색
for c in df.columns:
    if c.lower().replace(" ", "").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c: "KODEX200"}, inplace=True)
        break

# ── 기간 슬라이더 ───────────────────────────────
start, end = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", start, end, (start, end), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(d_from) : pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 신호(20·50 MA 교차) ─────────────────────────
def ma_sig(s):
    m20, m50 = s.rolling(20).mean(), s.rolling(50).mean()
    return (m20 - m50).apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)

s_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
s_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
s_m2   = ma_sig(view["M2_D"])      if "M2_D"      in view else pd.Series()
s_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

def last(sig): return sig.iloc[-1] if not sig.empty else 0
COL = {1:"#2ecc71", -1:"#e74c3c", 0:"#4d4d4d"}
TXT = {1:"비중↑",   -1:"비중↓",   0:"유지"}

# ── 카드 UI ────────────────────────────────────
def card(title, val, code):
    bg = COL[code]; tag = TXT[code]
    val_fmt = f"{val:,.0f}" if val > 1_000 else f"{val:,.2f}"
    return f"""
    <div style="background:{bg};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{title}</div>
      <div style="font-size:32px;font-weight:700;margin:4px 0;">{val_fmt}</div>
      <div style="font-size:14px;">{tag} · {sig_dt}</div>
    </div>"""

# ── 세로선 helper ──────────────────────────────
def vlines(sig):
    for d, c in sig[sig.shift(1) != sig].items():
        if c:
            yield dict(type="line", x0=d, x1=d, yref="paper", y0=0, y1=1,
                       line=dict(color=COL[c], width=1, dash="dot"), opacity=0.25)

# ── 대시보드 ───────────────────────────────────
st.set_page_config("Macro Dashboard", layout="wide")
st.title("📊 거시 · 자산 대시보드")

c1, c2, c3, c4 = st.columns(4)
if "Gold_KRWg" in view:
    c1.markdown(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], last(s_gold)), unsafe_allow_html=True)
if "KODEX200" in view:
    c2.markdown(card("KODEX 200",  view["KODEX200"].iloc[-1],  last(s_kdx)),  unsafe_allow_html=True)
if "M2_D" in view:
    c3.markdown(card("M2 통화량",   view["M2_D"].iloc[-1],      last(s_m2)),   unsafe_allow_html=True)
if "FX" in view:
    c4.markdown(card("USD/KRW",    view["FX"].iloc[-1],        last(s_fx)),   unsafe_allow_html=True)

tab_gold, tab_kodex, tab_m2, tab_fx, tab_signal = st.tabs(
    ["금 가격", "KODEX 200", "M2 통화량", "환율", "Signal"]
)

with tab_gold:
    if "Gold_KRWg" in view:
        fig = px.line(view[["Gold_KRWg"]], title="Gold (원/g)")
        for l in vlines(s_gold): fig.add_shape(l)
        st.plotly_chart(fig, use_container_width=True)

with tab_kodex:
    if "KODEX200" in view:
        fig = px.line(view[["KODEX200"]], title="KODEX 200")
        for l in vlines(s_kdx): fig.add_shape(l)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("KODEX 200 가격 열을 찾을 수 없습니다.")

with tab_m2:
    if "M2_D" in view:
        fig = px.line(view[["M2_D"]], title="M2 통화량 (일 보간)")
        for l in vlines(s_m2): fig.add_shape(l)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("M2 데이터가 없습니다.")

with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx = view[["FX"]].assign(MA20=view["FX"].rolling(20).mean(),
                                 MA50=view["FX"].rolling(50).mean())
        fig = px.line(fx, title="USD/KRW & MA20·50")
        for l in vlines(s_fx): fig.add_shape(l)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

with tab_signal:
    tbl = {k:v for k,v in {
        "Gold":   TXT[last(s_gold)],
        "KODEX":  TXT[last(s_kdx)],
        "M2":     TXT[last(s_m2)],
        "USD/KRW":TXT[last(s_fx)],
    }.items() if v!="유지"}
    st.write(f"### 비중 변화 신호 (기준 {sig_dt})")
    if tbl:
        st.table(pd.Series(tbl, name="Signal").to_frame())
    else:
        st.info("최근 비중 변화 신호가 없습니다.")

st.caption("Data: FRED · Stooq · ECOS · Yahoo Finance — Signals = 20/50 MA cross")
