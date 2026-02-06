# app.py
# ============================================================
# 목적
# - ERD 기반 DB(tbl_region, tbl_manufacturer, tbl_model, tbl_device, tbl_recall)에서 데이터 조회
# - Streamlit: [리콜 목록] + [통계] 2개 탭
# - CSV 업로드 UI 제거 (DB만 사용)
#
# 카드(리콜 목록) 표시 항목(요청 반영)
# - region_type(국내/해외), maker_name(제작사), model_name(차명)
# - device_type, recall_center, recall_date
# - recall_title, recall_type, recall_quantity
# - defect_desc, fix_method
#
# 필터/검색
# - 구분(region_type): 전체/국내/해외
# - 제작사(maker_name): 구분 선택 시 해당 구분의 제작사만 노출
# - 제조연도(manufacture_year): tbl_manufacturer.start_date ~ end_date 범위가 해당 연도와 겹치면 포함
# - 검색: 제작사(maker_name) + 차명(model_name)
#
# 통계(요청 반영)
# 1) 총 리콜 건수(기준 연도)
# 2) 대상 차량(누적 대수) = recall_quantity 합
# 3) 제조사별 리콜현황(리콜 건수 기준)  +  4) 연도별 리콜추이(좌/우 배치)
# 5) 모델별 리콜 순위(건수 기준)
#
# 실행
# - pip install streamlit pandas
# - streamlit run app.py
# ============================================================

import sqlite3
from datetime import date
import pandas as pd
import streamlit as st


# ============================================================
# 0) 기본 설정
# ============================================================
st.set_page_config(page_title="Car Recall Information Site", layout="wide")

# ✅ DB 파일 경로(필요 시 수정)
DB_PATH = "recalls.db"


# ============================================================
# 1) DB 커넥션/유틸
# ============================================================
def get_conn():
    # Streamlit 멀티스레드 이슈 방지
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def coalesce_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def safe_df(df: pd.DataFrame) -> pd.DataFrame:
    # pandas read_sql 결과가 비어도 안정적으로 처리하기 위한 방어
    if df is None:
        return pd.DataFrame()
    return df


# ============================================================
# 2) 옵션 로딩(구분/제작사/연도 범위)
# ============================================================
@st.cache_data(show_spinner=False)
def load_scopes(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    df = pd.read_sql(
        """
        SELECT DISTINCT region_type
        FROM tbl_region
        WHERE region_type IS NOT NULL AND region_type <> ''
        ORDER BY region_type
        """,
        conn,
    )
    conn.close()
    return df["region_type"].tolist()


def load_makers_by_scope(conn: sqlite3.Connection, region_type: str) -> list[str]:
    # region_type="전체"면 전체 제작사
    if region_type == "전체":
        df = pd.read_sql(
            """
            SELECT DISTINCT m.maker_name
            FROM tbl_manufacturer m
            WHERE m.maker_name IS NOT NULL AND m.maker_name <> ''
            ORDER BY m.maker_name
            """,
            conn,
        )
        return df["maker_name"].tolist()

    df = pd.read_sql(
        """
        SELECT DISTINCT m.maker_name
        FROM tbl_manufacturer m
        JOIN tbl_region r ON r.region_id = m.region_id
        WHERE r.region_type = ?
          AND m.maker_name IS NOT NULL AND m.maker_name <> ''
        ORDER BY m.maker_name
        """,
        conn,
        params=[region_type],
    )
    return df["maker_name"].tolist()


@st.cache_data(show_spinner=False)
def load_year_range(db_path: str):
    # 제조연도 필터 기준: tbl_manufacturer.start_date/end_date (ERD 반영)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    df = pd.read_sql(
        """
        SELECT
            MIN(CAST(strftime('%Y', start_date) AS INTEGER)) AS min_year,
            MAX(CAST(strftime('%Y', end_date)   AS INTEGER)) AS max_year
        FROM tbl_manufacturer
        WHERE start_date IS NOT NULL AND end_date IS NOT NULL
        """,
        conn,
    )
    conn.close()

    if df.empty or pd.isna(df.loc[0, "min_year"]) or pd.isna(df.loc[0, "max_year"]):
        return None, None

    return int(df.loc[0, "min_year"]), int(df.loc[0, "max_year"])


def compute_year_list(min_year: int | None, max_year: int | None) -> list[int]:
    # 요구사항: 루프(range)로 연도 생성
    if min_year is None or max_year is None:
        return []
    years = []
    for y in range(min_year, max_year + 1):
        years.append(y)
    return years


# ============================================================
# 3) 리콜 목록 조회(ERD 조인)
# ============================================================
def query_recalls(
    conn: sqlite3.Connection,
    region_type: str,
    maker_name: str,
    manufacture_year: int | None,
    keyword: str,
    limit: int = 500,
) -> pd.DataFrame:
    """
    조인 구조(ERD)
    tbl_recall -> tbl_device -> tbl_model -> tbl_manufacturer -> tbl_region
    """
    where = []
    params = []

    # 구분(국내/해외)
    if region_type != "전체":
        where.append("rgn.region_type = ?")
        params.append(region_type)

    # 제작사
    if maker_name != "전체":
        where.append("m.maker_name = ?")
        params.append(maker_name)

    # 제조연도(단일) - start_date/end_date 기간이 해당 연도와 "겹치면 포함"
    # m.start_date <= Y-12-31 AND m.end_date >= Y-01-01
    if manufacture_year is not None:
        y_start = date(manufacture_year, 1, 1).isoformat()
        y_end = date(manufacture_year, 12, 31).isoformat()
        where.append("(DATE(m.start_date) <= DATE(?) AND DATE(m.end_date) >= DATE(?))")
        params.extend([y_end, y_start])

    # 검색: 제작사 + 차명
    kw = (keyword or "").strip()
    if kw:
        where.append("(m.maker_name LIKE ? OR mdl.model_name LIKE ?)")
        like = f"%{kw}%"
        params.extend([like, like])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
            rgn.region_type,
            m.maker_name,
            mdl.model_name,
            d.device_type,

            rc.recall_title,
            rc.recall_type,
            rc.defect_desc,
            rc.fix_method,
            rc.recall_center,
            rc.recall_quantity,
            rc.recall_date,

            m.start_date AS manufacture_start_date,
            m.end_date   AS manufacture_end_date
        FROM tbl_recall rc
        JOIN tbl_device d        ON d.device_id = rc.device_id
        JOIN tbl_model  mdl      ON mdl.model_id = d.model_id
        JOIN tbl_manufacturer m  ON m.maker_id = mdl.maker_id
        JOIN tbl_region rgn      ON rgn.region_id = m.region_id
        {where_sql}
        ORDER BY DATE(rc.recall_date) DESC, rc.recall_id DESC
        LIMIT {int(limit)}
    """

    df = pd.read_sql(sql, conn, params=params)
    df = safe_df(df)

    # 숫자형 안전 보정
    if not df.empty and "recall_quantity" in df.columns:
        df["recall_quantity"] = pd.to_numeric(df["recall_quantity"], errors="coerce").fillna(0).astype(int)

    return df


# ============================================================
# 4) 통계 쿼리(ERD 조인 + 집계)
# ============================================================
def base_filtered_view(
    conn: sqlite3.Connection,
    region_type: str,
    maker_name: str,
) -> pd.DataFrame:
    """
    통계용 기본 뷰(필터: 구분/제작사만 적용)
    - 연도별 지표는 recall_date 기준 연도로 계산
    """
    where = []
    params = []

    if region_type != "전체":
        where.append("rgn.region_type = ?")
        params.append(region_type)

    if maker_name != "전체":
        where.append("m.maker_name = ?")
        params.append(maker_name)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
            rgn.region_type,
            m.maker_name,
            mdl.model_name,
            rc.recall_quantity,
            rc.recall_date
        FROM tbl_recall rc
        JOIN tbl_device d        ON d.device_id = rc.device_id
        JOIN tbl_model  mdl      ON mdl.model_id = d.model_id
        JOIN tbl_manufacturer m  ON m.maker_id = mdl.maker_id
        JOIN tbl_region rgn      ON rgn.region_id = m.region_id
        {where_sql}
    """
    df = pd.read_sql(sql, conn, params=params)
    df = safe_df(df)

    if not df.empty:
        df["recall_quantity"] = pd.to_numeric(df["recall_quantity"], errors="coerce").fillna(0).astype(int)
        # recall_date에서 year 추출(실패 시 NaN)
        df["recall_year"] = pd.to_datetime(df["recall_date"], errors="coerce").dt.year

    return df


def stats_kpi(df: pd.DataFrame, 기준연도: int):
    base_year = df[df["recall_year"] == 기준연도] if not df.empty else pd.DataFrame()
    total_cnt = int(len(base_year))
    total_units = int(base_year["recall_quantity"].sum()) if not base_year.empty else 0
    return total_cnt, total_units


def stats_maker_count(df: pd.DataFrame, 기준연도: int):
    base_year = df[df["recall_year"] == 기준연도]
    if base_year.empty:
        return pd.DataFrame(columns=["maker_name", "recall_cnt"])
    out = (
        base_year.groupby("maker_name", as_index=False)
        .size()
        .rename(columns={"size": "recall_cnt"})
        .sort_values("recall_cnt", ascending=False)
        .head(20)
    )
    return out


def stats_year_trend(df: pd.DataFrame, years: list[int]):
    rows = []
    for y in years:
        cnt = int((df["recall_year"] == y).sum()) if not df.empty else 0
        rows.append({"year": y, "recall_cnt": cnt})
    return pd.DataFrame(rows)


def stats_model_ranking(df: pd.DataFrame, 기준연도: int):
    base_year = df[df["recall_year"] == 기준연도]
    if base_year.empty:
        return pd.DataFrame(columns=["model_name", "recall_cnt"])
    out = (
        base_year.groupby("model_name", as_index=False)
        .size()
        .rename(columns={"size": "recall_cnt"})
        .sort_values("recall_cnt", ascending=False)
        .head(20)
    )
    return out


# ============================================================
# 5) Streamlit UI
# ============================================================
st.title("자동차 리콜 현황")
st.caption("ERD 기반 DB 조회 버전 (CSV 업로드 UI 제거)")

# DB 연결 체크
try:
    conn = get_conn()
except Exception as e:
    st.error(f"DB 연결 실패: {e}")
    st.stop()

# 공통 옵션 로딩
scopes = load_scopes(DB_PATH)
scope_options = ["전체"] + (scopes if scopes else ["국내", "해외"])

min_y, max_y = load_year_range(DB_PATH)
years = compute_year_list(min_y, max_y)

tab_list, tab_stats = st.tabs(["리콜 목록", "통계"])


# ============================================================
# [탭 1] 리콜 목록
# ============================================================
with tab_list:
    st.subheader("필터")

    c1, c2, c3, c4 = st.columns([1.2, 2.0, 1.3, 2.0])

    with c1:
        region_type = st.radio("구분(국내/해외)", scope_options, horizontal=True, index=0)

    with c2:
        maker_options = ["전체"] + load_makers_by_scope(conn, region_type)
        maker_name = st.selectbox("제작사", maker_options, index=0)

    with c3:
        if years:
            manufacture_year = st.selectbox("제조 연도", years, index=len(years) - 1)
        else:
            manufacture_year = None
            st.selectbox("제조 연도", ["데이터 없음"], index=0)

    with c4:
        keyword = st.text_input("검색(제작사/차명)", placeholder="예: 현대, 아반떼, BMW i5 ...").strip()

    st.divider()

    df = query_recalls(
        conn=conn,
        region_type=region_type,
        maker_name=maker_name,
        manufacture_year=manufacture_year,
        keyword=keyword,
        limit=500,
    )

    st.subheader("리콜 목록 (최근순 카드형)")
    st.caption(f"총 {len(df):,}건 (최대 500건 표시)")

    if df.empty:
        st.info("조건에 해당하는 리콜 정보가 없습니다.")
    else:
        for _, r in df.iterrows():
            with st.container(border=True):
                top = st.columns([1.2, 4.5, 1.6])

                with top[0]:
                    st.markdown(f"**구분**: {r['region_type']}")
                    st.markdown(f"**장치분류**: {r['device_type']}")

                with top[1]:
                    st.markdown(f"**{r['maker_name']}**  \n{r['model_name']}")
                    st.markdown(f"**리콜명**: {r['recall_title']}")
                    st.markdown(f"**리콜유형**: {r['recall_type']}")

                with top[2]:
                    st.markdown(f"**리콜일**  \n{r['recall_date']}")
                    st.markdown(f"**대상수량**  \n{coalesce_int(r['recall_quantity']):,}대")
                    st.markdown(f"**문의처**  \n{r['recall_center']}")

                # 제조기간(ERD 상 manufacturer에 있음)
                st.markdown(
                    f"**제조기간(ERD 기준)**: {r['manufacture_start_date']} ~ {r['manufacture_end_date']}"
                )

                with st.expander("상세 보기", expanded=False):
                    st.markdown("**결함내용(defect_desc)**")
                    st.write(r["defect_desc"])

                    st.markdown("**시정방법(fix_method)**")
                    st.write(r["fix_method"])


# ============================================================
# [탭 2] 통계
# ============================================================
with tab_stats:
    st.subheader("통계")

    s1, s2, s3 = st.columns([1.2, 2.0, 1.5])

    with s1:
        stat_region = st.selectbox("구분", scope_options, index=0, key="stat_region")

    with s2:
        stat_maker_options = ["전체"] + load_makers_by_scope(conn, stat_region)
        stat_maker = st.selectbox("제작사", stat_maker_options, index=0, key="stat_maker")

    with s3:
        if years:
            기준연도 = st.selectbox("기준 연도", years, index=len(years) - 1, key="stat_year")
        else:
            기준연도 = None
            st.selectbox("기준 연도", ["데이터 없음"], index=0, key="stat_year_dummy")

    if 기준연도 is None:
        st.info("연도 데이터가 없어 통계를 표시할 수 없습니다.")
    else:
        base = base_filtered_view(conn, stat_region, stat_maker)

        total_cnt, total_units = stats_kpi(base, 기준연도)
        k1, k2 = st.columns(2)
        k1.metric("총 리콜 건수", f"{total_cnt:,}", help="기준 연도(recall_date 기준)")
        k2.metric("대상 차량(누적 대수)", f"{total_units:,}", help="기준 연도(recall_date 기준)")

        st.divider()

        # ✅ 차트 2개를 양옆으로 배치
        left, right = st.columns(2)

        with left:
            st.markdown("### 제조사별 리콜 현황 (리콜 건수 기준)")
            df_maker = stats_maker_count(base, 기준연도)
            if df_maker.empty:
                st.info("표시할 데이터가 없습니다.")
            else:
                st.bar_chart(df_maker.set_index("maker_name")["recall_cnt"])

        with right:
            st.markdown("### 연도별 리콜 추이")
            df_tr = stats_year_trend(base, years)
            st.line_chart(df_tr.set_index("year")["recall_cnt"])

        st.divider()

        st.markdown("### 모델별 리콜 순위 (건수 기준)")
        df_model = stats_model_ranking(base, 기준연도)
        st.dataframe(df_model, use_container_width=True)

# 연결 종료
conn.close()