#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py – Macro Dashboard Overlay (SP500 integrated)
──────────────────────────────────────────────────
"""
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from dateutil.relativedelta import relativedelta

# ----------------------------------------------------------------
st.set_page_config(
    page_title="Macro Dashboard Overlay",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    div[data-testid="stSidebar"] div[data-testid="stPopover"] button {
        padding: 0.1rem 0.3rem;
        font-size: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ───────────────────────────────────────────────────────────────
# 0. 사이드바 – 도움말 / 옵션
# ----------------------------------------------------------------
HELP_MD = """
### 사용 방법
1. **표시 기간** 슬라이더로 날짜 구간을 지정합니다.  
2. **탭별 토글**을 켜서, 보고 싶은 지표(탭)를 고릅니다.  
   *예: ‘M2’ On → M2 월말·MA6·12 + YoY Bar 까지 한꺼번에 추가*  
3. 기본 스케일은 `표준화` 입니다. 값 범위가 크게 다른 지표끼리 겹쳐도 직선으로 눌리지 않아요.
"""

REL_MD = {
    "M2": (
        "- **M2** 증가율이 높으면 주식·부동산 등 위험자산 가격이 상승하기 쉽습니다."
        "\n- **금리** 하락과 함께 **M2**가 재가속하면 위험자산 비중 확대를 고려합니다."
    ),
    "RateKR": (
        "- 국내 **금리** 상승은 주식·부동산에 부정적 영향을 줍니다.",
        "\n- **금리**가 **CPI**보다 낮아 실질 금리가 마이너스면 **Gold**·**BTC** 비중 확대를 검토합니다.",
    ),
    "RateUS": (
        "- 미국 **금리** 상승은 전세계 금융시장에 영향을 줍니다.",
        "\n- **금리**가 **CPI**보다 낮아 실질 금리가 마이너스면 위험자산 선호가 높아질 수 있습니다.",
    ),
    "USDKRW": (
        "- 환율 하락(원화 강세)은 해외자산 투자 비용을 낮춰 **SP500** 비중 확대 근거가 됩니다."
        "\n- 환율 상승과 **Gold** 가격 동반 상승 시 위험 회피 심리로 주식 비중 축소를 검토합니다."
    ),
    "CPI": (
        "- 물가 상승은 긴축 가능성을 높여 위험자산에 부담입니다."
        "\n- 헤드라인·근원 **CPI** 흐름과 **실질금리**를 함께 보면 정책 방향을 가늠할 수 있습니다."
    ),
    "KODEX": (
        "- 국내 주식 지수로, **M2** 증가와 **금리** 하락 시 상승 가능성이 높아 비중 확대 신호입니다."
        "\n- **M2** 둔화나 **금리** 급등 국면에서는 비중 축소가 유리합니다."
    ),
    "SP500": (
        "- 미국 **M2US** 증가와 **RealRate** 하락이 함께할 때 강세가 나타나 **SP500** 비중 확대를 시사합니다."
        "\n- **RealRate**가 상승 전환하면 비중을 줄이는 것이 안전합니다."
    ),
    "Gold": (
        "- **RealRate**가 0 이하일 때 금 수요가 커져 비중 확대 요인이 됩니다."
        "\n- 달러 약세와 **Gold** 가격 동반 상승은 위험 회피 심리를 의미하며 주식 비중을 줄이고 금 비중을 늘릴 수 있습니다."
        "\n- **RealRate**가 플러스로 돌아서고 달러 강세가 나타나면 금 비중 축소를 검토합니다."
    ),
    "BTC": (
        "- 유동성이 풍부하고 **RealRate**가 낮을 때 강세가 나타나 **BTC** 비중 확대를 고려합니다."
        "\n- 위험 회피 국면이나 **금리** 급등기에는 변동성이 커지므로 비중 축소가 필요합니다."
    ),
    "M2US": (
        "- 미국 **M2US**가 빠르게 증가하면 **SP500** 등 미국 자산에 우호적인 환경이 만들어집니다."
        "\n- 반대로 증가세가 둔화하면 미국 주식 비중을 줄일 근거가 됩니다."
    ),
}

with st.sidebar.expander("ℹ️ 도움말 · Help", expanded=False):
    st.markdown(HELP_MD)



# ───────────────────────────────────────────────────────────────
# 1. 데이터 로드
# ----------------------------------------------------------------
DATA_FP = Path("data/all_data.csv")
if not DATA_FP.exists():
    st.error("❌ data/all_data.csv 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
    st.stop()


@st.cache_data(show_spinner=False)
def load_df(path: Path) -> pd.DataFrame:
    """CSV 로드 및 컬럼 정리 과정을 캐시합니다."""

    df = pd.read_csv(path, index_col=0, parse_dates=True).ffill().loc["2008-01-01":]

    # Gold 원화 환산 – CSV에 없을 때만 계산
    a0_cols = df.columns
    if "Gold_KRWg" not in a0_cols and {"Gold", "FX"}.issubset(a0_cols):
        df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

    # KODEX 200 컬럼 정규화
    for c in df.columns:
        if c.lower().replace(" ", "").startswith("kodex200") or "069500" in c.lower():
            df.rename(columns={c: "KODEX200"}, inplace=True)
            break

    # S&P 500 컬럼 정규화
    for c in df.columns:
        if c.lower() in {"sp500", "^gspc"} or "sp500" in c.lower():
            df.rename(columns={c: "SP500"}, inplace=True)
            break

    # M2 일별 보간
    after_cols = df.columns
    if "M2_D" not in after_cols and "M2" in after_cols:
        df["M2_D"] = df["M2"].resample("D").interpolate("linear")
    if "M2_US_D" not in after_cols and "M2_US" in after_cols:
        df["M2_US_D"] = df["M2_US"].resample("D").interpolate("linear")

    # CPI 및 Core CPI 컬럼 정규화
    for c in list(df.columns):
        uc = c.upper()
        if uc.startswith("CPIAUCSL"):
            df.rename(
                columns={c: "CPI" if not uc.endswith("_D") else "CPI_D"}, inplace=True
            )
        elif uc.startswith("CPILFESL"):
            df.rename(
                columns={c: "CoreCPI" if not uc.endswith("_D") else "CoreCPI_D"},
                inplace=True,
            )

    # CPI 일별 보간
    after_cols = df.columns
    if "CPI_D" not in after_cols and "CPI" in after_cols:
        df["CPI_D"] = df["CPI"].resample("D").ffill()
    if "CoreCPI_D" not in after_cols and "CoreCPI" in after_cols:
        df["CoreCPI_D"] = df["CoreCPI"].resample("D").ffill()

    # Real Rate 계산 (정책금리 - CPI YoY)
    if "RealRate_D" not in after_cols and {"Rate", "CPI_D"}.issubset(after_cols):
        cpi_yoy = df["CPI_D"].resample("ME").last().pct_change(12) * 100
        rr = (df["Rate"].resample("ME").last() - cpi_yoy).reindex(
            df.index, method="ffill"
        )
        df["RealRate_D"] = rr

    return df


df: pd.DataFrame = load_df(DATA_FP)

# ───────────────────────────────────────────────────────────────
# 2. 기간 슬라이더 & View DF
# ----------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📅 표시 기간")

    end_date = df.index.max().date()
    start_date = df.index.min().date()
    mid_date = df.index.max().date() - relativedelta(years=3)

    d0, d1, d2 = start_date, end_date, mid_date
    _date = st.slider(
        "기간", d0, d1, (d2, d1), format="YYYY-MM-DD", key="date_slider_3y"
    )
    d_from, d_to = _date

view = df.loc[pd.to_datetime(d_from) : pd.to_datetime(d_to)].copy()
if view.empty:
    st.warning("선택한 기간에 데이터가 없습니다.")
    st.stop()

sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ───────────────────────────────────────────────────────────────
# 3. Trend·Macro 점수
# ----------------------------------------------------------------


def trend_score(series, short: int = 20, long: int = 50):
    ma_s, ma_l = series.rolling(short).mean(), series.rolling(long).mean()
    cross = np.sign(ma_s - ma_l)
    mom_1m = np.sign(series.pct_change(21))
    return (cross + mom_1m).clip(-2, 2)


trend = {}
if "Gold_KRWg" in view:
    trend["Gold"] = trend_score(view["Gold_KRWg"])
if "KODEX200" in view:
    trend["KODEX"] = trend_score(view["KODEX200"])
if "SP500" in view:
    trend["SP500"] = trend_score(view["SP500"])
if "Bitcoin" in view:
    trend["BTC"] = trend_score(view["Bitcoin"])
if "FX" in view:
    trend["USDKRW"] = trend_score(view["FX"])

# Macro score (M2 YoY + 금리 스프레드)
macro = pd.Series(0, index=view.index)
if "M2_D" in view:
    month = view["M2_D"].resample("ME").last()
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
    s_m2 = m2_score
else:
    s_m2 = pd.Series(dtype=float)

if "Spread5D" in view.columns:
    spread = view["Spread5D"]
    spread_score = spread.apply(lambda x: 1 if x > 0.5 else -1 if x < 0 else 0)
    macro = macro.add(spread_score, fill_value=0)
elif {"Rate", "Bond10"}.issubset(view.columns):
    spread = (view["Bond10"] - view["Rate"]).rolling(5).mean()
    spread_score = spread.apply(lambda x: 1 if x > 0.5 else -1 if x < 0 else 0)
    macro = macro.add(spread_score, fill_value=0)

macro = macro.clip(-3, 3)

# ───────────────────────────────────────────────────────────────
# 4. 색상·유틸 및 월별 세로선 함수
# ----------------------------------------------------------------
COLORS = (
    px.colors.qualitative.Plotly
    + px.colors.qualitative.Set2
    + px.colors.qualitative.Set3
)
SIG_COL_LINE = {2: "#16a085", 1: "#2ecc71", -1: "#f39c12", -2: "#e74c3c"}

# Signal 라인을 완전히 비활성화 (빈 리스트 반환)


def vlines(*args, **kwargs):
    return []


# 매월 1일에 얇은 세로선 추가 – 한 번만 실행


def add_monthly_guides(fig: go.Figure, start: pd.Timestamp, end: pd.Timestamp):
    """주어진 구간의 매월 1일에 세로선을 한 번씩 추가합니다."""
    for dt in pd.date_range(start=start.normalize(), end=end.normalize(), freq="MS"):
        fig.add_shape(
            type="line",
            x0=dt,
            x1=dt,
            yref="paper",
            y0=0,
            y1=1,
            line=dict(color="#bdc3c7", width=1, dash="dot"),
            opacity=0.3,
            layer="below",
        )


# ───────────────────────────────────────────────────────────────
# 5. Sidebar – 탭 토글 & 스케일 모드 + 보조 지표 토글
# ----------------------------------------------------------------
TAB_KEYS = {
    "Gold": "금 가격",
    "KODEX": "KODEX 200",
    "SP500": "S&P 500",
    "BTC": "Bitcoin",
    "M2": "국내 M2 통화량",
    "M2US": "미국 M2 통화량",
    "USDKRW": "환율",
    "RateKR": "국내 금리/10Y",
    "RateUS": "미국 금리/10Y",
    "CPI": "CPI·근원·실질금리",
}

st.sidebar.markdown("### 🔀 탭 On / Off")
selected_tabs = []
for key, label in TAB_KEYS.items():
    default_on = key in {"Gold", "KODEX"}
    col_t, col_p = st.sidebar.columns([6, 1])
    with col_t:
        val = st.toggle(label, value=default_on, key=f"tab_{key}")
    with col_p:
        with st.popover(" "):
            st.markdown(REL_MD.get(key, ""))
    if val:
        selected_tabs.append(key)

if not selected_tabs:
    st.warning("사이드바에서 최소 1개의 탭을 켜 주세요.")
    st.stop()

st.sidebar.markdown("### ⚖️ 값 스케일")
scale_mode = st.sidebar.radio("값 스케일", ("원본 값", "표준화 (0‑1 Min‑Max)"), index=1)

# ───────────────────────────────────────────────────────────────
# 5‑1. 보조 지표 토글 섹션
# ----------------------------------------------------------------

st.sidebar.markdown("### ✨ 보조 지표")

AUX_DEFAULTS = {k: False for k in TAB_KEYS}

aux_enabled = {}
for k in selected_tabs:
    aux_enabled[k] = st.sidebar.toggle(
        f"{TAB_KEYS[k]} 보조 지표", value=AUX_DEFAULTS[k], key=f"aux_{k}"
    )

# ───────────────────────────────────────────────────────────────
# 6. 스케일 함수
# ----------------------------------------------------------------


def scaler(series: pd.Series):
    if scale_mode.startswith("표준화"):
        rng = series.max() - series.min()

        if rng != 0:
            return (series - series.min()) / rng
        return pd.Series(0, index=series.index)

    return series


# ───────────────────────────────────────────────────────────────
# 7. Figure – 선택 탭 Trace 합성
# ----------------------------------------------------------------
fig = go.Figure()
color_iter = iter(COLORS)

for tab in selected_tabs:
    # Gold (원/g)
    if tab == "Gold" and "Gold_KRWg" in view:
        g = view[["Gold_KRWg"]].rename(columns={"Gold_KRWg": "Gold"})
        if aux_enabled["Gold"]:
            for ma in (20, 50, 120):
                g[f"MA{ma}"] = g["Gold"].rolling(ma).mean()
        for col in g.columns:
            fig.add_scatter(
                x=g.index,
                y=scaler(g[col]),
                name=f"Gold {col}" if col != "Gold" else "Gold",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # KODEX 200
    elif tab == "KODEX" and "KODEX200" in view:
        k = view[["KODEX200"]]
        if aux_enabled["KODEX"]:
            for ma in (20, 50, 120):
                k[f"MA{ma}"] = k["KODEX200"].rolling(ma).mean()
        for col in k.columns:
            fig.add_scatter(
                x=k.index,
                y=scaler(k[col]),
                name=f"KODEX {col}" if col != "KODEX200" else "KODEX200",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # S&P 500
    elif tab == "SP500" and "SP500" in view:
        s = view[["SP500"]]
        if aux_enabled["SP500"]:
            for ma in (20, 50, 120):
                s[f"MA{ma}"] = s["SP500"].rolling(ma).mean()
        for col in s.columns:
            fig.add_scatter(
                x=s.index,
                y=scaler(s[col]),
                name=f"S&P500 {col}" if col != "SP500" else "S&P 500",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # Bitcoin
    elif tab == "BTC" and "Bitcoin" in view:
        b = view[["Bitcoin"]]
        if aux_enabled["BTC"]:
            for ma in (20, 50, 120):
                b[f"MA{ma}"] = b["Bitcoin"].rolling(ma).mean()
        for col in b.columns:
            fig.add_scatter(
                x=b.index,
                y=scaler(b[col]),
                name=f"BTC {col}" if col != "Bitcoin" else "Bitcoin",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # M2
    elif tab == "M2" and "M2_D" in view:
        m = view["M2_D"].resample("ME").last().to_frame("M2_M")
        if aux_enabled["M2"]:
            m["MA6"] = m.M2_M.rolling(6).mean()
            m["MA12"] = m.M2_M.rolling(12).mean()
            yoy = (m.M2_M.pct_change(12) * 100).rename("YoY%")
            fig.add_bar(
                x=yoy.index,
                y=scaler(yoy),
                name="M2 YoY% (bar)",
                opacity=0.45,
                marker_color=next(color_iter),
            )
        for col in m.columns:
            fig.add_scatter(
                x=m.index,
                y=scaler(m[col]),
                name=f"{col}",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # M2US
    elif tab == "M2US" and "M2_US_D" in view:
        m = view["M2_US_D"].resample("ME").last().to_frame("M2US_M")
        if aux_enabled["M2US"]:
            m["MA6"] = m.M2US_M.rolling(6).mean()
            m["MA12"] = m.M2US_M.rolling(12).mean()
            yoy = (m.M2US_M.pct_change(12) * 100).rename("YoY%")
            fig.add_bar(
                x=yoy.index,
                y=scaler(yoy),
                name="US M2 YoY% (bar)",
                opacity=0.45,
                marker_color=next(color_iter),
            )
        for col in m.columns:
            fig.add_scatter(
                x=m.index,
                y=scaler(m[col]),
                name=f"{col}",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # USDKRW
    elif tab == "USDKRW" and "FX" in view:
        fx = view[["FX"]]
        if aux_enabled["USDKRW"]:
            for ma in (20, 50, 120):
                fx[f"MA{ma}"] = fx["FX"].rolling(ma).mean()
        for col in fx.columns:
            fig.add_scatter(
                x=fx.index,
                y=scaler(fx[col]),
                name=f"FX {col}" if col != "FX" else "USD/KRW",
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # CPI · Core CPI · Real Rate
    elif tab == "CPI" and {"CPI_D", "CoreCPI_D", "RealRate_D"}.issubset(view.columns):
        df_cpi = pd.DataFrame({
            "CPI": view["CPI_D"].resample("ME").last(),
            "CoreCPI": view["CoreCPI_D"].resample("ME").last(),
            "RealRate": view["RealRate_D"].resample("ME").last(),
        })
        if aux_enabled.get("CPI"):
            yoy = (df_cpi["CPI"].pct_change(12) * 100).rename("CPI YoY%")
            fig.add_bar(
                x=yoy.index,
                y=scaler(yoy),
                name="CPI YoY% (bar)",
                opacity=0.45,
                marker_color=next(color_iter),
            )
            yoy2 = (df_cpi["CoreCPI"].pct_change(12) * 100).rename("Core CPI YoY%")
            fig.add_bar(
                x=yoy2.index,
                y=scaler(yoy2),
                name="Core CPI YoY% (bar)",
                opacity=0.45,
                marker_color=next(color_iter),
            )
        for col in df_cpi.columns:
            fig.add_scatter(
                x=df_cpi.index,
                y=scaler(df_cpi[col]),
                name=col,
                mode="lines",
                line=dict(width=2, color=next(color_iter)),
            )

    # Korean Rate & 10Y
    elif tab == "RateKR" and {"Rate", "Bond10"}.issubset(view.columns):
        cols = ["Rate", "Bond10"]
        r = view[cols].copy()
        if aux_enabled["RateKR"]:
            for base_col in cols:
                m = r[base_col].resample("ME").last()
                r[f"{base_col}_MA3M"] = m.rolling(3).mean().reindex(r.index, method="ffill")
        for col in r.columns:
            fig.add_scatter(
                x=r.index,
                y=scaler(r[col]),
                name=col,
                mode="lines",
                line=dict(
                    width=2,
                    color=next(color_iter),
                    dash="dot" if "MA" in col else "solid",
                ),
            )
    # US Rate & 10Y
    elif tab == "RateUS" and {"Rate_US", "Bond10_US"}.issubset(view.columns):
        cols = ["Rate_US", "Bond10_US"]
        r = view[cols].copy()
        if aux_enabled["RateUS"]:
            for base_col in cols:
                m = r[base_col].resample("ME").last()
                r[f"{base_col}_MA3M"] = m.rolling(3).mean().reindex(r.index, method="ffill")
        for col in r.columns:
            fig.add_scatter(
                x=r.index,
                y=scaler(r[col]),
                name=col,
                mode="lines",
                line=dict(
                    width=2,
                    color=next(color_iter),
                    dash="dot" if "MA" in col else "solid",
                ),
            )

# 월별 세로 가이드라인 추가
add_monthly_guides(fig, view.index.min(), view.index.max())

# ───────────────────────────────────────────────────────────────
# 8. Figure Layout
# ----------------------------------------------------------------
# 원본 값일 때는 금액(원), 지수 또는 비율(%) 등 여러 단위를 포괄적으로 표시한다.
y_title = (
    "Value (원·지수/%)" if scale_mode.startswith("원본") else "표준화 값 (0–1)"
)
fig.update_layout(
    height=640,
    title=f"선택한 탭 Overlay – {scale_mode}",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis_title=y_title,
    margin=dict(l=40, r=40, t=60, b=40),
)
fig.update_xaxes(rangeslider_visible=True)

st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────────
# 9. Snapshot (원본 값 기준)
# ----------------------------------------------------------------

snap_vals = {}
if "Gold_KRWg" in view:
    snap_vals["Gold (원/g)"] = view["Gold_KRWg"].iloc[-1]
if "KODEX200" in view:
    snap_vals["KODEX 200"] = view["KODEX200"].iloc[-1]
if "SP500" in view:
    snap_vals["S&P 500"] = view["SP500"].iloc[-1]
if "Bitcoin" in view:
    snap_vals["Bitcoin"] = view["Bitcoin"].iloc[-1]
if "FX" in view:
    snap_vals["USD/KRW"] = view["FX"].iloc[-1]
if "Rate" in view:
    snap_vals["기준금리 (%)"] = view["Rate"].iloc[-1]
if "Bond10" in view:
    snap_vals["10Y (%)"] = view["Bond10"].iloc[-1]
if "Rate_US" in view:
    snap_vals["연준금리 (%)"] = view["Rate_US"].iloc[-1]
if "Bond10_US" in view:
    snap_vals["미국10Y (%)"] = view["Bond10_US"].iloc[-1]
if "M2_D" in view:
    snap_vals["국내 M2 월말"] = view["M2_D"].resample("ME").last().iloc[-1]
if "M2_US_D" in view:
    snap_vals["미국 M2 월말"] = view["M2_US_D"].resample("ME").last().iloc[-1]
if "CPI_D" in view:
    snap_vals["CPI"] = view["CPI_D"].resample("ME").last().iloc[-1]
if "RealRate_D" in view:
    snap_vals["Real Rate"] = view["RealRate_D"].resample("ME").last().iloc[-1]

st.markdown("### 최근 값 Snapshot")

snap_units = {
    "Gold (원/g)": "₩",
    "KODEX 200": "₩",
    "S&P 500": "$",
    "Bitcoin": "$",
    "USD/KRW": "₩",
    "기준금리 (%)": "%",
    "10Y (%)": "%",
    "연준금리 (%)": "%",
    "미국10Y (%)": "%",
    "국내 M2 월말": "₩",
    "미국 M2 월말": " B",
    "CPI": "",
    "Real Rate": "%",
}

def _fmt(val: float, unit: str) -> str:
    if unit == "₩":
        return f"{val:,.0f}{unit}"
    return f"{val:,.2f}{unit}"

snap_tbl = pd.DataFrame(
    [
        {"항목": label, "값": _fmt(val, snap_units.get(label, ""))}
        for label, val in snap_vals.items()
    ]
)

st.table(snap_tbl)

# ───────────────────────────────────────────────────────────────
# 10. Signal 카드 (기존 로직 유지)
# ----------------------------------------------------------------
with st.expander("🔔 통합 자산 시그널", expanded=False):
    final_scores = {}
    for asset, ts in trend.items():
        final_scores[asset] = int((ts + macro).clip(-3, 3).iloc[-1])

    if "RTMS" in view:
        realty_trend = (
            view["RTMS"]
            .pct_change(3)
            .apply(lambda x: 2 if x > 0.03 else 1 if x > 0 else -1 if x > -0.03 else -2)
        )
        final_scores["Realty"] = int((realty_trend + macro).clip(-3, 3).iloc[-1])

    st.write(f"### 기준일: {sig_dt}")
    if final_scores:
        _cols = st.columns(len(final_scores))
        for (asset, score), c in zip(final_scores.items(), _cols):
            c.markdown(
                f"<div style='background:{SIG_COL_LINE.get(score, '#6c757d')};border-radius:8px;padding:20px 12px;text-align:center;color:white;'>"
                f"<div style='font-size:18px;font-weight:600;'>{asset}</div>"
                f"<div style='font-size:32px;font-weight:700;margin:4px 0;'>{score:+}</div>"
                f"<div style='font-size:14px;opacity:.8;'>{sig_dt}</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("시그널을 계산할 데이터가 부족합니다.")

st.caption(
    "Data: FRED · Stooq · ECOS · Yahoo Finance — Signals = Macro(M2 + Spread) × Trend"
)
