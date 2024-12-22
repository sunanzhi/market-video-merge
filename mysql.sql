-- 创建数据库
CREATE DATABASE video_merger_db;

-- 使用数据库
USE video_merger_db;

-- 创建表结构
CREATE TABLE video_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    video_name VARCHAR(255) NOT NULL,
    md5_hash VARCHAR(32) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);