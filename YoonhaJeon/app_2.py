# app.py
# ============================================================
# 목적
# - Streamlit에서 CSV 업로드로 즉시 실행 가능
# - [리콜 목록] 필터/검색 + 카드형 리스트
# - [통계] KPI + 차트(좌/우 배치) + 모델 순위
#
# 수정 반영
# 1) 통계에서 "전체" 필터 선택 시 국내/해외 합산으로 정상 집계되도록 안정화
# 2) 제조사별 리콜현황 + 연도별 리콜추이를 좌/우로 배치
# ============================================================

import re
from datetime import datetime, date

import pandas as pd
import streamlit as st


# ============================================================
# 0) 기본 설정
# ============================================================
st.set_page_config(page_title="Car Recall Information Site", layout="wide")


# ============================================================
# 1) 전처리 유틸
# ============================================================
def parse_units_to_int(s: str) -> int:
    if s is None:
        return 0
    s = str(s).strip()
    if not s:
        return 0
    digits = re.sub(r"[^0-9]", "", s)
    return int(digits) if digits else 0


def parse_period_to_dates(period: str):
    if period is None:
        return None, None
    period = str(period).strip()
    if "~" not in period:
        return None, None

    left, right = [x.strip() for x in period.split("~", 1)]
    try:
        start_dt = datetime.strptime(left, "%Y-%m-%d").date().isoformat()
        end_dt = datetime.strptime(right, "%Y-%m-%d").date().isoformat()
        return start_dt, end_dt
    except Exception:
        return None, None


def preprocess_csv(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = ["구분", "제작사", "차명", "생산기간", "대상수량", "결함내용", "시정방법", "기타문의"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV에 필수 컬럼이 없습니다: {missing}")

    start_dates, end_dates = [], []
    for p in df["생산기간"].tolist():
        sdt, edt = parse_period_to_dates(p)
        start_dates.append(sdt)
        end_dates.append(edt)

    out = pd.DataFrame(
        {
            "scope": df["구분"].astype(str),
            "maker": df["제작사"].astype(str),
            "car_name": df["차명"].astype(str),
            "start_date": start_dates,
            "end_date": end_dates,
            "target_units": df["대상수량"].map(parse_units_to_int),
            "defect_text": df["결함내용"].astype(str),
            "fix_text": df["시정방법"].astype(str),
            "contact_text": df["기타문의"].astype(str),
        }
    )

    # 날짜 결측 제거
    out = out.dropna(subset=["start_date", "end_date"]).copy()

    # 안전장치: 숫자형 보장
    out["target_units"] = pd.to_numeric(out["target_units"], errors="coerce").fillna(0).astype(int)

    return out


# ============================================================
# 2) 업로드 데이터 로딩
# ============================================================
@st.cache_data(show_spinner=False)
def load_data_from_upload(uploaded_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(pd.io.common.BytesIO(uploaded_bytes))
    return preprocess_csv(df)


# ============================================================
# 3) 공통 로직
# ============================================================
def compute_year_list(df: pd.DataFrame):
    min_y = df["start_date"].str[:4].astype(int).min()
    max_y = df["end_date"].str[:4].astype(int).max()

    years = []
    for y in range(min_y, max_y + 1):
        years.append(y)
    return years


def makers_by_scope(df: pd.DataFrame, scope_value: str):
    # scope_value="전체"면 국내/해외 합산 제작사 목록
    if scope_value == "전체":
        return sorted(df["maker"].dropna().unique().tolist())
    return sorted(df.loc[df["scope"] == scope_value, "maker"].dropna().unique().tolist())


def filter_by_manufacture_year(df: pd.DataFrame, y: int):
    # 기간 겹침 포함
    y_start = date(y, 1, 1).isoformat()
    y_end = date(y, 12, 31).isoformat()
    return df[(df["start_date"] <= y_end) & (df["end_date"] >= y_start)]


# --- 통계용 집계 ---
def kpi_total_recall_count(df: pd.DataFrame, 기준연도: int):
    return int(len(filter_by_manufacture_year(df, 기준연도)))


def kpi_total_units(df: pd.DataFrame, 기준연도: int):
    return int(filter_by_manufacture_year(df, 기준연도)["target_units"].sum())


def maker_recall_count(df: pd.DataFrame, 기준연도: int):
    base = filter_by_manufacture_year(df, 기준연도)
    out = base.groupby("maker", as_index=False).size().rename(columns={"size": "recall_cnt"})
    return out.sort_values("recall_cnt", ascending=False).head(20)


def year_trend(df: pd.DataFrame, years: list[int]):
    rows = []
    for y in years:
        cnt = len(filter_by_manufacture_year(df, y))
        rows.append({"year": y, "recall_cnt": int(cnt)})
    return pd.DataFrame(rows)


def model_ranking(df: pd.DataFrame, 기준연도: int):
    base = filter_by_manufacture_year(df, 기준연도)
    out = base.groupby("car_name", as_index=False).size().rename(columns={"size": "recall_cnt"})
    return out.sort_values("recall_cnt", ascending=False).head(20)


# ============================================================
# 4) UI
# ============================================================
st.title("자동차 리콜 현황")
st.caption("CSV 업로드 기반 MVP")

with st.expander("데이터 업로드 (CSV)", expanded=True):
    uploaded = st.file_uploader("CSV 업로드", type=["csv"])

if uploaded is None:
    st.info("CSV를 업로드하면 화면이 표시됩니다.")
    st.stop()

try:
    df_all = load_data_from_upload(uploaded.getvalue())
except Exception as e:
    st.error(f"CSV 로딩/전처리 실패: {e}")
    st.stop()

# 공통 옵션
scopes = ["전체"] + sorted(df_all["scope"].dropna().unique().tolist())
years = compute_year_list(df_all)

tab_list, tab_stats = st.tabs(["리콜 목록", "통계"])


# ----------------------------
# [탭 1] 리콜 목록
# ----------------------------
with tab_list:
    st.subheader("필터")

    c1, c2, c3, c4 = st.columns([1.2, 2.0, 1.3, 2.0])

    with c1:
        scope_value = st.radio("구분(국내/해외)", scopes, horizontal=True, index=0)

    with c2:
        maker_options = ["전체"] + makers_by_scope(df_all, scope_value)
        maker_value = st.selectbox("제작사", maker_options, index=0)

    with c3:
        manufacture_year = st.selectbox("제조 연도", years, index=len(years) - 1)

    with c4:
        search_text = st.text_input("검색(제작사/차명)", placeholder="예: 현대, 아반떼, BMW i5 ...").strip()

    df = df_all.copy()
    if scope_value != "전체":
        df = df[df["scope"] == scope_value]
    if maker_value != "전체":
        df = df[df["maker"] == maker_value]

    df = filter_by_manufacture_year(df, manufacture_year)

    if search_text:
        df = df[
            df["maker"].str.contains(search_text, case=False, na=False)
            | df["car_name"].str.contains(search_text, case=False, na=False)
        ]

    df = df.sort_values("end_date", ascending=False).head(500)

    st.divider()
    st.subheader("리콜 목록 (최근순 카드형)")
    st.caption(f"총 {len(df):,}건 (최대 500건 표시)")

    if df.empty:
        st.info("조건에 해당하는 리콜 정보가 없습니다.")
    else:
        for _, r in df.iterrows():
            with st.container(border=True):
                top = st.columns([1.2, 4.5, 1.3])

                with top[0]:
                    st.markdown(f"**구분**: {r['scope']}")
                with top[1]:
                    st.markdown(f"**{r['maker']}**  \n{r['car_name']}")
                with top[2]:
                    st.markdown(f"**대상수량**  \n{int(r['target_units']):,}대")

                st.markdown(f"**생산기간**: {r['start_date']} ~ {r['end_date']}")

                with st.expander("상세 보기", expanded=False):
                    st.markdown("**결함내용**")
                    st.write(r["defect_text"])
                    st.markdown("**시정방법**")
                    st.write(r["fix_text"])
                    st.markdown("**기타문의**")
                    st.write(r["contact_text"])


# ----------------------------
# [탭 2] 통계
# ----------------------------
with tab_stats:
    st.subheader("통계")

    s1, s2, s3 = st.columns([1.2, 2.0, 1.5])

    with s1:
        stat_scope = st.selectbox("구분", scopes, index=0, key="stat_scope")

    with s2:
        # ✅ stat_scope="전체"면 국내/해외 합산 제작사 목록이 뜨도록 보장
        stat_makers = ["전체"] + makers_by_scope(df_all, stat_scope)
        stat_maker = st.selectbox("제작사", stat_makers, index=0, key="stat_maker")

    with s3:
        기준연도 = st.selectbox("기준 연도", years, index=len(years) - 1, key="stat_year")

    # ✅ 통계 베이스 DF 구성: "전체"면 필터 미적용(= 국내/해외 합산)
    base = df_all.copy()
    if stat_scope != "전체":
        base = base[base["scope"] == stat_scope]
    if stat_maker != "전체":
        base = base[base["maker"] == stat_maker]

    # KPI
    total_cnt = kpi_total_recall_count(base, 기준연도)
    total_units = kpi_total_units(base, 기준연도)

    k1, k2 = st.columns(2)
    k1.metric("총 리콜 건수", f"{total_cnt:,}", help="선택한 기준 연도(제조연도 기준)")
    k2.metric("대상 차량(누적 대수)", f"{total_units:,}", help="선택한 기준 연도(제조연도 기준)")

    st.divider()

    # ✅ 차트 2개를 좌/우 배치
    left, right = st.columns(2)

    with left:
        st.markdown("### 제조사별 리콜 현황 (리콜 건수 기준)")
        df_maker = maker_recall_count(base, 기준연도)
        if df_maker.empty:
            st.info("표시할 데이터가 없습니다.")
        else:
            st.bar_chart(df_maker.set_index("maker")["recall_cnt"])

    with right:
        st.markdown("### 연도별 리콜 추이")
        df_tr = year_trend(base, years)
        st.line_chart(df_tr.set_index("year")["recall_cnt"])

    st.divider()

    st.markdown("### 모델별 리콜 순위 (건수 기준)")
    df_model = model_ranking(base, 기준연도)
    st.dataframe(df_model, use_container_width=True)