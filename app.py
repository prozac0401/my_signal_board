import pandas as pd, streamlit as st, plotly.express as px

# ── 1. 데이터 로드 ──────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

# Gold → 원/g
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# ── 2. KODEX200 열 자동 탐지 ────────────────────
def find_kodex(colnames):
    for c in colnames:
        low = c.lower().replace(" ", "")
        if low.startswith("kodex200") or "069500" in low:
            return c
    return None

KDX_COL = find_kodex(df.columns)
if KDX_COL and KDX_COL != "KODEX200":
    df.rename(columns={KDX_COL: "KODEX200"}, inplace=True)
    KDX_COL = "KODEX200"

# ── 3. 기간 슬라이더 ────────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 4. 20·50 MA 교차 신호 ──────────────────────
def ma_sig(s):
    m20, m50 = s.rolling(20).mean(), s.rolling(50).mean()
    return (m20 - m50).apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)

sig_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
sig_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
sig_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

def latest(s): return s.iloc[-1] if not s.empty else 0
COLOR = {1:"#2ecc71", -1:"#e74c3c", 0:"#4d4d4d"}
LABEL = {1:"비중↑",   -1:"비중↓",   0:"유지"}

# ── 5. 카드 HTML ───────────────────────────────
def card(title, val, code):
    bg, tag = COLOR[code], LABEL[code]
    val = f"{val:,.0f}" if val>1_000 else f"{val:,.2f}"
    return f"""
    <div style="background:{bg};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{title}</div>
      <div style="font-size:32px;font-weight:700;margin:4px 0;">{val}</div>
      <div style="font-size:14px;">{tag} · {sig_dt}</div>
    </div>"""

# ── 6. 세로선 helper ───────────────────────────
def vlines(sig):
    for d,c in sig[sig.shift(1)!=sig].items():
        if c:  # 유지 제외
            yield dict(type="line", x0=d, x1=d, yref="paper", y0=0, y1=1,
                       line=dict(color=COLOR[c], width=1, dash="dot"), opacity=0.25)

# ── 7. 대시보드 ─────────────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

cols = st.columns(3)
if "Gold_KRWg" in view:
    cols[0].markdown(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], latest(sig_gold)), unsafe_allow_html=True)
if "KODEX200" in view:
    cols[1].markdown(card("KODEX 200",  view["KODEX200"].iloc[-1],  latest(sig_kdx)),  unsafe_allow_html=True)
if "FX" in view:
    cols[2].markdown(card("USD/KRW",    view["FX"].iloc[-1],        latest(sig_fx)),   unsafe_allow_html=True)

tab_price, tab_kodex, tab_fx, tab_signal = st.tabs(["가격", "KODEX", "환율", "Signal"])

# ── 가격 탭 (Gold / KODEX200) ──────────────────
with tab_price:
    if "Gold_KRWg" in view:
        g_fig = px.line(view[["Gold_KRWg"]], title="Gold (원/g)")
        for l in vlines(sig_gold): g_fig.add_shape(l)
        st.plotly_chart(g_fig, use_container_width=True)

with tab_kodex:
    if "KODEX200" in view:
        k_fig = px.line(view[["KODEX200"]], title="KODEX 200")
        for l in vlines(sig_kdx): k_fig.add_shape(l)
        st.plotly_chart(k_fig, use_container_width=True)
    else:
        st.warning("KODEX 200 가격 열을 찾을 수 없습니다.")

# ── 환율 탭 ────────────────────────────────────
with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx_df = view[["FX"]].assign(MA20=view["FX"].rolling(20).mean(),
                                    MA50=view["FX"].rolling(50).mean())
        f_fig = px.line(fx_df, title="USD/KRW & MA20·50")
        for l in vlines(sig_fx): f_fig.add_shape(l)
        st.plotly_chart(f_fig, use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

# ── Signal 탭 ──────────────────────────────────
with tab_signal:
    table = {k:v for k,v in {
        "Gold": LABEL[latest(sig_gold)],
        "KODEX": LABEL[latest(sig_kdx)],
        "USD/KRW": LABEL[latest(sig_fx)]
    }.items() if v!="유지"}
    st.write(f"### 비중 변화 신호 (기준 {sig_dt})")
    if table:
        st.table(pd.Series(table, name="Signal").to_frame())
    else:
        st.info("최근 비중 변화 신호가 없습니다.")

st.caption("Data sources: FRED · Stooq · ECOS · KRX · Yahoo Finance  |  Signals = 20/50 MA cross")
