"""
Macro Dashboard Overlay
=======================
Streamlit 대시보드 App.

* **목표**  –  한 그래프 위에 여러 거시경제 지표를 *On / Off* 토글(스위치)로 겹쳐서 보여준다.
* **기능 추가 (2025‑07‑11)**
    * **스케일 모드** – `원본 값` vs `표준화(0‑1 Min‑Max)` 라디오 버튼을 사이드바에 추가.
    * "표준화"를 선택하면, 선택된 각 지표를 기간 내 `min‑max` 정규화하여 0~1 범위에 꽉 차도록 표시. 값 범위가 큰 지표도 납작해지지 않음.
* **데이터**    data/all_data.csv · 일(日) 단위 시계열 (index: Date)
* **주의**    `표준화` 모드에서는 y축이 0–1 로 고정되므로, 실제 단위는 hover tooltip 에서 확인.

Written 2025‑07‑11  (UTC+9)
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px   # 테마·팔레트 확장 대비 보유
from pathlib import Path

st.set_page_config(
    page_title="Macro Dashboard Overlay",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────────────────────────────────────
# 0. 사이드바 – 도움말 / 옵션
# ----------------------------------------------------------------
HELP_MD = """
### 사용 방법
1. **표시 기간** 슬라이더로 날짜 구간을 지정합니다.  
2. **지표 On/Off** 스위치를 켜서, 겹쳐 보고 싶은 시계열을 선택합니다.  
3. **값 스케일** 라디오 버튼으로 `원본 값` 또는 `표준화` 방식을 선택합니다.  
4. 그래프가 자동으로 업데이트되어 선택한 지표만 한 컷에 겹쳐집니다.

> ⚠️ `원본 값` 모드에서는 서로 단위가 다른 지표를 그대로 겹쳐 놓기 때문에, 값 범위가 작은 지표는 선이 거의 직선으로 보일 수 있습니다.
>  
> `표준화` 모드를 사용하면 모든 지표가 0~1 범위에 맞춰져 비교가 용이하지만, 실제 수치는 툴팁에서 확인하세요.
"""

with st.sidebar.expander("ℹ️ 도움말 · Help", expanded=False):
    st.markdown(HELP_MD)

# ───────────────────────────────────────────────────────────────
# 1. 데이터 로드 및 선처리
# ----------------------------------------------------------------
DATA_FP = Path("data/all_data.csv")
if not DATA_FP.exists():
    st.error("❌ data/all_data.csv 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
    st.stop()

# csv → DataFrame (index: Date)

df: pd.DataFrame = (
    pd.read_csv(DATA_FP, index_col=0, parse_dates=True)
    .ffill()                             # 앞 결측 채우기
    .loc["2008-01-01":]                # 분석 구간 cut
)

# ─ 파생 컬럼 ----------------------------------------------------
if {"Gold", "FX"}.issubset(df.columns):       # 달러 금 · 환율 → 원화 환산(g)
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

# KODEX200 (티커명·컬럼명 가변) 표준화
for c in df.columns:
    if c.lower().replace(" ", "").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c: "KODEX200"}, inplace=True)
        break

# M2 일별 보간
if "M2_D" not in df.columns and "M2" in df.columns:
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ───────────────────────────────────────────────────────────────
# 2. 기간 슬라이더 & View DataFrame
# ----------------------------------------------------------------
st.sidebar.markdown("### 📅 표시 기간")

d0, d1 = df.index.min().date(), df.index.max().date()
_calendar_kwargs = dict(format="YYYY-MM-DD")

d_from, d_to = st.sidebar.slider("기간", d0, d1, (d0, d1), **_calendar_kwargs)
view: pd.DataFrame = df.loc[pd.to_datetime(d_from) : pd.to_datetime(d_to)].copy()

if view.empty:
    st.warning("선택한 기간에 데이터가 없습니다.")
    st.stop()

# ───────────────────────────────────────────────────────────────
# 3. Sidebar – 지표 On / Off 스위치 & 스케일 모드
# ----------------------------------------------------------------
EXCLUDE = {"FX", "Rate", "Bond10"}   # 기본 숨김 (또는 내부 계산용)

st.sidebar.markdown("### 🔀 지표 On / Off")

selected_cols: list[str] = []
for col in sorted(view.columns):
    if col in EXCLUDE:
        continue
    friendly = col.replace("_", " ")
    default_on = col in {"M2_D", "KODEX200"}  # 최초 기본 선택 예시
    if st.sidebar.toggle(friendly, value=default_on, key=col):
        selected_cols.append(col)

if not selected_cols:
    st.warning("사이드바에서 최소 1개의 지표를 켜 주세요.")
    st.stop()

st.sidebar.markdown("### ⚖️ 값 스케일")
scale_mode = st.sidebar.radio("값 스케일", ("원본 값", "표준화 (0‑1 Min‑Max)"), index=0)

# ───────────────────────────────────────────────────────────────
# 4. Overlay Plot
# ----------------------------------------------------------------
plot_df = view[selected_cols].copy()

if scale_mode.startswith("표준화"):
    # 각 시리즈를 0‑1 범위로 정규화 (min‑max) – 같은 y축 대비
    def _minmax(s: pd.Series):
        rng = s.max() - s.min()
        return (s - s.min()) / rng if rng != 0 else 0

    plot_df = plot_df.apply(_minmax)

color_seq = px.colors.qualitative.Set2 + px.colors.qualitative.Set3
fig = go.Figure()

for i, col in enumerate(plot_df.columns):
    fig.add_scatter(
        x=plot_df.index,
        y=plot_df[col],
        name=col.replace("_", " "),
        mode="lines",
        line=dict(width=2, color=color_seq[i % len(color_seq)]),
        opacity=0.9,
    )

y_title = "Value (원/%) – 단일 스케일" if scale_mode == "원본 값" else "표준화 값 (0–1)"

fig.update_layout(
    height=580,
    margin=dict(l=40, r=40, t=60, b=40),
    title=f"선택 지표 Overlay – {scale_mode}",
    xaxis_title="Date",
    yaxis_title=y_title,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig.update_xaxes(rangeslider_visible=True)

st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────────
# 5. 최근 값 Snapshot (항상 원본 값으로)
# ----------------------------------------------------------------
if scale_mode == "원본 값":
    snapshot_df = plot_df.copy()
else:
    # 표준화 모드일 때도 원본 최근 값이 더 유용하므로 view 사용
    snapshot_df = view[selected_cols]

st.markdown("### 최근 값 Snapshot")
cols = st.columns(len(selected_cols))
for c, col in zip(cols, selected_cols):
    last_val = snapshot_df[col].iloc[-1]
    c.metric(col.replace("_", " "), f"{last_val:,.2f}")

# ───────────────────────────────────────────────────────────────
# End of File
