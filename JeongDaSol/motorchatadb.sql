-- 1. 제조사 정보 (tbl_manufacturer)
-- motor_chata.tbl_manufacturer definition

CREATE TABLE `tbl_manufacturer` (
  `maker_id` int NOT NULL AUTO_INCREMENT COMMENT '제조사 ID',
  `maker_name` varchar(30) NOT NULL COMMENT '제조사명',
  `maker_detail` varchar(50) DEFAULT NULL COMMENT '제조사 상세 설명',
  `region_at` varchar(10) DEFAULT NULL COMMENT '제조 국가/지역',
  PRIMARY KEY (`maker_id`),
  KEY `idx_manufacturer_name` (`maker_name`),
  KEY `idx_manufacturer_region` (`region_at`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- 2. 모델 정보 (tbl_model)
CREATE TABLE `tbl_model` (
  `model_id` int NOT NULL AUTO_INCREMENT COMMENT '모델 ID',
  `maker_id` int NOT NULL COMMENT '제조사 ID',
  `model_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '모델명',
  `start_date` datetime DEFAULT NULL COMMENT '제조 시작일',
  `end_date` datetime DEFAULT NULL COMMENT '제조 종료일',
  PRIMARY KEY (`model_id`),
  KEY `idx_model_maker` (`maker_id`),
  KEY `idx_model_name` (`model_name`),
  CONSTRAINT `fk_model_maker` FOREIGN KEY (`maker_id`) REFERENCES `tbl_manufacturer` (`maker_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=256 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- 3. 리콜 정보 (tbl_recall)
CREATE TABLE `tbl_recall` (
  `recall_id` int NOT NULL COMMENT '리콜 고유 ID(외부 기준)',
  `model_id` int NOT NULL COMMENT '모델 ID',
  `recall_title` varchar(255) NOT NULL COMMENT '리콜 제목',
  `recall_type` varchar(50) DEFAULT NULL COMMENT '리콜 유형',
  `defect_desc` text COMMENT '결함 내용',
  `fix_method` text COMMENT '조치 방법',
  `recall_center` varchar(255) DEFAULT NULL COMMENT '리콜 접수 기관',
  `recall_quantity` int DEFAULT NULL COMMENT '리콜 수량',
  `recall_date` varchar(30) DEFAULT NULL COMMENT '리콜 기간/일자',
  `device_type` varchar(50) NOT NULL COMMENT '장치 분류',
  PRIMARY KEY (`model_id`,`recall_id`),
  KEY `idx_recall_type` (`recall_type`),
  KEY `idx_recall_date` (`recall_date`),
  CONSTRAINT `fk_recall_model` FOREIGN KEY (`model_id`) REFERENCES `tbl_model` (`model_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

