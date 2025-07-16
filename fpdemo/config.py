#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
疲劳驾驶检测系统配置文件
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库配置
class DatabaseConfig:
    """数据库配置类"""
    
    # 从环境变量或默认值获取配置
    HOST = os.getenv('DB_HOST', 'localhost')
    PORT = int(os.getenv('DB_PORT', 3306))
    USER = os.getenv('DB_USER', 'root')
    PASSWORD = os.getenv('DB_PASSWORD', '')  # 默认为空，需要用户设置
    DATABASE = os.getenv('DB_NAME', 'demo01')
    CHARSET = 'utf8mb4'
    
    @classmethod
    def get_config(cls):
        """获取数据库配置字典"""
        return {
            'host': cls.HOST,
            'port': cls.PORT,
            'user': cls.USER,
            'password': cls.PASSWORD,
            'database': cls.DATABASE,
            'charset': cls.CHARSET
        }
    
    @classmethod
    def set_password(cls, password):
        """设置数据库密码"""
        cls.PASSWORD = password
        # 可以选择保存到环境变量或配置文件
        os.environ['DB_PASSWORD'] = password

# Flask应用配置
class FlaskConfig:
    """Flask应用配置"""
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'fatigue_detection_system_secret_key_2024')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # 文件上传配置
    UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
    MODEL_FOLDER = BASE_DIR / 'models' / 'uploads'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    
    # 后端API配置
    BACKEND_URL = os.getenv('BACKEND_URL', 'http://127.0.0.1:5001')
    
    @classmethod
    def init_folders(cls):
        """初始化必要的文件夹"""
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.MODEL_FOLDER.mkdir(parents=True, exist_ok=True)
        (cls.UPLOAD_FOLDER / 'results').mkdir(exist_ok=True)

# 系统配置
class SystemConfig:
    """系统配置"""
    
    # 支持的文件格式
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
    ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv'}
    ALLOWED_MODEL_EXTENSIONS = {'.pt', '.pth'}
    
    # 检测配置
    DEFAULT_CONFIDENCE_THRESHOLD = 0.5
    DEFAULT_IOU_THRESHOLD = 0.45
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = BASE_DIR / 'logs' / 'app.log'
    
    @classmethod
    def init_logs(cls):
        """初始化日志目录"""
        cls.LOG_FILE.parent.mkdir(exist_ok=True)

# 开发环境配置
class DevelopmentConfig(FlaskConfig):
    """开发环境配置"""
    DEBUG = True
    
class ProductionConfig(FlaskConfig):
    """生产环境配置"""
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY')  # 生产环境必须设置
    
    if not SECRET_KEY:
        raise ValueError("生产环境必须设置 SECRET_KEY 环境变量")

# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """获取配置类"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    return config.get(config_name, config['default'])

# 初始化配置
def init_config():
    """初始化配置"""
    FlaskConfig.init_folders()
    SystemConfig.init_logs()
    
    # 检查数据库密码是否设置
    if not DatabaseConfig.PASSWORD:
        print("⚠️  警告: 数据库密码未设置")
        print("请在 config.py 中设置 DatabaseConfig.PASSWORD")
        print("或设置环境变量 DB_PASSWORD")

if __name__ == "__main__":
    # 测试配置
    print("=== 配置测试 ===")
    print(f"数据库配置: {DatabaseConfig.get_config()}")
    print(f"上传目录: {FlaskConfig.UPLOAD_FOLDER}")
    print(f"模型目录: {FlaskConfig.MODEL_FOLDER}")
    print(f"后端URL: {FlaskConfig.BACKEND_URL}")
    
    init_config()
    print("✅ 配置初始化完成")
