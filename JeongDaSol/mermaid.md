```mermaid
erDiagram
    tbl_manufacturer {
        int maker_id PK "제조사 ID"
        varchar maker_name "제조사명"
        varchar maker_detail "제조사 상세 설명"
        varchar region_at "제조 국가/지역"
    }

    tbl_model {
        int model_id PK "모델 ID"
        int maker_id FK "제조사 ID"
        varchar model_name "모델명"
        datetime start_date "제조 시작일"
        datetime end_date "제조 종료일"
    }

    tbl_recall {
        int recall_id PK "리콜 고유 ID"
        int model_id PK, FK "모델 ID"
        varchar recall_title "리콜 제목"
        varchar recall_type "리콜 유형"
        text defect_desc "결함 내용"
        text fix_method "조치 방법"
        varchar recall_center "리콜 접수 기관"
        int recall_quantity "리콜 수량"
        varchar recall_date "리콜 기간/일자"
        varchar device_type "장치 분류"
    }

    tbl_manufacturer ||--o{ tbl_model : "1:N"
    tbl_model ||--o{ tbl_recall : "1:N"
