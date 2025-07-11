import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px   # 남겨 두면 추후 확장·테마 적용 시 편리

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
df = (
    pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
    .ffill()
    .loc["2008-01-01":]
)

if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

for c in df.columns:
    if c.lower().replace(" ", "").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c: "KODEX200"}, inplace=True)
        break

if "M2_D" not in df.columns and "M2" in df.columns:
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ── 2. 기간 슬라이더 ───────────────────────────────────────────
d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.slider("표시 기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(d_from) : pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 3. 자산별 가격 “추세 점수”  (-2 … +2) ───────────────────────
def trend_score(series, short: int = 20, long: int = 50):
    """Cross + 1‑개월 모멘텀 스코어 (‑2 … +2)"""
    ma_s, ma_l = series.rolling(short).mean(), series.rolling(long).mean()
    cross = np.sign(ma_s - ma_l)  # -1 / 0 / +1
    mom_1m = np.sign(series.pct_change(21))  # -1 / 0 / +1
    return (cross + mom_1m).clip(-2, 2)

trend = {}
if "Gold_KRWg" in view:
    trend["Gold"] = trend_score(view["Gold_KRWg"])
if "KODEX200" in view:
    trend["KODEX"] = trend_score(view["KODEX200"])
if "FX" in view:
    trend["USDKRW"] = trend_score(view["FX"])

# 기존 변수와의 호환성 유지
s_gold = trend.get("Gold", pd.Series(dtype=float))
s_kdx = trend.get("KODEX", pd.Series(dtype=float))
s_fx = trend.get("USDKRW", pd.Series(dtype=float))

# ── 4. 매크로 레짐 점수 (-3 … +3) ──────────────────────────────
macro = pd.Series(0, index=view.index)

# 4‑A) M2 YoY 구간 점수 (‑2 … +2)
if "M2_D" in view:
    month = view["M2_D"].resample("M").last()
    m2_yoy = (month.pct_change(12) * 100).rename("M2_YoY")

    def m2_cls(x):
        if pd.isna(x):
            return -1
        if x > 9:
            return 2
        if x >= 6:
            return 1
        if x >= 3:
            return -1
        return -2

    m2_score = m2_yoy.apply(m2_cls).reindex(view.index, method="ffill")
    macro = macro.add(m2_score, fill_value=0)
    s_m2 = m2_score  # 외부 노출용
else:
    s_m2 = pd.Series(dtype=float)

# 4‑B) 장‑단 스프레드 (+1 / 0 / ‑1)
if {"Rate", "Bond10"}.issubset(view.columns):
    spread = (view["Bond10"] - view["Rate"]).rolling(5).mean()
    spread_score = spread.apply(lambda x: 1 if x > 0.5 else -1 if x < 0 else 0)
    macro = macro.add(spread_score, fill_value=0)

macro = macro.clip(-3, 3)

# ── 5. 시각·색 팔레트 ─────────────────────────────────────────
SIG_COL = {
    3: "#198754",
    2: "#28c76f",
    1: "#6c757d",
    0: "#6c757d",
    -1: "#6c757d",
    -2: "#ff9f43",
    -3: "#dc3545",
}
SIG_TXT = {
    3: "Strong Buy",
    2: "Buy",
    1: "Neutral +",
    0: "Neutral",
    -1: "Neutral –",
    -2: "Sell",
    -3: "Strong Sell",
}

COL_PRICE = {2: "#16a085", 1: "#2ecc71", -1: "#f39c12", -2: "#e74c3c", 0: "#95a5a6"}
TXT_PRICE = {2: "↑", 1: "↑", -1: "↓", -2: "↓", 0: "유지"}

COL_LINE = {2: "#16a085", 1: "#2ecc71", -1: "#f39c12", -2: "#e74c3c"}

# ── 6. 유틸리티 ───────────────────────────────────────────────
def last(s: pd.Series):
    return s.iloc[-1] if not s.empty else np.nan


def card_sig(asset: str, score: int) -> str:
    clr = SIG_COL.get(score, "#95a5a6")
    lbl = SIG_TXT.get(score, "N/A")
    return f"""
    <div style="background:{clr};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
        <div style="font-size:18px;font-weight:600;">{asset}</div>
        <div style="font-size:32px;font-weight:700;margin:4px 0;">{lbl}</div>
        <div style="font-size:14px;opacity:.8;">{sig_dt}</div>
    </div>"""


def price_card(t: str, v: float, code: int) -> str:
    return f"""
    <div style="background:{COL_PRICE[code]};border-radius:8px;padding:20px 12px;text-align:center;color:white;">
        <div style="font-size:18px;font-weight:600;">{t}</div>
        <div style="font-size:32px;font-weight:700;margin:4px 0;">{v:,.0f}</div>
        <div style="font-size:14px;">{TXT_PRICE[code]} · {sig_dt}</div>
    </div>"""


def vlines(sig: pd.Series, cmap=COL_LINE, min_gap="30D", width: int = 2):
    """신호 변화 지점에 세로 점선 추가."""

    # ① 값이 달라진 지점만 추출
    ev = sig[sig.shift(1) != sig]

    # ② 최소 간격 필터
    if isinstance(min_gap, str):
        min_gap = pd.Timedelta(min_gap)
    keep_idx = []
    last_dt = None
    for dt, val in ev.items():
        if last_dt is None or dt - last_dt >= min_gap:
            keep_idx.append(dt)
            last_dt = dt
    ev = ev.loc[keep_idx]

    # ③ Plotly shape dict 생성
    for dt, val in ev.items():
        color = cmap.get(val, "#95a5a6")
        yield {
            "type": "line",
            "x0": dt,
            "x1": dt,
            "yref": "paper",
            "y0": 0,
            "y1": 1,
            "line": {"color": color, "width": width, "dash": "dot"},
            "opacity": 0.4,
        }

# ── 7. 페이지 레이아웃 & HELP ─────────────────────────────────
st.set_page_config("Macro Dashboard", layout="wide")
st.title("📊 거시 · 자산 대시보드")
with st.sidebar.expander("ℹ️ M2 YoY 도움말", False):
    st.markdown(HELP_MD, unsafe_allow_html=True)

# ── 8. 상단 가격 카드 ─────────────────────────────────────────
c1, c2, c3 = st.columns(3)
if "Gold_KRWg" in view:
    c1.markdown(
        price_card(
            "Gold (원/g)",
            view["Gold_KRWg"].iloc[-1],
            int(last(trend.get("Gold", pd.Series()))),
        ),
        unsafe_allow_html=True,
    )
if "KODEX200" in view:
    c2.markdown(
        price_card(
            "KODEX 200",
            view["KODEX200"].iloc[-1],
            int(last(trend.get("KODEX", pd.Series()))),
        ),
        unsafe_allow_html=True,
    )
if "FX" in view:
    c3.markdown(
        price_card(
            "USD/KRW",
            view["FX"].iloc[-1],
            int(last(trend.get("USDKRW", pd.Series()))),
        ),
        unsafe_allow_html=True,
    )

# ── 9. 지표 겹쳐 보기 (Toggle UI) ──────────────────────────────
# 1) 선택 가능한 지표 정의 ---------------------------------------------------
options = []
series_map = {}
shape_map = {}

if "Gold_KRWg" in view:
    options.append("Gold")
    series_map["Gold"] = view["Gold_KRWg"]
    shape_map["Gold"] = s_gold

if "KODEX200" in view:
    options.append("KODEX")
    series_map["KODEX"] = view["KODEX200"]
    shape_map["KODEX"] = s_kdx

if "FX" in view:
    options.append("USDKRW")
    series_map["USDKRW"] = view["FX"]
    shape_map["USDKRW"] = s_fx

if "M2_D" in view:
    m2_month = view["M2_D"].resample("M").last()
    m2_yoy = (m2_month.pct_change(12) * 100).reindex(view.index, method="ffill")
    options.append("M2_YoY")
    series_map["M2_YoY"] = m2_yoy
    shape_map["M2_YoY"] = s_m2

if "Rate" in view:
    options.append("Rate")
    series_map["Rate"] = view["Rate"]
    shape_map["Rate"] = pd.Series(dtype=float)  # 표시용 세로선 없음

if "Bond10" in view:
    options.append("Bond10")
    series_map["Bond10"] = view["Bond10"]
    shape_map["Bond10"] = pd.Series(dtype=float)

# 2) UI – 멀티셀렉트 --------------------------------------------------------
st.sidebar.markdown("## 지표 선택 (On / Off)")
default_sel = ["Gold", "KODEX"] if set(["Gold", "KODEX"]).issubset(options) else options[:2]
selected = st.sidebar.multiselect("포개서 볼 지표를 선택하세요", options, default=default_sel)

# 3) 그래프 그리기 ----------------------------------------------------------
fig = go.Figure()
color_cycle = px.colors.qualitative.Plotly  # 10‑색 PAL

for i, asset in enumerate(selected):
    ser = series_map[asset]
    fig.add_scatter(
        x=ser.index,
        y=ser,
        name=asset,
        mode="lines",
        line=dict(width=2, dash="dot" if asset == "M2_YoY" else "solid"),
        opacity=0.85,
        marker_color=color_cycle[i % len(color_cycle)],
    )

    sig_series = shape_map.get(asset, pd.Series(dtype=float))
    if not sig_series.empty:
        for shape in vlines(sig_series):
            fig.add_shape(shape)

fig.update_layout(
    title="선택한 지표 겹쳐 보기 (y‑축 원본 스케일)",
    hovermode="x unified",
    legend_orientation="h",
    legend_y=1.08,
)

st.plotly_chart(fig, use_container_width=True)

# ── 10. Signal 카드 (선택) ─────────────────────────────────────
with st.expander("🔔 통합 자산 시그널", expanded=False):
    final_scores = {}
    for asset, ts in trend.items():
        combined = (ts + macro).clip(-3, 3)
        final_scores[asset] = int(last(combined))

    if "RTMS" in view:
        realty_trend = view["RTMS"].pct_change(3).apply(
            lambda x: 2 if x > 0.03 else 1 if x > 0 else -1 if x > -0.03 else -2
        )
        final_scores["Realty"] = int(last((realty_trend + macro).clip(-3, 3)))

    st.markdown(f"### 기준일: {sig_dt}")
    if final_scores:
        columns = st.columns(len(final_scores))
        for (asset, score), col in zip(final_scores.items(), columns):
            col.markdown(card_sig(asset, score), unsafe_allow_html=True)
    else:
        st.info("시그널을 계산할 데이터가 부족합니다.")

st.caption("Data: FRED · Stooq · ECOS · Yahoo Finance — Signals = Macro(M2 + Spread) × Trend")
