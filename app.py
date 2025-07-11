import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px   # 테마·팔레트 확장 대비
from pathlib import Path

"""
Macro Dashboard Overlay — 표준화 오버레이 전용 (2025‑07‑11)
----------------------------------------------------------
* **목표**  –  선택한 거시경제·자산 지표를 **0‑1 Min‑Max 표준화**하여 한 y축에 겹쳐서 보여줍니다.
* **왜?**  단위·스케일이 다른 시계열을 원본 값 그대로 겹치면 값 범위가 작은 지표가 납작해지므로, 모든 지표를 기간 내 최대·최소로 정규화해 시각적으로 0‑1 범위에 ‘꽉 차게’ 매핑합니다.
* **사용 방법**  사이드바에서 표시 기간을 조정하고, On/Off 스위치로 보고 싶은 지표를 고르세요. 그래프는 자동으로 업데이트됩니다.

Data source ▶ `data/all_data.csv`  (日 단위)
"""

# ───────────────────────────────────────────────────────────────
# 0. Page Config & Sidebar Help
# ----------------------------------------------------------------
st.set_page_config(
    page_title="Macro Dashboard Overlay (Normalized)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

HELP_MD = """
### 사용 가이드
1. **표시 기간** 슬라이더로 원하는 날짜 구간을 지정합니다.
2. **지표 On/Off** 스위치를 켜서 시계열을 선택합니다.
3. 각 지표는 선택한 기간 내 `min‑max` 방식으로 **0–1** 로 정규화되어 한 그래프에 겹쳐집니다.

> 📝 툴팁에는 정규화된 값(0–1)이 표시됩니다. 실제 단위‑값이 필요하면 원본 데이터를 참고하세요.
"""
with st.sidebar.expander("ℹ️ 도움말 · Help", expanded=False):
    st.markdown(HELP_MD)

# ───────────────────────────────────────────────────────────────
# 1. Load & Pre‑process Data
# ----------------------------------------------------------------
DATA_FP = Path("data/all_data.csv")
if not DATA_FP.exists():
    st.error("❌ data/all_data.csv 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
    st.stop()

# csv → DataFrame (index: Date)
df = (
    pd.read_csv(DATA_FP, index_col=0, parse_dates=True)
    .ffill()
    .loc["2008-01-01":]
)

# 파생 컬럼 ------------------------------------------------------
if {"Gold", "FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

for c in df.columns:
    if c.lower().replace(" ", "").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c: "KODEX200"}, inplace=True)
        break

if "M2_D" not in df.columns and "M2" in df.columns:
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ───────────────────────────────────────────────────────────────
# 2. Date Range Selection
# ----------------------------------------------------------------
st.sidebar.markdown("### 📅 표시 기간")

d0, d1 = df.index.min().date(), df.index.max().date()
d_from, d_to = st.sidebar.slider("기간", d0, d1, (d0, d1), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(d_from) : pd.to_datetime(d_to)].copy()

if view.empty:
    st.warning("선택한 기간에 데이터가 없습니다.")
    st.stop()

# ───────────────────────────────────────────────────────────────
# 3. Indicator Toggles
# ----------------------------------------------------------------
EXCLUDE = {"FX", "Rate", "Bond10"}  # 기본 숨김 또는 내부 계산용

st.sidebar.markdown("### 🔀 지표 On / Off")
selected_cols: list[str] = []
for col in sorted(view.columns):
    if col in EXCLUDE:
        continue
    friendly = col.replace("_", " ")
    default_on = col in {"M2_D", "KODEX200"}
    if st.sidebar.toggle(friendly, value=default_on, key=col):
        selected_cols.append(col)

if not selected_cols:
    st.warning("사이드바에서 최소 1개의 지표를 켜 주세요.")
    st.stop()

# ───────────────────────────────────────────────────────────────
# 4. Normalize & Plot
# ----------------------------------------------------------------
plot_df = view[selected_cols].copy()

# 0‑1 Min‑Max 정규화 ------------------------------------------------
plot_df = plot_df.apply(lambda s: (s - s.min()) / (s.max() - s.min()) if (s.max() - s.min()) != 0 else 0)

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

fig.update_layout(
    height=580,
    margin=dict(l=40, r=40, t=60, b=40),
    title="선택 지표 Overlay – 표준화 (0‑1)",
    xaxis_title="Date",
    yaxis_title="표준화 값 (0–1)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig.update_xaxes(rangeslider_visible=True)

st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────────
# 5. Snapshot – 최근 원본 값 (informative)
# ----------------------------------------------------------------
st.markdown("### 최근 *원본* 값 Snapshot")
cols = st.columns(len(selected_cols))
for c, col in zip(cols, selected_cols):
    last_val = view[col].iloc[-1]
    c.metric(col.replace("_", " "), f"{last_val:,.2f}")

# End of file
