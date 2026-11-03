-- INFRA-03: runs ONCE on a fresh MySQL 8 instance (docker-entrypoint-initdb.d, or the CI step).
-- DEV / CI ONLY. In production the DBA runs the equivalent with a real secret password.

-- 1. The chatbot's own schema (Django migrations create the tables inside it)
CREATE DATABASE IF NOT EXISTS onecare_chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 2. Stand-in for Spring Boot's schema, ONLY so the privilege test (AC6) has something to try to read
CREATE DATABASE IF NOT EXISTS onecare_core CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS onecare_core.users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
INSERT INTO onecare_core.users (email) VALUES ('privilege-test@example.com');

-- 3. The Django database user: least privilege (AC6)
CREATE USER IF NOT EXISTS 'chatbot_app'@'%' IDENTIFIED BY 'chatbot_dev_pw';
-- `\_` = literal underscore (an unescaped _ is a wildcard in GRANT database names)
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
    ON `onecare\_chatbot`.* TO 'chatbot_app'@'%';
-- Needed only so pytest-django can create its throw-away test database. Never grant this in production.
GRANT ALL PRIVILEGES ON `test\_onecare\_chatbot`.* TO 'chatbot_app'@'%';
FLUSH PRIVILEGES;