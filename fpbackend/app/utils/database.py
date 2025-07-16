import pymysql
from pymysql.cursors import DictCursor
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        """建立数据库连接"""
        try:
            # 从环境变量获取数据库配置，如果没有则使用默认值
            db_host = os.getenv('DB_HOST', 'localhost')
            db_port = int(os.getenv('DB_PORT', 3306))
            db_user = os.getenv('DB_USER', 'root')
            db_password = os.getenv('DB_PASSWORD', '604002')
            db_name = os.getenv('DB_NAME', 'test')

            self.connection = pymysql.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                charset="utf8mb4",
                cursorclass=DictCursor
            )
            logger.info(f"数据库连接成功: {db_host}:{db_port}/{db_name}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def execute_query(self, sql, params=None):
        """执行查询语句"""
        try:
            if not self.connection or not self.connection.open:
                self.connect()
            if not self.connection:
                raise Exception("数据库连接未建立")
            cursor = self.connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            if self.connection:
                self.connection.commit()
            return cursor
        except pymysql.err.OperationalError as e:
            # 连接断开时自动重连一次
            if e.args[0] in (2006, 2013):  # MySQL server has gone away, Lost connection
                logger.warning(f"数据库连接断开，尝试自动重连... 错误: {e}")
                self.connect()
                if not self.connection:
                    logger.error("重连数据库失败")
                    raise Exception("重连数据库失败")
                cursor = self.connection.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                if self.connection:
                    self.connection.commit()
                return cursor
            else:
                logger.error(f"执行查询失败: {e}")
                if self.connection:
                    self.connection.rollback()
                raise
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            if self.connection:
                self.connection.rollback()
            raise
    
    def fetch_all(self, sql, params=None):
        """获取所有结果"""
        cursor = self.execute_query(sql, params)
        return cursor.fetchall()
    
    def fetch_one(self, sql, params=None):
        """获取单个结果"""
        cursor = self.execute_query(sql, params)
        return cursor.fetchone()
    
    def execute(self, sql, params=None):
        """执行增删改操作"""
        cursor = self.execute_query(sql, params)
        return cursor.rowcount
    
    def close(self):
        """关闭数据库连接"""
        if self.connection and self.connection.open:
            self.connection.close()

# 全局数据库管理器实例
db = None

def get_db():
    """获取数据库连接"""
    global db
    if db is None:
        try:
            db = DatabaseManager()
        except Exception as e:
            logger.error(f"无法创建数据库连接: {e}")
            return None
    return db 