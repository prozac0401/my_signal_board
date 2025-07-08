import pandas as pd, streamlit as st, plotly.express as px

# ── 데이터 로드 ────────────────────────────────
df = (
    pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
      .ffill()
      .loc["2008-01-01":]
)

if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# KODEX200 열 탐색
kodex_col = next((c for c in df.columns if c.lower().replace(" ","").startswith("kodex200") or "069500" in c.lower()), None)
if kodex_col and kodex_col != "KODEX200":
    df.rename(columns={kodex_col:"KODEX200"}, inplace=True)

# ── 기간 슬라이더 ──────────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 20·50 MA 신호 ────────────────────────────
def ma_sig(s):  # 1=↑, -1=↓, 0=유지
    m20, m50 = s.rolling(20).mean(), s.rolling(50).mean()
    return (m20-m50).apply(lambda x:1 if x>0 else -1 if x<0 else 0)

sig_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
sig_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
sig_m2   = ma_sig(view["M2_D"])      if "M2_D"      in view else pd.Series()
sig_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

def latest(s): return s.iloc[-1] if not s.empty else 0
COL = {1:"#2ecc71", -1:"#e74c3c", 0:"#4d4d4d"}
TXT = {1:"비중↑",   -1:"비중↓",   0:"유지"}

# ── 카드 HTML ─────────────────────────────────
def card(title,val,code):
    bg, tag = COL[code], TXT[code]
    val_fmt = f"{val:,.0f}" if val>1_000 else f"{val:,.2f}"
    return f"""
    <div style="background:{bg};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{title}</div>
      <div style="font-size:32px;font-weight:700;margin:4px 0;">{val_fmt}</div>
      <div style="font-size:14px;">{tag} · {sig_dt}</div>
    </div>"""

# ── 세로선 helper ─────────────────────────────
def vlines(sig):
    for d,c in sig[sig.shift(1)!=sig].items():
        if c:
            yield dict(type="line", x0=d, x1=d, yref="paper", y0=0, y1=1,
                       line=dict(color=COL[c], width=1, dash="dot"), opacity=0.25)

# ── 대시보드 헤더 ─────────────────────────────
st.set_page_config("Macro Dashboard", layout="wide")
st.title("📊 거시 · 자산 대시보드")

c1,c2,c3,c4 = st.columns(4)
if "Gold_KRWg" in view:
    c1.markdown(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], latest(sig_gold)), unsafe_allow_html=True)
if "KODEX200" in view:
    c2.markdown(card("KODEX 200",  view["KODEX200"].iloc[-1],  latest(sig_kdx)),  unsafe_allow_html=True)
if "M2_D" in view:
    c3.markdown(card("M2 통화량",   view["M2_D"].iloc[-1],      latest(sig_m2)),   unsafe_allow_html=True)
if "FX" in view:
    c4.markdown(card("USD/KRW",    view["FX"].iloc[-1],        latest(sig_fx)),   unsafe_allow_html=True)

