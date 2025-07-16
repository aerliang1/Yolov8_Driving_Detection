-- 疲劳检测系统数据库初始化脚本

-- 创建数据库
CREATE DATABASE IF NOT EXISTS fatigue_detection CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE fatigue_detection;

-- 用户表
CREATE TABLE IF NOT EXISTS login_user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'monitor', 'driver') NOT NULL DEFAULT 'driver',
    email VARCHAR(100),
    phone VARCHAR(20),
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 检测记录表
CREATE TABLE IF NOT EXISTS detection_record (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    method ENUM('image', 'video', 'camera') NOT NULL,
    result VARCHAR(50) NOT NULL,
    fatigue_level ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'low',
    status ENUM('processing', 'completed', 'failed') DEFAULT 'completed',
    remark TEXT,
    details TEXT,
    duration DECIMAL(10,2) DEFAULT 0.00,
    confidence DECIMAL(5,2) DEFAULT 0.00,
    file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_timestamp (timestamp),
    INDEX idx_fatigue_level (fatigue_level),
    INDEX idx_method (method)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 模型管理表
CREATE TABLE IF NOT EXISTS model_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_path VARCHAR(500) NOT NULL,
    model_version VARCHAR(20),
    model_size BIGINT,
    accuracy DECIMAL(5,2),
    status ENUM('active', 'inactive') DEFAULT 'active',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_model_name (model_name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入默认管理员用户
INSERT INTO login_user (username, password, role, email) VALUES 
('admin', 'admin123', 'admin', 'admin@fatigue-detection.com'),
('monitor', 'monitor123', 'monitor', 'monitor@fatigue-detection.com'),
('driver', 'driver123', 'driver', 'driver@fatigue-detection.com')
ON DUPLICATE KEY UPDATE username=username;

-- 插入系统配置
INSERT INTO system_config (config_key, config_value, description) VALUES 
('system_name', '疲劳检测系统', '系统名称'),
('detection_threshold', '0.7', '检测置信度阈值'),
('detection_interval', '5', '检测间隔(秒)'),
('log_retention', '30', '日志保留天数'),
('max_upload_size', '100', '最大上传文件大小(MB)')
ON DUPLICATE KEY UPDATE config_value=VALUES(config_value);

-- 插入默认模型信息
INSERT INTO model_info (model_name, model_path, model_version, description) VALUES 
('best.pt', '/app/best.pt', '1.0', '默认疲劳检测模型')
ON DUPLICATE KEY UPDATE model_name=model_name;
