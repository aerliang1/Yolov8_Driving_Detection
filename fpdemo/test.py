import pymysql
import os
import sys

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '673740Pan'),  # 请修改为您的实际密码
    'database': os.getenv('DB_NAME', 'demo01'),
    'charset': 'utf8mb4'
}

# 全局连接对象
conn = None

def get_connection():
    """获取数据库连接"""
    global conn
    try:
        if conn is None or not conn.open:
            conn = pymysql.connect(**DB_CONFIG)
            print("✅ 数据库连接成功")
        return conn
    except pymysql.err.OperationalError as e:
        error_code, error_msg = e.args
        print(f"❌ 数据库连接失败: {error_msg}")

        if error_code == 1045:
            print("🔧 解决建议:")
            print("1. 检查用户名和密码是否正确")
            print("2. 运行 'python test_mysql_connection.py' 进行诊断")
            print("3. 修改 test.py 中的 DB_CONFIG 配置")

        return None
    except Exception as e:
        print(f"❌ 数据库连接异常: {e}")
        return None

def con_my_sql(sql_code):
    """执行SQL语句"""
    try:
        connection = get_connection()
        if connection is None:
            return None, "数据库连接失败"

        connection.ping(reconnect=True)
        print(f"执行SQL: {sql_code}")

        # 通过游标对象发出sql
        cursor = connection.cursor(pymysql.cursors.DictCursor)  # 返回数据是字典形式，而不是数组
        cursor.execute(sql_code)

        # 提交事务
        connection.commit()

        # 不关闭连接，让连接保持打开状态
        return cursor

    except pymysql.MySQLError as err_massage:
        if connection:
            connection.rollback()
        print(f"❌ SQL执行失败: {err_massage}")
        return type(err_massage), err_massage
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return None, str(e)

# username= "王五"
# password = '654321'
#
# code = "INSERT INTO `login_user`(`username`, `password`)VALUE ('%s','%s')" % (username, password)
# print(con_my_sql(code))


# code = "SELECT * FROM `login_user`"
# cursor_ans = con_my_sql(code)
# print("查询结果:", cursor_ans.fetchall())