# 데이터 베이스 생성
create database motor_chata;

# 계정 생성
create user 'leedhroxx'@'%' identified by 'leedhroxx';
create user 'rshyun24'@'%' identified by 'rshyun24';
create user 'wohhahha'@'%' identified by 'wohhahha';
create user 'yhjeon0315'@'%' identified by 'yhjeon0315';
create user 'tksemf075'@'%' identified by 'tksemf075';
create user 'jinseoh123'@'%' identified by 'jinseoh123';

# 계정 삭제
DROP USER 'wohhahha'@'%';

-- (확인용) 사용자 목록 조회
SELECT * FROM mysql.user
where user = 'leedhroxx';

# 새로 만든 motor_chata 데이터베이스에 대한 모든 권한을 'skn26'에게 부여
grant all privileges on motor_chata.* to 'tksemf075'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX ON motor_chata.* TO 'leedhroxx'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX ON motor_chata.* TO 'rshyun24'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX ON motor_chata.* TO 'wohhahha'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX ON motor_chata.* TO 'yhjeon0315'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX ON motor_chata.* TO 'jinseoh123'@'%';