# app.py
import streamlit as st
import pandas as pd

from recall_repo import (
    fetch_recalls,
    fetch_makers,
    fetch_year_range,
    fetch_kpi,
    fetch_maker_ranking,
    fetch_year_trend,
    fetch_model_ranking,
)

# =========================
# 0) 기본 설정
# =========================
st.set_page_config(page_title="Car Recall Information Site", layout="wide")
st.title("자동차 리콜 현황")


# =========================
# 1) 공통 옵션 로딩 (캐시)
# =========================
@st.cache_data(show_spinner=False)
def cached_makers(scope: str):
    return ["전체"] + fetch_makers(scope)


@st.cache_data(show_spinner=False)
def cached_years():
    min_y, max_y = fetch_year_range()
    return list(range(min_y, max_y + 1))


scopes = ["전체", "국내", "해외"]
years = cached_years()

tab_list, tab_stats = st.tabs(["리콜 목록", "통계"])


# =========================
# [탭 1] 리콜 목록
# =========================
with tab_list:
    st.subheader("필터")

    r1 = st.columns([1.0, 4.0])
    with r1[0]:
        scope_value = st.radio("구분(국내/해외)", scopes, horizontal=True, index=0)
    with r1[1]:
        st.empty()

    r2 = st.columns([1.3, 1.3, 3.0])

    with r2[0]:
        maker_options = cached_makers(scope_value)
        maker_value = st.selectbox("제작사", maker_options, index=0)

    # 제조 연도: "전체" 포함
    with r2[1]:
        year_options = ["전체"] + years
        manufacture_year_ui = st.selectbox("제조 연도", year_options, index=0)

    with r2[2]:
        search_text = st.text_input(
            "검색(제작사/차명)",
            placeholder="예: 현대, 아반떼, 무쏘 EV ...",
        ).strip()

    # UI 선택값 → DB 파라미터
    manufacture_year_param = None if manufacture_year_ui == "전체" else int(manufacture_year_ui)

    try:
        recalls = fetch_recalls(
            scope=scope_value,
            maker=maker_value,
            manufacture_year=manufacture_year_param,
            search_text=search_text,
            limit=500,
        )
    except Exception as e:
        st.error(str(e))
        st.stop()

    st.divider()
    st.subheader("리콜 목록 (최근순 카드형)")
    st.caption(f"총 {len(recalls):,}건 (최대 500건 표시)")

    if not recalls:
        st.info("조건에 해당하는 리콜 정보가 없습니다.")
    else:
        for r in recalls:
            with st.container(border=True):
                top = st.columns([1.2, 4.5, 1.3])

                with top[0]:
                    st.markdown(f"**구분**: {r.scope}")

                with top[1]:
                    st.markdown(f"**{r.maker}**  \n{r.car_name}")

                with top[2]:
                    st.markdown(f"**대상수량**  \n{int(r.target_units):,}대")

                st.markdown(f"**생산기간**: {r.start_date.date()} ~ {r.end_date.date()}")

                with st.expander("상세 보기", expanded=False):
                    st.markdown("**결함내용**")
                    st.text(r.defect_text)

                    st.markdown("**시정방법**")
                    st.write(r.fix_text)

                    st.markdown("**기타문의**")
                    st.write(r.contact_text)


# =========================
# [탭 2] 통계
# =========================
with tab_stats:
    st.subheader("통계")

    s1, s2, s3 = st.columns([1.2, 2.0, 1.5])

    with s1:
        stat_scope = st.selectbox("구분", scopes, index=0, key="stat_scope")

    with s2:
        stat_makers = cached_makers(stat_scope)
        stat_maker = st.selectbox("제작사", stat_makers, index=0, key="stat_maker")

    with s3:
        year_options = ["전체"] + years
        기준연도_ui = st.selectbox("기준 연도", year_options, index=0, key="stat_year")

    기준연도_param = None if 기준연도_ui == "전체" else int(기준연도_ui)

    # KPI
    try:
        total_cnt, total_units = fetch_kpi(stat_scope, stat_maker, 기준연도_param)
    except Exception as e:
        st.error(str(e))
        st.stop()

    k1, k2 = st.columns(2)
    k1.metric(
        "총 리콜 건수",
        f"{total_cnt:,}",
        help="기준 연도(제조연도 기준). '전체'는 연도 필터 미적용",
    )
    k2.metric(
        "대상 차량(누적 대수)",
        f"{total_units:,}",
        help="기준 연도(제조연도 기준). '전체'는 연도 필터 미적용",
    )

    st.divider()

    left, right = st.columns(2)

    # -------------------------
    # 제조사별 리콜 현황 (Bar)
    # -------------------------
    with left:
        st.markdown("### 제조사별 리콜 현황 (리콜 건수 기준)")
        rows = fetch_maker_ranking(stat_scope, stat_maker, 기준연도_param, top_n=20)

        if not rows:
            st.info("표시할 데이터가 없습니다.")
        else:
            # ✅ rows: List[Tuple[maker, recall_cnt]]
            df_maker = pd.DataFrame(rows, columns=["maker", "recall_cnt"])
            df_maker["recall_cnt"] = df_maker["recall_cnt"].astype(int)

            st.bar_chart(df_maker, x="maker", y="recall_cnt")

    # -------------------------
    # 연도별 리콜 추이 (Line)
    # -------------------------
    with right:
        st.markdown("### 연도별 리콜 추이")
        min_y, max_y = years[0], years[-1]
        trend = fetch_year_trend(stat_scope, stat_maker, min_y, max_y)

        if not trend:
            st.info("표시할 데이터가 없습니다.")
        else:
            # ✅ trend: List[Tuple[year, recall_cnt]]
            df_trend = pd.DataFrame(trend, columns=["year", "recall_cnt"])
            df_trend["year"] = df_trend["year"].astype(int)
            df_trend["recall_cnt"] = df_trend["recall_cnt"].astype(int)

            st.line_chart(df_trend, x="year", y="recall_cnt")

    st.divider()

    # -------------------------
    # 모델별 리콜 순위 (Table)
    # -------------------------
    st.markdown("### 모델별 리콜 순위 (건수 기준)")
    model_rows = fetch_model_ranking(stat_scope, stat_maker, 기준연도_param, top_n=20)

    if not model_rows:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.table([{"car_name": name, "recall_cnt": int(cnt)} for name, cnt in model_rows])