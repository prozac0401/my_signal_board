
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
3. 그래프가 자동으로 업데이트되어 선택한 지표만 한 컷에 겹쳐집니다.

> ⚠️ 서로 단위(%) vs 가격 값이 다른 지표를 그대로 겹쳐 놓기 때문에, 스케일이 작은 지표는 선이 거의 직선으로 보일 수 있습니다.
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
# 3. Sidebar – 지표 On / Off 스위치
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

# ───────────────────────────────────────────────────────────────
# 4. Overlay Plot (단일 y‑축)
# ----------------------------------------------------------------
color_seq = px.colors.qualitative.Set2 + px.colors.qualitative.Set3
fig = go.Figure()

for i, col in enumerate(selected_cols):
    fig.add_scatter(
        x=view.index,
        y=view[col],
        name=col.replace("_", " "),
        mode="lines",
        line=dict(width=2, color=color_seq[i % len(color_seq)]),
        opacity=0.85,
    )

fig.update_layout(
    height=580,
    margin=dict(l=40, r=40, t=60, b=40),
    title="선택 지표 Overlay",
    xaxis_title="Date",
    yaxis_title="Value (원/%) – 단일 스케일",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig.update_xaxes(rangeslider_visible=True)

st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────────
# 5. (옵션) 최근 값 카드 예시
# ----------------------------------------------------------------
st.markdown("### 최근 값 Snapshot")
cols = st.columns(len(selected_cols))
for c, col in zip(cols, selected_cols):
    last_val = view[col].iloc[-1]
    c.metric(col.replace("_", " "), f"{last_val:,.2f}")

# ───────────────────────────────────────────────────────────────
# End of File
