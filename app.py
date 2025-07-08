import pandas as pd, streamlit as st, plotly.express as px

# ── HELP 패널 ───────────────────────────────────────────────────
HELP_MD = """
### 💡 M2 통화량 신호 가이드 ( **YoY** 기준 )
| M2 YoY 상태 | 전략적 시사점 |
|-------------|---------------|
| **YoY > 0 🟢** | 유동성 **팽창 재개** → 주식·위험자산 ↑ |
| **YoY ≤ 0 🔴** | 유동성 **둔화/수축** → 리스크 축소·현금 ↑ |

#### ✨ 응용 TIP
| 아이디어 | 설명 |
|----------|------|
| **신호 필터링** | M2 YoY > 0 구간에서만 주식 신호(**KODEX 200**) 채택 → 가짜 반등 회피 |
| **멀티 컨펌** | M2 ↑ + 환율 ↓ + KODEX 200 ↑ **3 신호 동시** → **공격적 비중 확대**<br>M2 ↓ + Gold ↓ 동시 → 안전자산 축소·현금 확보 |
| **모멘텀 지표** | YoY% 자체에 20·50 MA 교차를 돌리면 선행성이 더 높아지기도 함 |
"""

# ── 1. 데이터 로드 ──────────────────────────────
df = (
    pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
      .ffill()
      .loc["2008-01-01":]
)

if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

for c in df.columns:                     # KODEX200 탐지
    if c.lower().replace(" ","").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c:"KODEX200"}, inplace=True); break

if "M2_D" not in df.columns and "M2" in df.columns:    # 즉석 보간
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ── 2. 기간 슬라이더 ────────────────────────────
d0,d1 = df.index.min().date(), df.index.max().date()
d_from,d_to = st.slider("표시 기간", d0, d1, (d0,d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 3. 신호 계산 ────────────────────────────────
def ma_sig(s):
    m20,m50 = s.rolling(20).mean(), s.rolling(50).mean()
    return (m20-m50).apply(lambda x:1 if x>0 else -1 if x<0 else 0)

s_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
s_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
s_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

# M2 → YoY% 신호
if "M2_D" in view:
    month = view["M2_D"].resample("M").last()
    yoy   = (month.pct_change(12)*100).rename("M2_YoY")
    s_m2  = (yoy > 0).astype(int).replace({0:-1})
    s_m2  = s_m2.reindex(view.index, method="ffill").fillna(-1)
else:
    s_m2 = pd.Series()

def last(sig): return sig.iloc[-1] if not sig.empty else 0
COL,TXT = {1:"#2ecc71",-1:"#e74c3c",0:"#4d4d4d"}, {1:"비중↑",-1:"비중↓",0:"유지"}

# ── 4. 카드 ────────────────────────────────────
def card(t,v,code):
    bg,tag = COL[code], TXT[code]
    vfmt = f"{v:,.0f}" if v>1_000 else f"{v:,.2f}"
    return f"""
    <div style="background:{bg};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{t}</div>
      <div style="font-size:32px;font-weight:700;margin:4px 0;">{vfmt}</div>
      <div style="font-size:14px;">{tag} · {sig_dt}</div>
    </div>"""

def vlines(sig):
    for d,c in sig[sig.shift(1)!=sig].items():
        if c in COL:
            yield dict(type="line", x0=d, x1=d, yref="paper", y0=0, y1=1,
                       line=dict(color=COL[c], width=1, dash="dot"), opacity=0.25)

# ── 5. 레이아웃 & HELP ─────────────────────────
st.set_page_config("Macro Dashboard", layout="wide")
st.title("📊 거시 · 자산 대시보드")
with st.sidebar.expander("ℹ️ M2 신호 도움말", False):
    st.markdown(HELP_MD, unsafe_allow_html=True)

c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view: c1.markdown(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], last(s_gold)), unsafe_allow_html=True)
if "KODEX200" in view:  c2.markdown(card("KODEX 200",  view["KODEX200"].iloc[-1],  last(s_kdx)),  unsafe_allow_html=True)
if "FX" in view:        c3.markdown(card("USD/KRW",    view["FX"].iloc[-1],        last(s_fx)),   unsafe_allow_html=True)

tab_gold, tab_kdx, tab_m2, tab_fx, tab_sig = st.tabs(
    ["금 가격","KODEX 200","M2 통화량","환율","Signal"]
)

with tab_gold:
    g = view[["Gold_KRWg"]].assign(MA20=lambda x:x.Gold_KRWg.rolling(20).mean(),
                                   MA50=lambda x:x.Gold_KRWg.rolling(50).mean(),
                                   MA120=lambda x:x.Gold_KRWg.rolling(120).mean())
    fig = px.line(g, title="Gold (원/g) · MA20·50·120")
    for l in vlines(s_gold): fig.add_shape(l)
    st.plotly_chart(fig, use_container_width=True)

with tab_kdx:
    k = view[["KODEX200"]].assign(MA20=lambda x:x.KODEX200.rolling(20).mean(),
                                  MA50=lambda x:x.KODEX200.rolling(50).mean(),
                                  MA120=lambda x:x.KODEX200.rolling(120).mean())
    fig = px.line(k, title="KODEX 200 · MA20·50·120")
    for l in vlines(s_kdx): fig.add_shape(l)
    st.plotly_chart(fig, use_container_width=True)

with tab_m2:
    if "M2_D" in view:
        m = view["M2_D"].resample("M").last().to_frame("M2_M")
        m["MA6"] = m.M2_M.rolling(6).mean(); m["MA12"] = m.M2_M.rolling(12).mean()
        st.plotly_chart(px.line(m, title="M2 월말 값 · MA6·12"), use_container_width=True)

        yoy = (m.M2_M.pct_change(12)*100).rename("YoY%")
        fig = px.bar(yoy, title="M2 YoY 증가율 (%)", opacity=0.4, labels={"value":"%","index":"date"})
        fig.add_scatter(x=m.index, y=m.M2_M, mode="lines", name="M2 (월)", yaxis="y2")
        fig.update_layout(yaxis2=dict(anchor="x", overlaying="y", side="right", showgrid=False))
        for l in vlines(s_m2): fig.add_shape(l)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("M2 데이터가 없습니다.")

with tab_fx:
    fx = view[["FX"]].assign(MA20=view.FX.rolling(20).mean(),
                             MA50=view.FX.rolling(50).mean(),
                             MA120=view.FX.rolling(120).mean())
    fig = px.line(fx, title="USD/KRW · MA20·50·120")
    for l in vlines(s_fx): fig.add_shape(l)
    st.plotly_chart(fig, use_container_width=True)

with tab_sig:
    tbl = {k:v for k,v in {"Gold":TXT[last(s_gold)],
                           "KODEX":TXT[last(s_kdx)],
                           "USD/KRW":TXT[last(s_fx)],
                           "M2 YoY":TXT[last(s_m2)]}.items() if v!="유지"}
    st.write(f"### 비중 변화 신호 (기준 {sig_dt})")
    st.table(pd.Series(tbl, name="Signal").to_frame() if tbl else pd.Series(dtype=str))

st.caption("Data: FRED · Stooq · ECOS · Yahoo Finance — Signals = M2 YoY & MA cross")
