import numpy as np                                    # ★ NEW
import pandas as pd, streamlit as st, plotly.express as px

# ── HELP 패널 ───────────────────────────────────────────────────
HELP_MD = """
### M2 YoY 4-단계 구간
| 구간 | 해석 | 시사점 |
|------|------|-------|
| **> 9 %** • 팽창 | 평균 + 0.5 σ 이상 | 리스크-온 (주식·부동산 확대) |
| **6 – 9 %** • 완충 | 평균 부근 | 중립 · 추세 확인 |
| **3 – 6 %** • 둔화 | 평균 – 1 σ 이상 | 경계 · 리밸런스 |
| **< 3 %** • 수축 | 평균 – 1 σ 이하 | 리스크-오프 (현금·단기채 확대) |

#### 응용 TIP
| 아이디어 | 설명 |
|----------|------|
| **신호 필터링** | M2 YoY > 9 % 구간에서만 KODEX 200 신호 채택 → 가짜 반등 회피 |
| **멀티 컨펌** | M2 팽창 + 환율 ↓ + KODEX 200 ↑ → **공격적 비중 확대**<br>M2 수축 + Gold ↓ → 안전자산 축소·현금 확보 |
| **모멘텀 결합** | ‘팽창’이면서 M2 YoY 20 EMA 위 && 기울기 상승일 때만 리스크-온 |
"""

# ── 1. 데이터 로드 ──────────────────────────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"]*df["FX"]/31.1035

for c in df.columns:
    if c.lower().replace(" ","").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c:"KODEX200"}, inplace=True); break

if "M2_D" not in df.columns and "M2" in df.columns:
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ── 2. 기간 슬라이더 ───────────────────────────────────────────
d0,d1 = df.index.min().date(), df.index.max().date()
d_from,d_to = st.slider("표시 기간", d0, d1, (d0,d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 3. 자산별 가격 “추세 점수”  (-2 … +2) ─────────────────────── ★ NEW
def trend_score(series, short=20, long=50):
    ma_s, ma_l = series.rolling(short).mean(), series.rolling(long).mean()
    cross  = np.sign(ma_s - ma_l)                # -1 / 0 / +1
    mom_1m = np.sign(series.pct_change(21))      # -1 / 0 / +1
    return (cross + mom_1m).clip(-2, 2)

trend = {}
if "Gold_KRWg" in view: trend["Gold"]   = trend_score(view["Gold_KRWg"])
if "KODEX200"  in view: trend["KODEX"]  = trend_score(view["KODEX200"])
if "FX"        in view: trend["USDKRW"] = trend_score(view["FX"])

# ── 4. 매크로 레짐 점수 (-3 … +3) ────────────────────────────── ★ NEW
macro = pd.Series(0, index=view.index)

# 4-A) M2 YoY 4-단계  (-2 … +2)
if "M2_D" in view:
    month = view["M2_D"].resample("M").last()
    m2_yoy = (month.pct_change(12)*100).rename("M2_YoY")
    def m2_cls(x):
        if pd.isna(x): return -1
        if x>9: return 2
        if x>=6: return 1
        if x>=3: return -1
        return -2
    m2_score = m2_yoy.apply(m2_cls).reindex(view.index, method="ffill")
    macro = macro.add(m2_score, fill_value=0)

# 4-B) 장-단 스프레드  (+1 / 0 / -1)
if {"Rate","Bond10"}.issubset(view.columns):
    spread = (view["Bond10"] - view["Rate"]).rolling(5).mean()
    spread_score = spread.apply(lambda x: 1 if x>0.5 else -1 if x<0 else 0)
    macro = macro.add(spread_score, fill_value=0)

macro = macro.clip(-3, 3)

# ── 5. 최종 시그널  (-3 … +3)  &  색·라벨 ─────────────────── ★ NEW
def last(s): return s.iloc[-1] if not s.empty else np.nan

SIG_COL = { 3:"#198754", 2:"#28c76f", 1:"#6c757d", 0:"#6c757d",
           -1:"#6c757d",-2:"#ff9f43",-3:"#dc3545"}
SIG_TXT = { 3:"Strong Buy", 2:"Buy", 1:"Neutral +", 0:"Neutral",
           -1:"Neutral –",-2:"Sell",-3:"Strong Sell"}

def card_sig(asset, score):
    clr  = SIG_COL.get(score, "#95a5a6")
    lbl  = SIG_TXT.get(score, "N/A")
    return f"""
    <div style="background:{clr};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
        <div style="font-size:18px;font-weight:600;">{asset}</div>
        <div style="font-size:32px;font-weight:700;margin:4px 0;">{lbl}</div>
        <div style="font-size:14px;opacity:.8;">{sig_dt}</div>
    </div>"""

# ── 6. 기존 가격·MoM 카드 (방향성) ──────────────────────────────
COL_PRICE = { 2:"#16a085", 1:"#2ecc71", -1:"#f39c12", -2:"#e74c3c", 0:"#95a5a6"}
TXT_PRICE = { 2:"↑", 1:"↑", -1:"↓", -2:"↓", 0:"유지"}

def price_card(t,v,code):
    return f"""<div style="background:{COL_PRICE[code]};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
      <div style="font-size:18px;font-weight:600;">{t}</div>
      <div style="font-size:32px;font-weight:700;margin:4px 0;">{v:,.0f}</div>
      <div style="font-size:14px;">{TXT_PRICE[code]} · {sig_dt}</div></div>"""

# ── 7. 레이아웃 & HELP ─────────────────────────────────────────
st.set_page_config("Macro Dashboard", layout="wide")
st.title("📊 거시 · 자산 대시보드")
with st.sidebar.expander("ℹ️ M2 YoY 도움말", False):
    st.markdown(HELP_MD, unsafe_allow_html=True)

# ── 8. 가격 카드 (Top) ─────────────────────────────────────────
c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view: c1.markdown(price_card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], int(last(trend.get("Gold", pd.Series())))), unsafe_allow_html=True)
if "KODEX200" in view:  c2.markdown(price_card("KODEX 200",   view["KODEX200"].iloc[-1],  int(last(trend.get("KODEX", pd.Series())))),  unsafe_allow_html=True)
if "FX" in view:        c3.markdown(price_card("USD/KRW",     view["FX"].iloc[-1],        int(last(trend.get("USDKRW", pd.Series())))), unsafe_allow_html=True)

# ── 9. 탭 ───────────────────────────────────────────────────────
tab_gold, tab_kdx, tab_m2, tab_fx, tab_rate, tab_sig = st.tabs(
    ["금 가격", "KODEX 200", "M2 통화량·YoY", "환율", "금리·10Y", "Signal"]
)

# 1) 금 가격 탭 --------------------------------------------------------------
with tab_gold:
    g = view[["Gold_KRWg"]].assign(MA20=lambda x:x.Gold_KRWg.rolling(20).mean(),
                                   MA50=lambda x:x.Gold_KRWg.rolling(50).mean(),
                                   MA120=lambda x:x.Gold_KRWg.rolling(120).mean())
    fig = px.line(g, title="Gold (원/g) · MA20·50·120")
    for l in vlines(s_gold): fig.add_shape(l)
    st.plotly_chart(fig, use_container_width=True)

# 2) KODEX200 탭 ------------------------------------------------------------
with tab_kdx:
    k = view[["KODEX200"]].assign(MA20=lambda x:x.KODEX200.rolling(20).mean(),
                                  MA50=lambda x:x.KODEX200.rolling(50).mean(),
                                  MA120=lambda x:x.KODEX200.rolling(120).mean())
    fig = px.line(k, title="KODEX 200 · MA20·50·120")
    for l in vlines(s_kdx): fig.add_shape(l)
    st.plotly_chart(fig, use_container_width=True)

# 3) M2 탭 -------------------------------------------------------------------
# ── M2: 월값·MA6·12 + YoY% 합친 하나의 그래프 ────────────────
with tab_m2:
    if "M2_D" in view:
        m = view["M2_D"].resample("M").last().to_frame("M2_M")
        m["MA6"]  = m.M2_M.rolling(6).mean()
        m["MA12"] = m.M2_M.rolling(12).mean()
        yoy = (m.M2_M.pct_change(12)*100).rename("YoY%")

        fig = px.bar(yoy, title="M2 YoY (%)  +  월말 M2 · MA6·12", opacity=0.45,
                     labels={"value":"YoY %","index":"date"})

        # 월말 M2 + MA6·12 (눈금 숨김)
        fig.add_scatter(x=m.index, y=m.M2_M,  name="M2 월말",  yaxis="y2", mode="lines")
        fig.add_scatter(x=m.index, y=m.MA6,   name="MA6",      yaxis="y2", mode="lines")
        fig.add_scatter(x=m.index, y=m.MA12,  name="MA12",     yaxis="y2", mode="lines")

        fig.update_layout(
            yaxis=dict(title="YoY %"),
            yaxis2=dict(anchor="x", overlaying="y", side="right",
                        showticklabels=False, title=None),
            legend=dict(x=0.02,y=0.98),
        )
        for l in vlines(s_m2): fig.add_shape(l)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("M2 데이터가 없습니다.")

# 4) 환율 탭 ------------------------------------------------------------------
with tab_fx:
    fx = view[["FX"]].assign(MA20=view.FX.rolling(20).mean(),
                             MA50=view.FX.rolling(50).mean(),
                             MA120=view.FX.rolling(120).mean())
    fig = px.line(fx, title="USD/KRW · MA20·50·120")
    for l in vlines(s_fx): fig.add_shape(l)
    st.plotly_chart(fig, use_container_width=True)

# 5) 금리·10Y 탭 (NEW) -------------------------------------------------------
# ── 5) 금리·10Y 탭 ─────────────────────────────
with tab_rate:
    if {"Rate", "Bond10"}.issubset(view.columns):
        r = view[["Rate", "Bond10"]].copy()

        # ① 기준금리는 그대로 3-일 SMA 유지
        r["Rate_MA3"] = r.Rate.rolling(3).mean()

        # ② Bond10은 3-‘개월’ SMA (월말 데이터 가정)
        bond_m = r["Bond10"].resample("M").last()
        r["Bond10_MA3M"] = bond_m.rolling(3).mean().reindex(r.index, method="ffill")

        fig = px.line(
            r,
            y=["Rate", "Rate_MA3", "Bond10", "Bond10_MA3M"],
            labels={"value": "%", "variable": ""},
            title="🇰🇷 기준금리 vs 10Y 국채수익률 · 3일·3개월 SMA"
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── 카드용 마지막 “유효” 값 ────────────────────────
        rate_last  = r["Rate"].dropna().iloc[-1]   if not r["Rate"].dropna().empty else None
        bond_last  = r["Bond10"].dropna().iloc[-1] if not r["Bond10"].dropna().empty else None

        col1, col2 = st.columns(2)
        col1.markdown(card("기준금리 (%)",   rate_last, 0),  unsafe_allow_html=True)
        col2.markdown(card("10Y 수익률 (%)", bond_last, 0), unsafe_allow_html=True)
    else:
        st.info("Rate 또는 Bond10 데이터가 없습니다.")

# 6) Signal 탭  ------------------------------------------------------------- ★ NEW
with tab_sig:
    final_scores = {}
    for asset, ts in trend.items():
        combined = (ts + macro).clip(-3, 3)
        final_scores[asset] = int(last(combined))
    # 부동산 신호 예시 (월간 YoY 3개월 모멘텀)
    if "RTMS" in view:
        realty_trend = view["RTMS"].pct_change(3).apply(
            lambda x: 2 if x>0.03 else 1 if x>0 else -1 if x>-0.03 else -2
        )
        final_scores["Realty"] = int(last((realty_trend + macro).clip(-3,3)))

    st.write(f"### 통합 자산 시그널  (기준 {sig_dt})")
    if final_scores:
        cols = st.columns(len(final_scores))
        for (asset,score),col in zip(final_scores.items(), cols):
            col.markdown(card_sig(asset, score), unsafe_allow_html=True)
    else:
        st.info("시그널을 계산할 데이터가 부족합니다.")

st.caption("Data: FRED · Stooq · ECOS · Yahoo Finance — Signals = Macro(M2 + Spread) × Trend")
