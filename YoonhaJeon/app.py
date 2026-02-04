# app.py
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# =========================
# 0) Page Config + Global CSS
# =========================
st.set_page_config(
    page_title="자동차 리콜 현황",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; padding-bottom: 2rem; }
      .kpi-card { border: 1px solid rgba(49,51,63,0.15); border-radius: 14px; padding: 14px 16px; }
      .kpi-label { font-size: 0.85rem; color: rgba(49,51,63,0.65); margin-bottom: 2px; }
      .kpi-value { font-size: 1.4rem; font-weight: 700; }
      .kpi-sub { font-size: 0.8rem; color: rgba(49,51,63,0.55); margin-top: 2px; }
      .section-title { font-weight: 700; margin: 6px 0 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# 1) Data Layer (DB 연결 포인트)
# =========================
@st.cache_data(show_spinner=False)
def load_recall_data() -> pd.DataFrame:
    """
    TODO: DB에서 리콜 데이터를 읽어 DataFrame으로 반환하세요.
    - 권장 컬럼 예시(최소):
      manufacturer, model, recall_date, severity, status, affected_units, reason

    예시:
      import sqlalchemy as sa
      engine = sa.create_engine(DB_URL)
      df = pd.read_sql("SELECT ...", engine)
      return df
    """
    # 현재는 DB 미연결: 빈 데이터프레임 반환(앱은 정상 구동)
    return pd.DataFrame(
        columns=[
            "manufacturer",     # 제조사
            "model",            # 모델
            "recall_date",      # 리콜일 (date/datetime)
            "severity",         # 심각도(예: 위험/경고/주의)
            "status",           # 처리상태(예: 진행중/완료/계획)
            "affected_units",   # 대상 차량 대수(int)
            "reason",           # 리콜 사유
        ]
    )

def apply_filters(df: pd.DataFrame, q: str, mfg: str, severity: str) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    if q:
        q_lower = q.lower()
        # 제조사/모델/사유 기준 간단 검색
        mask = (
            out["manufacturer"].astype(str).str.lower().str.contains(q_lower, na=False)
            | out["model"].astype(str).str.lower().str.contains(q_lower, na=False)
            | out["reason"].astype(str).str.lower().str.contains(q_lower, na=False)
        )
        out = out[mask]

    if mfg != "전체":
        out = out[out["manufacturer"] == mfg]

    if severity != "전체":
        out = out[out["severity"] == severity]

    return out

# =========================
# 2) Header
# =========================
header_left, header_right = st.columns([0.85, 0.15], vertical_alignment="center")
with header_left:
    st.title("자동차 리콜 현황")
    st.caption("실시간 리콜 정보 조회 서비스")
with header_right:
    # 추후: 로그인/버튼 등 배치 가능
    st.empty()

st.divider()

# =========================
# 3) Controls (Search + Filters)
# =========================
controls = st.container()
with controls:
    q = st.text_input("검색", placeholder="제조사, 모델명, 리콜 사유로 검색...", label_visibility="collapsed")

    c1, c2, c3 = st.columns([0.18, 0.18, 0.64], vertical_alignment="center")
    with c1:
        mfg_selected = st.selectbox("제조사", options=["전체"], index=0)
    with c2:
        severity_selected = st.selectbox("심각도", options=["전체", "위험", "경고", "주의"], index=0)
    with c3:
        reset = st.button("필터 초기화", use_container_width=False)

    if reset:
        st.session_state.clear()
        st.rerun()

# =========================
# 4) Tabs
# =========================
tab_list, tab_stats = st.tabs(["🚗 리콜 목록", "🚨 통계"])

# Load + Filter
df_raw = load_recall_data()

# (DB 연결 후) 제조사 목록 동적 반영
if not df_raw.empty:
    mfg_options = ["전체"] + sorted(df_raw["manufacturer"].dropna().unique().tolist())
    # selectbox 옵션을 동적으로 바꾸려면 session_state key로 관리하는 것이 안정적이라,
    # 단순화를 위해 현재는 기본 옵션만 유지했습니다.
    # 운영 시: st.selectbox(..., options=mfg_options, key="mfg") 형태 추천.

df = apply_filters(df_raw, q=q, mfg=mfg_selected, severity=severity_selected)

# =========================
# 5) Tab: List (리콜 목록)
# =========================
with tab_list:
    st.markdown('<div class="section-title">리콜 목록</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("현재 표시할 데이터가 없습니다. DB 연결 후 데이터가 적재되면 목록이 표시됩니다.")
    else:
        st.write(f"총 **{len(df):,}건**의 리콜 정보")

        # 카드형 리스트 (간단 버전)
        # 운영 시: CSS 카드 + 버튼/expander로 확장 가능
        for i, row in df.head(20).iterrows():
            with st.container():
                left, right = st.columns([0.92, 0.08], vertical_alignment="center")
                with left:
                    title = f"{row.get('manufacturer','')} {row.get('model','')}"
                    st.markdown(f"**{title}**")
                    st.caption(
                        f"심각도: {row.get('severity','-')} · 상태: {row.get('status','-')} · "
                        f"리콜일: {row.get('recall_date','-')} · 대상: {row.get('affected_units','-')}"
                    )
                    st.write(str(row.get("reason", ""))[:220])
                with right:
                    st.button("상세", key=f"detail_{i}")
            st.divider()

# =========================
# 6) Tab: Stats (통계 대시보드)
# =========================
with tab_stats:
    st.markdown('<div class="section-title">통계</div>', unsafe_allow_html=True)

    # ---- KPI Row (4 cards) ----
    k1, k2, k3, k4 = st.columns(4, gap="large")

    total_recalls = int(len(df)) if not df.empty else 0
    total_units = int(df["affected_units"].fillna(0).sum()) if (not df.empty and "affected_units" in df.columns) else 0
    severe_cnt = int((df["severity"] == "위험").sum()) if (not df.empty and "severity" in df.columns) else 0
    mfg_cnt = int(df["manufacturer"].nunique()) if (not df.empty and "manufacturer" in df.columns) else 0

    def kpi(col, label, value, sub=""):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value">{value}</div>
                  <div class="kpi-sub">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    kpi(k1, "총 리콜 건수", f"{total_recalls:,}", f"기준일: {date.today().isoformat()}")
    kpi(k2, "총 영향 차량", f"{total_units:,}", "대상 차량 합계")
    kpi(k3, "위험 리콜", f"{severe_cnt:,}", "severity=위험")
    kpi(k4, "제조사 수", f"{mfg_cnt:,}", "고유 제조사")

    st.divider()

    # ---- 2x2 Charts Grid ----
    g1, g2 = st.columns(2, gap="large")
    g3, g4 = st.columns(2, gap="large")

    # 1) 제조사별 리콜 현황 (Bar)
    with g1:
        st.markdown("**제조사별 리콜 현황**")
        if df.empty:
            st.info("DB 연결 후 차트가 표시됩니다.")
        else:
            by_mfg = df.groupby("manufacturer", dropna=False).size().reset_index(name="count")
            fig = px.bar(by_mfg, x="manufacturer", y="count")
            st.plotly_chart(fig, use_container_width=True)

    # 2) 심각도별 분포 (Pie/Donut)
    with g2:
        st.markdown("**심각도별 분포**")
        if df.empty:
            st.info("DB 연결 후 차트가 표시됩니다.")
        else:
            by_sev = df.groupby("severity", dropna=False).size().reset_index(name="count")
            fig = px.pie(by_sev, names="severity", values="count", hole=0.45)
            st.plotly_chart(fig, use_container_width=True)

    # 3) 월별 리콜 추이 (Bar)
    with g3:
        st.markdown("**월별 리콜 추이**")
        if df.empty:
            st.info("DB 연결 후 차트가 표시됩니다.")
        else:
            tmp = df.copy()
            tmp["recall_date"] = pd.to_datetime(tmp["recall_date"], errors="coerce")
            tmp = tmp.dropna(subset=["recall_date"])
            tmp["ym"] = tmp["recall_date"].dt.to_period("M").astype(str)
            by_month = tmp.groupby("ym").size().reset_index(name="count").sort_values("ym")
            fig = px.bar(by_month, x="ym", y="count")
            st.plotly_chart(fig, use_container_width=True)

    # 4) 처리 상태별 분포 (Pie/Donut)
    with g4:
        st.markdown("**처리 상태별 분포**")
        if df.empty:
            st.info("DB 연결 후 차트가 표시됩니다.")
        else:
            by_status = df.groupby("status", dropna=False).size().reset_index(name="count")
            fig = px.pie(by_status, names="status", values="count", hole=0.45)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- Top Table ----
    st.markdown("**대상 리콜 현황 (대상 차량 기준)**")
    if df.empty:
        st.info("DB 연결 후 테이블이 표시됩니다.")
    else:
        # 대상 차량 대수 기준 Top 5
        top5 = (
            df.assign(affected_units=pd.to_numeric(df["affected_units"], errors="coerce").fillna(0).astype(int))
              .sort_values("affected_units", ascending=False)
              .head(5)
              .loc[:, ["manufacturer", "model", "reason", "affected_units", "severity", "status"]]
        )
        st.dataframe(top5, use_container_width=True, hide_index=True)
