# recall_repo.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Tuple

import mysql.connector


# =========================
# 1) DB CONFIG
# =========================
DB_CONFIG = {
    "host": "192.168.2.76",
    "port": 3306,
    "user": "yhjeon0315",
    "password": "yhjeon0315",
    "database": "motor_chata",
}


# =========================
# 2) DTO (Streamlit에서 쓸 모델)
# =========================
@dataclass
class RecallView:
    scope: str
    maker: str
    car_name: str
    start_date: datetime
    end_date: datetime
    target_units: int
    defect_text: str
    fix_text: str
    contact_text: str


# =========================
# 3) 공통 WHERE 빌더
#    - Streamlit에서 전달받은 필터를 SQL WHERE로 변환
# =========================
def _build_where(
    scope: str,
    maker: str,
    manufacture_year: Optional[int],
    search_text: str,
) -> Tuple[str, List]:
    where = []
    params: List = []

    # scope: "전체"면 미적용, 아니면 제조사 테이블의 region_at으로 필터
    if scope != "전체":
        where.append("mf.region_at = %s")
        params.append(scope)

    # maker: "전체"면 미적용, 아니면 제조사명 필터
    if maker != "전체":
        where.append("mf.maker_name = %s")
        params.append(maker)

    # 제조연도: 기간 겹침 포함 (start_date <= 12/31 AND end_date >= 01/01)
    if manufacture_year is not None:
        y_start = date(manufacture_year, 1, 1)
        y_end = date(manufacture_year, 12, 31)
        where.append("md.start_date <= %s AND md.end_date >= %s")
        params.extend([y_end, y_start])

    # 검색: 제조사/차명
    s = (search_text or "").strip()
    if s:
        where.append(
            "(mf.maker_name LIKE CONCAT('%', %s, '%') OR md.model_name LIKE CONCAT('%', %s, '%'))"
        )
        params.extend([s, s])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return where_sql, params


# =========================
# 4) 리콜 목록 조회 (카드 리스트용)
# =========================
def fetch_recalls(
    scope: str = "전체",
    maker: str = "전체",
    manufacture_year: Optional[int] = None,
    search_text: str = "",
    limit: int = 500,
) -> List[RecallView]:
    where_sql, params = _build_where(scope, maker, manufacture_year, search_text)

    sql = f"""
        SELECT
            COALESCE(mf.region_at, '')        AS scope,
            COALESCE(mf.maker_name, '')       AS maker,
            COALESCE(md.model_name, '')       AS car_name,
            md.start_date                     AS start_date,
            md.end_date                       AS end_date,
            COALESCE(rc.recall_quantity, 0)   AS target_units,
            COALESCE(rc.defect_desc, '')      AS defect_text,
            COALESCE(rc.fix_method, '')       AS fix_text,
            COALESCE(rc.recall_center, '')    AS contact_text
        FROM tbl_recall rc
        JOIN tbl_model md
          ON rc.model_id = md.model_id
        JOIN tbl_manufacturer mf
          ON md.maker_id = mf.maker_id
        {where_sql}
        ORDER BY md.end_date DESC
        LIMIT %s
    """

    params.append(int(limit))

    out: List[RecallView] = []

    try:
        with mysql.connector.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                for row in cursor.fetchall():
                    out.append(RecallView(*row))
    except mysql.connector.Error as err:
        raise RuntimeError(f"DB 오류(fetch_recalls): {err}")

    return out


# =========================
# 5) 옵션 데이터: 제작사 목록
#    - scope="전체"면 합산
# =========================
def fetch_makers(scope: str = "전체") -> List[str]:
    where_sql = ""
    params: List = []

    if scope != "전체":
        where_sql = "WHERE region_at = %s"
        params.append(scope)

    sql = f"""
        SELECT DISTINCT maker_name
        FROM tbl_manufacturer
        {where_sql}
        ORDER BY maker_name
    """

    out: List[str] = []
    try:
        with mysql.connector.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                for (maker_name,) in cursor.fetchall():
                    if maker_name:
                        out.append(maker_name)
    except mysql.connector.Error as err:
        raise RuntimeError(f"DB 오류(fetch_makers): {err}")

    return out


# =========================
# 6) 옵션 데이터: 제조 연도 범위(최소~최대)
# =========================
def fetch_year_range() -> Tuple[int, int]:
    sql = """
        SELECT
            MIN(YEAR(start_date)) AS min_year,
            MAX(YEAR(end_date))   AS max_year
        FROM tbl_model
        WHERE start_date IS NOT NULL
          AND end_date IS NOT NULL
    """

    try:
        with mysql.connector.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if not row or row[0] is None or row[1] is None:
                    # 데이터가 없거나 NULL이면 fallback
                    return 2000, datetime.now().year
                return int(row[0]), int(row[1])
    except mysql.connector.Error as err:
        raise RuntimeError(f"DB 오류(fetch_year_range): {err}")


# =========================
# 7) 통계: KPI (건수/대수)
# =========================
def fetch_kpi(scope: str, maker: str, year: int) -> Tuple[int, int]:
    where_sql, params = _build_where(scope, maker, year, search_text="")

    sql = f"""
        SELECT
            COUNT(*) AS recall_cnt,
            COALESCE(SUM(COALESCE(rc.recall_quantity, 0)), 0) AS total_units
        FROM tbl_recall rc
        JOIN tbl_model md
          ON rc.model_id = md.model_id
        JOIN tbl_manufacturer mf
          ON md.maker_id = mf.maker_id
        {where_sql}
    """

    try:
        with mysql.connector.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                cnt, units = cursor.fetchone()
                return int(cnt or 0), int(units or 0)
    except mysql.connector.Error as err:
        raise RuntimeError(f"DB 오류(fetch_kpi): {err}")


# =========================
# 8) 통계: 제조사별 리콜 건수 TOP N
# =========================
def fetch_maker_ranking(scope: str, maker: str, year: int, top_n: int = 20):
    # maker 필터가 "전체"가 아니면 '해당 maker만' 나와서 랭킹 의미가 줄어듦.
    # 하지만 사용자가 선택한 maker를 존중해 동일 필터로 집계합니다.
    where_sql, params = _build_where(scope, maker, year, search_text="")

    sql = f"""
        SELECT
            mf.maker_name AS maker,
            COUNT(*)      AS recall_cnt
        FROM tbl_recall rc
        JOIN tbl_model md
          ON rc.model_id = md.model_id
        JOIN tbl_manufacturer mf
          ON md.maker_id = mf.maker_id
        {where_sql}
        GROUP BY mf.maker_name
        ORDER BY recall_cnt DESC
        LIMIT %s
    """
    params.append(int(top_n))

    rows = []
    try:
        with mysql.connector.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
    except mysql.connector.Error as err:
        raise RuntimeError(f"DB 오류(fetch_maker_ranking): {err}")

    return rows  # List[Tuple[maker, recall_cnt]]


# =========================
# 9) 통계: 연도별 추이 (리스트로 반환)
# =========================
def fetch_year_trend(scope: str, maker: str, min_year: int, max_year: int):
    # 연도별로 기간 겹침 집계를 해야 해서 SQL을 연도별로 한 번에 만들기 까다롭습니다.
    # 여기서는 안정성을 우선해 "연도별 반복 호출"로 구현합니다(연도 범위가 크지 않다는 전제).
    trend = []
    for y in range(min_year, max_year + 1):
        cnt, _ = fetch_kpi(scope, maker, y)
        trend.append((y, cnt))
    return trend  # List[Tuple[year, recall_cnt]]


# =========================
# 10) 통계: 모델별 리콜 순위 TOP N
# =========================
def fetch_model_ranking(scope: str, maker: str, year: int, top_n: int = 20):
    where_sql, params = _build_where(scope, maker, year, search_text="")

    sql = f"""
        SELECT
            md.model_name AS car_name,
            COUNT(*)      AS recall_cnt
        FROM tbl_recall rc
        JOIN tbl_model md
          ON rc.model_id = md.model_id
        JOIN tbl_manufacturer mf
          ON md.maker_id = mf.maker_id
        {where_sql}
        GROUP BY md.model_name
        ORDER BY recall_cnt DESC
        LIMIT %s
    """
    params.append(int(top_n))

    rows = []
    try:
        with mysql.connector.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
    except mysql.connector.Error as err:
        raise RuntimeError(f"DB 오류(fetch_model_ranking): {err}")

    return rows  # List[Tuple[car_name, recall_cnt]]