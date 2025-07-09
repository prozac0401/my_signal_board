import pandas as pd, streamlit as st, plotly.express as px

# ╭── HELP 패널 ──────────────────────────────────────────────────╮
HELP_MD = """
### M2 YoY 4-단계 구간
| 구간 | 해석 | 시사점 |
|------|------|-------|
| **> 9 %**  • 팽창 | 평균 + 0.5 σ 이상 | **리스크-온** (주식·부동산 확대) |
| **6 – 9 %** • 완충 | 평균 부근 | 중립 · 추세 확인 |
| **3 – 6 %** • 둔화 | 평균 – 1 σ 이상 | 경계 · 리밸런스 |
| **< 3 %**  • 수축 | 평균 – 1 σ 이하 | **리스크-오프** (현금·단기채 확대) |

#### 응용 TIP
| 아이디어 | 설명 |
|----------|------|
| **신호 필터링** | M2 YoY > 9 % 구간일 때만 주식 신호(**KODEX 200**) 채택 → 가짜 반등 회피 |
| **멀티 컨펌** | M2 팽창(> 9 %) + 환율 ↓ + KODEX 200 ↑ → **공격적 비중 확대**<br>M2 수축(< 3 %) + Gold ↓ → 안전자산 축소·현금 확보 |
| **모멘텀 결합** | ‘팽창’ 구간이면서 M2 YoY 20 EMA 위·기울기 상승일 때만 리스크-온 |
"""
# ╰──────────────────────────────────────────────────────────────╯

# ───── 이하 로직/그래프/신호는 이전 버전과 동일 ──────
# (※ 변경된 부분은 타이틀·HELP_MD 뿐입니다)

df = (pd.read_csv("data/all_data.csv", index_col=0, parse_dates=True)
        .ffill()
        .loc["2008-01-01":])

if {"Gold","FX"}.issubset(df.columns):
    df["Gold_KRWg"] = df["Gold"] * df["FX"] / 31.1035

for c in df.columns:
    if c.lower().replace(" ","").startswith("kodex200") or "069500" in c.lower():
        df.rename(columns={c:"KODEX200"}, inplace=True); break

if "M2_D" not in df.columns and "M2" in df.columns:
    df["M2_D"] = df["M2"].resample("D").interpolate("linear")

# ── 슬라이더
d0,d1 = df.index.min().date(), df.index.max().date()
d_from,d_to = st.slider("표시 기간", d0, d1, (d0,d1), format="YYYY-MM-DD")
view   = df.loc[pd.to_datetime(d_from):pd.to_datetime(d_to)]
sig_dt = view.index[-1].strftime("%Y-%m-%d")

# ── 자산 신호
def ma_sig(s): m20,m50=s.rolling(20).mean(),s.rolling(50).mean(); return (m20-m50).apply(lambda x:1 if x>0 else -1 if x<0 else 0)
s_gold = ma_sig(view["Gold_KRWg"]) if "Gold_KRWg" in view else pd.Series()
s_kdx  = ma_sig(view["KODEX200"])  if "KODEX200"  in view else pd.Series()
s_fx   = ma_sig(view["FX"])        if "FX"        in view else pd.Series()

# ── M2 YoY 4-단계
if "M2_D" in view:
    m  = view["M2_D"].resample("M").last()
    yy = (m.pct_change(12)*100).rename("YoY")
    def cls(x):
        if pd.isna(x): return -1
        if x>9: return 2
        if x>=6: return 1
        if x>=3: return -1
        return -2
    s_m2 = yy.apply(cls).reindex(view.index, method="ffill")
else:
    s_m2 = pd.Series()

COL = {2:"#16a085",1:"#2ecc71",-1:"#f39c12",-2:"#e74c3c"}
TXT = {2:"팽창",1:"완충",-1:"둔화",-2:"수축"}
def last(sig): return sig.iloc[-1] if not sig.empty else -1

def card(t,v,code):
    bg = COL.get(code,"#95a5a6"); tag = TXT.get(code,"—")
    v = f"{v:,.0f}" if v>1_000 else f"{v:,.2f}"
    return f"<div style='background:{bg};border-radius:8px;padding:20px 12px;text-align:center;color:#fff;'><div style='font-size:18px;font-weight:600'>{t}</div><div style='font-size:32px;font-weight:700;margin:4px 0'>{v}</div><div style='font-size:14px'>{tag} · {sig_dt}</div></div>"

def vlines(sig):
    for d,c in sig[sig.shift(1)!=sig].items():
        if c in COL:
            yield dict(type="line",x0=d,x1=d,yref="paper",y0=0,y1=1,line=dict(color=COL[c],width=1,dash="dot"),opacity=0.25)

# ── 레이아웃 & HELP
st.set_page_config("Macro Dashboard", layout="wide")
st.title("거시 · 자산 대시보드")  # 📊 이모지 제거
with st.sidebar.expander("M2 YoY 도움말", False):
    st.markdown(HELP_MD, unsafe_allow_html=True)

# ── 상단 카드
c1,c2,c3 = st.columns(3)
if "Gold_KRWg" in view: c1.markdown(card("Gold (원/g)", view["Gold_KRWg"].iloc[-1], last(s_gold)), unsafe_allow_html=True)
if "KODEX200" in view:  c2.markdown(card("KODEX 200",   view["KODEX200"].iloc[-1],  last(s_kdx)),  unsafe_allow_html=True)
if "FX" in view:        c3.markdown(card("USD/KRW",     view["FX"].iloc[-1],        last(s_fx)),   unsafe_allow_html=True)

# --- (금·KODEX·환율 그래프, M2 합친 그래프, Signal 표) ---
#     아래 부분은 이전 버전과 동일이므로 생략 없이 그대로 사용하시면 됩니다.
