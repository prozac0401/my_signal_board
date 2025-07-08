import pandas as pd, streamlit as st, plotly.express as px, plotly.graph_objects as go

# ── 데이터 로드 & 전처리 ─────────────────────────
df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

if "069500.KS" in df.columns and "KODEX200" not in df.columns:
    df.rename(columns={"069500.KS":"KODEX200"}, inplace=True)

vol_cols = [c for c in df.columns if c.startswith("Vol_")]

# ── 날짜 슬라이더 ────────────────────────────────
start, end = st.slider(
    "표시 기간", df.index.min().date(), df.index.max().date(),
    (df.index.min().date(), df.index.max().date()), format="YYYY-MM-DD")
view = df.loc[pd.to_datetime(start):pd.to_datetime(end)]

# ── 신호 계산 (20/50 MA) & 색상 매핑 ─────────────
def ma_cross(series):
    ma20, ma50 = series.rolling(20).mean(), series.rolling(50).mean()
    if ma20.isna().iloc[-1] or ma50.isna().iloc[-1]:
        return 0   # 회색
    prev, curr = ma20.sub(ma50).iloc[-2], ma20.sub(ma50).iloc[-1]
    if prev < 0 < curr:   return 1  # 🟢
    if prev > 0 > curr:   return -1 # 🔴
    return 0

sig_map = {1:("비중↑","#006400"), -1:("비중↓","#8B0000"), 0:("유지","#808080")}
sig_gold  = ma_cross(view["Gold_KRWg"]) if "Gold_KRWg" in view else 0
sig_kodex = ma_cross(view["KODEX200"])  if "KODEX200"  in view else 0
sig_fx    = ma_cross(view["FX"])        if "FX"        in view else 0

# ── Streamlit 레이아웃 ──────────────────────────
st.set_page_config("Macro × Suwon Dashboard", layout="wide")
st.title("📊 거시 · 자산 · 수원 거래량")

# 메트릭 카드 (Plotly Indicator → 배경색 가능)
def card(title, value, sig_code):
    label, color = sig_map[sig_code]
    fig = go.Figure(go.Indicator(
        mode="number+delta",
        value=value,
        number={"font":{"size":22,"color":"white"}},
        title={"text":f"<b>{title}</b><br><span style='font-size:0.8em'>{label}</span>",
               "font":{"color":"white"}},
        domain={"x":[0,1],"y":[0,1]}
    ))
    fig.update_layout(height=140, paper_bgcolor=color)
    st.plotly_chart(fig, use_container_width=True)

c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view: c1.write(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], sig_gold))
if "KODEX200" in view:  c2.write(card("KODEX 200",   view["KODEX200"].iloc[-1], sig_kodex))
if "FX" in view:        c3.write(card("USD/KRW",     view["FX"].iloc[-1],       sig_fx))

# ── 탭 ──────────────────────────────────────────
tab_price, tab_macro, tab_fx, tab_sig = st.tabs(["가격", "거시·거래량", "환율", "Signal"])

with tab_price:
    cols = [c for c in ["Gold_KRWg","KODEX200"] if c in view.columns]
    st.plotly_chart(px.line(view[cols], title="Gold (원/g) · KODEX 200"), use_container_width=True)

with tab_macro:
    macro_cols = [c for c in ["Rate","M2","DXY","Bond10"] if c in view.columns]
    if macro_cols:
        st.plotly_chart(px.line(view[macro_cols], title="거시 지표"), use_container_width=True)
    if vol_cols:
        st.plotly_chart(px.line(view[vol_cols], title="수원 4구 거래량"), use_container_width=True)

with tab_fx:
    if "FX" in view and view["FX"].notna().any():
        fx_df = view[["FX"]].copy()
        fx_df["MA20"] = fx_df["FX"].rolling(20).mean()
        fx_df["MA50"] = fx_df["FX"].rolling(50).mean()
        st.plotly_chart(px.line(fx_df, title="USD/KRW & MA20·50"), use_container_width=True)
    elif "DXY" in view and view["DXY"].notna().any():
        st.plotly_chart(px.line(view[["DXY"]], title="DXY 달러지수"), use_container_width=True)
    else:
        st.info("환율 데이터가 없습니다.")

with tab_sig:
    sig_table = pd.DataFrame({
        "자산":["Gold","KODEX200","USD/KRW"],
        "Signal":[sig_map[s][0] for s in [sig_gold,sig_kodex,sig_fx]]
    }).set_index("자산")
    st.table(sig_table)

st.caption("Data: FRED · Stooq · ECOS · K-REB · Yahoo Finance | Signals: 20/50 MA cross")
