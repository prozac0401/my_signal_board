import pandas as pd
import streamlit as st
import plotly.express as px

# ╭──── HELP 패널 ────╮
HELP_MD = """
### M2 YoY 4-단계 구간
| 구간 | 해석 | 시사점 |
|------|------|-------|
| **> 9 %**  • 팽창 | 평균 + 0.5 σ↑ | 리스크-온 (주식·부동산 확대) |
| **6 – 9 %** • 완충 | 평균 부근 | 중립 · 추세 확인 |
| **3 – 6 %** • 둔화 | 평균 – 1 σ↑ | 경계 · 리밸런스 |
| **< 3 %** • 수축 | 평균 – 1 σ↓ | 리스크-오프 (현금·단기채 확대) |

#### 응용 TIP
| 아이디어 | 설명 |
|----------|------|
| **신호 필터링** | M2 YoY > 9 % 구간일 때만 주식 신호(**KODEX 200**) 채택 → 가짜 반등 회피 |
| **멀티 컨펌** | M2 팽창(> 9 %) + 환율 ↓ + KODEX 200 ↑ → 공격적 비중 확대<br>M2 수축(< 3 %) + Gold ↓ → 안전자산 축소·현금 확보 |
| **모멘텀 결합** | ‘팽창’ 구간이면서 M2 YoY 20 EMA 위·기울기 상승일 때만 리스크-온 |
"""

# ── 1. 데이터 로드 ──────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

for c in df.columns:                   # KODEX200 매핑
    if c.lower().replace(" ", "").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c: "KODEX200"}, inplace=True)
        break

if "M2_D" not in df.columns and "M2" in df.columns:  # 일 보간
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ── 2. 기간 슬라이더 ───────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 3. 자산 신호 ───────────────────────────────
def ma_sig(s):
    m20, m50 = s.rolling(20).mean(), s.rolling(50).mean()
    return (m20 - m50).apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)

s_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
s_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
s_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

# ── 4. M2 YoY 4-단계 신호 ──────────────────────
if "M2_D" in view:
    m = view["M2_D"].resample("M").last()
    yoy = (m.pct_change(12) * 100).rename("YoY")
    def cls(x):
        if pd.isna(x): return -1
        if x >  9: return  2
        if x >= 6: return  1
        if x >= 3: return -1
        return -2
    s_m2 = yoy.apply(cls).reindex(view.index, method="ffill")
else:
    s_m2 = pd.Series()

# ── 5. 색상·라벨 ───────────────────────────────
COL = {2:"#16a085", 1:"#2ecc71", -1:"#f39c12", -2:"#e74c3c"}
TXT = {2:"팽창", 1:"완충", -1:"둔화", -2:"수축"}
def last(sig): return sig.iloc[-1] if not sig.empty else -1

def card(t,v,code):
    bg, tag = COL.get(code,"#95a5a6"), TXT.get(code,"—")
    val = f"{v:,.0f}" if v > 1_000 else f"{v:,.2f}"
    return f"""<div style="background:{bg};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{t}</div>
      <div style="font-size:32px;font-weight:700;margin:4px 0;">{val}</div>
      <div style="font-size:14px;">{tag} · {sig_dt}</div></div>"""

def vlines(sig):
    for d,c in sig[sig.shift(1)!=sig].items():
        if c in COL:
            yield dict(type="line", x0=d, x1=d, yref="paper", y0=0, y1=1,
                       line=dict(color=COL[c], width=1, dash="dot"), opacity=0.25)

# ── 6. 레이아웃 & HELP ────────────────────────
st.set_page_config("Macro Dashboard", layout="wide")
st.title("거시 · 자산 대시보드")
with st.sidebar.expander("M2 YoY 도움말", False):
    st.markdown(HELP_MD, unsafe_allow_html=True)

# 카드
c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view: c1.markdown(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], last(s_gold)), unsafe_allow_html=True)
if "KODEX200" in view:  c2.markdown(card("KODEX 200",   view["KODEX200"].iloc[-1],  last(s_kdx)),  unsafe_allow_html=True)
if "FX" in view:        c3.markdown(card("USD/KRW",     view["FX"].iloc[-1],        last(s_fx)),   unsafe_allow_html=True)

# ── 7. 섹션 선택 (라디오) ──────────────────────
section = st.radio(
    "그래프·표 선택",
    ("금 가격", "KODEX 200", "M2 통화량·YoY", "환율", "Signal"),
    horizontal=True
)

# 금 그래프
if section == "금 가격" and "Gold_KRWg" in view:
    g = view[["Gold_KRWg"]].assign(
        MA20=lambda x: x.Gold_KRWg.rolling(20).mean(),
        MA50=lambda x: x.Gold_KRWg.rolling(50).mean(),
        MA120=lambda x: x.Gold_KRWg.rolling(120).mean()
    )
    fig = px.line(g, title="Gold (원/g) · MA20·50·120")
    for ln in vlines(s_gold): fig.add_shape(ln)
    st.plotly_chart(fig, use_container_width=True)

# KODEX 그래프
elif section == "KODEX 200" and "KODEX200" in view:
    k = view[["KODEX200"]].assign(
        MA20=lambda x: x.KODEX200.rolling(20).mean(),
        MA50=lambda x: x.KODEX200.rolling(50).mean(),
        MA120=lambda x: x.KODEX200.rolling(120).mean()
    )
    fig = px.line(k, title="KODEX 200 · MA20·50·120")
    for ln in vlines(s_kdx): fig.add_shape(ln)
    st.plotly_chart(fig, use_container_width=True)

# M2 그래프
elif section == "M2 통화량·YoY" and "M2_D" in view:
    m = view["M2_D"].resample("M").last().to_frame("M2_M")
    m["MA6"] = m.M2_M.rolling(6).mean()
    m["MA12"] = m.M2_M.rolling(12).mean()
    yoy = (m.M2_M.pct_change(12)*100).rename("YoY %")

    fig = px.bar(yoy, title="M2 YoY (%)  +  월말 M2 · MA6·12", opacity=0.45)
    fig.add_scatter(x=m.index, y=m.M2_M,  name="M2 월말", yaxis="y2", mode="lines")
    fig.add_scatter(x=m.index, y=m.MA6,   name="MA6",     yaxis="y2", mode="lines")
    fig.add_scatter(x=m.index, y=m.MA12,  name="MA12",    yaxis="y2", mode="lines")
    fig.update_layout(
        yaxis=dict(title="YoY %"),
        yaxis2=dict(anchor="x", overlaying="y", side="right", showticklabels=False),
        legend=dict(x=0.02,y=0.98))
    for ln in vlines(s_m2): fig.add_shape(ln)
    st.plotly_chart(fig, use_container_width=True)

# 환율 그래프
elif section == "환율" and "FX" in view and view["FX"].notna().any():
    fx = view[["FX"]].assign(
        MA20=view.FX.rolling(20).mean(),
        MA50=view.FX.rolling(50).mean(),
        MA120=view.FX.rolling(120).mean()
    )
    fig = px.line(fx, title="USD/KRW · MA20·50·120")
    for ln in vlines(s_fx): fig.add_shape(ln)
    st.plotly_chart(fig, use_container_width=True)

# Signal 표
elif section == "Signal":
    sig_dict = {
        "Gold":    TXT.get(last(s_gold), ""),
        "KODEX":   TXT.get(last(s_kdx), ""),
        "USD/KRW": TXT.get(last(s_fx), ""),
        "M2 YoY":  TXT.get(last(s_m2), "")
    }
    tbl = {k: v for k, v in sig_dict.items() if v}
    st.subheader(f"비중 변화 신호 (기준 {sig_dt})")
    st.table(pd.Series(tbl, name="Signal").to_frame() if tbl else pd.Series(dtype=str))

st.caption("Data : FRED · Stooq · ECOS · Yahoo Finance")