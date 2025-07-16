#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立管理员系统主应用
完全按照原系统实现，包含完整的前后端一体化管理员系统
"""

import os
import sys
import pymysql
from pymysql.cursors import DictCursor
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for, make_response
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
import logging
from functools import wraps

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'admin_system_secret_key_2024'

# 启用CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})


class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        """建立数据库连接"""
        try:
            # 从环境变量获取数据库配置，如果没有则使用默认值
            db_host = '101.245.79.154'
            db_port =  3306
            db_user = 'root'
            db_password =  '123456'
            db_name =  'admin'

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
        cursor = None
        try:
            cursor = self.execute_query(sql, params)
            result = cursor.fetchall()
            return result
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass

    def fetch_one(self, sql, params=None):
        """获取单个结果"""
        cursor = None
        try:
            cursor = self.execute_query(sql, params)
            result = cursor.fetchone()
            return result
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass

    def execute(self, sql, params=None):
        """执行增删改操作"""
        cursor = None
        try:
            cursor = self.execute_query(sql, params)
            rowcount = cursor.rowcount
            return rowcount
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass

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
    # 角色名称映射
def get_role_name(role):
    role_names = {
        'admin': '管理员',
        'monitor': '监控人员',
        'driver': '驾驶员'
    }
    return role_names.get(role, role)

# 通用的消息提示页面
def show_message(message, redirect_url, show_button=True, button_text="确定", timeout=3000):
    auto_redirect = f"""
    <script>
        setTimeout(function() {{
            window.location.href = "{redirect_url}";
        }}, {timeout});
    </script>
    """
    
    button_html = f'<a href="{redirect_url}" class="layui-btn layui-btn-normal">{button_text}</a>' if show_button else ""
    
    return f'''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>系统提示</title>
        <link rel="stylesheet" href="/static/css/layui.css">
        <style>
            body {{ display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; background-color: #f5f7fa; }}
            .message-box {{ width: 400px; background-color: #fff; border-radius: 6px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); overflow: hidden; }}
            .message-header {{ background-color: #009688; color: #fff; text-align: center; padding: 15px 0; font-size: 18px; }}
            .message-content {{ padding: 30px; text-align: center; }}
            .message-text {{ margin-bottom: 20px; font-size: 16px; color: #333; }}
        </style>
    </head>
    <body>
        <div class="message-box">
            <div class="message-header">系统提示</div>
            <div class="message-content">
                <div class="message-text">{message}</div>
                {button_html}
            </div>
        </div>
        {auto_redirect}
    </body>
    </html>
    '''

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 角色验证装饰器
def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                return show_message("权限不足", "/login", show_button=True, button_text="返回登录")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 系统日志记录功能
def log_action(username, role, action, details="", ip_address=""):
    try:
        database = get_db()
        if database is None:
            return
        
        if not ip_address:
            ip_address = request.remote_addr if request else "127.0.0.1"
        
        # 生成东八区北京时间
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = datetime.now(beijing_tz)
        beijing_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        
        sql = "INSERT INTO system_log (username, role, action, details, ip_address, timestamp) VALUES (%s, %s, %s, %s, %s, %s)"
        database.execute(sql, (username, role, action, details, ip_address, beijing_str))
    except Exception as e:
        logger.error(f"记录日志失败: {e}")

# 静态文件服务
@app.route('/static/<path:filename>')
def static_files(filename):
    """提供静态文件访问"""
    return send_from_directory('static', filename)

# 主页路由
@app.route('/')
def index():
    """主页重定向到登录或控制台"""
    # if 'username' in session:
    #     return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    # 清除会话中的用户名和上传的文件名
    username = session.pop('username', None)
    role = session.pop('role', None)
    uploaded_filename = session.pop('uploaded_filename', None)
    if username and role:
        log_action(username, role, "用户退出登录")

    # 设置响应头禁止浏览器缓存
    resp = redirect(url_for('login'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

# 登录注册路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            return show_message("用户名和密码不能为空", "/login", show_button=True, button_text="返回登录")

        try:
            database = get_db()
            if database is None:
                return show_message("数据库连接失败", "/login", show_button=True, button_text="返回登录")

            sql = "SELECT id, username, password, role, register_time, last_login FROM login_user WHERE username = %s"
            user = database.fetch_one(sql, (username,))

            if not user or user['password'] != password:
                return show_message("用户名或密码错误", "/login", show_button=True, button_text="返回登录")

            # 检查是否为管理员
            if user['role'] != 'admin':
                return show_message("只有管理员可以访问此系统", "/login", show_button=True, button_text="返回登录")

            # 更新最后登录时间
            beijing_tz = timezone(timedelta(hours=8))
            beijing_time = datetime.now(beijing_tz)
            beijing_str = beijing_time.strftime('%Y-%m-%d %H:%M:%S')

            update_sql = "UPDATE login_user SET last_login = %s WHERE id = %s"
            database.execute(update_sql, (beijing_str, user['id']))

            # 设置session
            session['username'] = username
            session['role'] = user['role']
            session['user_id'] = user['id']
            session['register_time'] = user.get('register_time')
            session['last_login'] = beijing_str

            # 记录登录日志
            log_action(username, user['role'], "管理员登录", f"登录独立管理员系统")

            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            logger.error(f"登录错误: {e}")
            return show_message("系统错误，请稍后重试", "/login", show_button=True, button_text="返回登录")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'admin')  # 默认为管理员

        if not username or not password:
            return show_message("用户名和密码不能为空", "/register", show_button=True, button_text="返回注册")

        if password != confirm_password:
            return show_message("两次输入的密码不一致", "/register", show_button=True, button_text="返回注册")

        try:
            database = get_db()
            if database is None:
                return show_message("数据库连接失败", "/register", show_button=True, button_text="返回注册")

            # 检查用户名是否已存在
            check_sql = "SELECT id FROM login_user WHERE username = %s"
            existing_user = database.fetch_one(check_sql, (username,))
            if existing_user:
                return show_message("用户名已存在", "/register", show_button=True, button_text="返回注册")

            # 生成东八区北京时间
            beijing_tz = timezone(timedelta(hours=8))
            beijing_now = datetime.now(beijing_tz)
            beijing_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')

            # 插入新用户
            insert_sql = "INSERT INTO login_user (username, password, role, register_time) VALUES (%s, %s, %s, %s)"
            database.execute(insert_sql, (username, password, role, beijing_str))

            # 记录注册日志
            log_action(username, role, "用户注册", f"注册新管理员账户")

            return show_message("注册成功", "/login", show_button=True, button_text="前往登录")

        except Exception as e:
            logger.error(f"注册错误: {e}")
            return show_message("系统错误，请稍后重试", "/register", show_button=True, button_text="返回注册")

    return render_template('register.html')

# 管理员页面路由
@app.route('/admin/dashboard')
@login_required
@role_required(['admin'])
def admin_dashboard():
    """管理控制台"""
    resp = make_response(render_template('admin/dashboard.html',
                                       username=session['username'],
                                       role=session['role'],
                                       role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/admin/permissions')
@login_required
@role_required(['admin'])
def admin_permissions():
    """权限管理"""
    resp = make_response(render_template('admin/permissions.html',
                                       username=session['username'],
                                       role=session['role'],
                                       role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/admin/records')
@login_required
@role_required(['admin'])
def admin_records():
    """检测记录管理页面"""
    # 预加载一些记录数据供页面初始显示
    records = []
    try:
        db = get_db()
        if db:
            sql = "SELECT id, username, timestamp, method, result, fatigue_level, status FROM detection_record ORDER BY timestamp DESC LIMIT 50"
            records = db.fetch_all(sql)

            # 处理时间格式
            if records:
                for record in records:
                    if record.get('timestamp'):
                        if hasattr(record['timestamp'], 'strftime'):
                            record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                        elif not isinstance(record['timestamp'], str):
                            record['timestamp'] = str(record['timestamp'])

            logger.info(f"Pre-loaded {len(records)} records for admin page")
    except Exception as e:
        logger.error(f"预加载检测记录失败: {e}")
        records = []

    resp = make_response(render_template('admin/records.html',
                                       username=session['username'],
                                       role=session['role'],
                                       role_name=get_role_name(session['role']),
                                       records=records))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/admin/system_log')
@login_required
@role_required(['admin'])
def admin_system_log():
    """系统日志"""
    resp = make_response(render_template('admin/system_log.html',
                                       username=session['username'],
                                       role=session['role'],
                                       role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/admin/profile')
@login_required
@role_required(['admin'])
def admin_profile_page():
    """个人信息"""
    # 获取当前登录用户信息
    try:
        db = get_db()
        if db:
            sql = "SELECT id, username, role, register_time, last_login FROM login_user WHERE username = %s AND role = 'admin'"
            user_info = db.fetch_one(sql, (session.get('username'),))
            if not user_info:
                user_info = {
                    'username': session.get('username', ''),
                    'role': session.get('role', ''),
                    'register_time': '未知',
                    'last_login': '未知'
                }
        else:
            user_info = {
                'username': session.get('username', ''),
                'role': session.get('role', ''),
                'register_time': '未知',
                'last_login': '未知'
            }
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        user_info = {
            'username': session.get('username', ''),
            'role': session.get('role', ''),
            'register_time': '未知',
            'last_login': '未知'
        }

    resp = make_response(render_template('admin/profile.html',
                                       username=session['username'],
                                       role=session['role'],
                                       role_name=get_role_name(session['role']),
                                       user_info=user_info))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/change-password', methods=['POST'])
@login_required
@role_required(['admin'])
def admin_change_password():
    """管理员修改密码"""
    try:
        data = request.get_json()
        old_password = data.get('old_password', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()

        if not all([old_password, new_password, confirm_password]):
            return jsonify({'success': False, 'message': '所有字段都不能为空'}), 400

        if new_password != confirm_password:
            return jsonify({'success': False, 'message': '新密码和确认密码不一致'}), 400

        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        # 验证旧密码
        username = session.get('username')
        check_sql = "SELECT id, password FROM login_user WHERE username = %s AND role = 'admin'"
        user = db.fetch_one(check_sql, (username,))

        if not user or user['password'] != old_password:
            return jsonify({'success': False, 'message': '原密码错误'}), 400

        # 更新密码
        update_sql = "UPDATE login_user SET password = %s WHERE id = %s"
        db.execute(update_sql, (new_password, user['id']))

        # 记录操作日志
        log_action(session['username'], session['role'], "修改密码", "管理员修改密码")

        return jsonify({'success': True, 'message': '密码修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改密码失败: {e}'}), 500

@app.route('/api/change-username', methods=['POST'])
@login_required
@role_required(['admin'])
def admin_change_username():
    """管理员修改用户名"""
    try:
        data = request.get_json()
        old_username = data.get('old_username', '').strip()
        new_username = data.get('new_username', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        if not old_username or not new_username or not confirm_password:
            return jsonify({'success': False, 'message': '所有字段均不能为空'}), 400
            
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
        # 验证当前用户身份
        sql = "SELECT id, password FROM login_user WHERE username = %s AND role='admin'"
        user = db.fetch_one(sql, (old_username,))
        if not user or user['password'] != confirm_password:
            return jsonify({'success': False, 'message': '密码确认错误'}), 400
            
        # 检查新用户名是否已存在
        check_sql = "SELECT id FROM login_user WHERE username = %s"
        if db.fetch_one(check_sql, (new_username,)):
            return jsonify({'success': False, 'message': '新用户名已存在'}), 400
            
        # 更新用户名
        update_sql = "UPDATE login_user SET username = %s WHERE username = %s AND role='admin'"
        db.execute(update_sql, (new_username, old_username))
        
        # 更新session中的用户名
        session['username'] = new_username
        
        # 记录操作日志
        log_action(new_username, session['role'], "修改用户名", f"用户名从 {old_username} 修改为 {new_username}")
        
        return jsonify({'success': True, 'message': '用户名修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'用户名修改失败: {e}'}), 500

@app.route('/api/admin/system-settings', methods=['POST'])
@login_required
@role_required(['admin'])
def system_settings():
    """保存系统设置（这里只做示例，实际应存入配置表）"""
    try:
        data = request.get_json()
        # 假设有 system_name, detection_threshold, detection_interval, log_retention
        # 实际应存入数据库配置表，这里仅返回成功
        return jsonify({'success': True, 'message': '系统设置保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'系统设置保存失败: {e}'}), 500

# API接口 - 完全按照原系统实现

# 仪表盘统计
@app.route('/api/dashboard-stats', methods=['GET'])
@login_required
@role_required(['admin'])
def dashboard_stats():
    """获取仪表盘统计数据"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        total_users = db.fetch_one("SELECT COUNT(*) as cnt FROM login_user")['cnt']
        online_drivers = db.fetch_one("SELECT COUNT(*) as cnt FROM login_user WHERE role='driver'")['cnt']
        
        # 使用当前日期字符串，避免时区问题
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = datetime.now(beijing_tz)
        today_str = beijing_now.strftime('%Y-%m-%d')
        
        today_detections = db.fetch_one(
            "SELECT COUNT(*) as cnt FROM detection_record WHERE DATE(timestamp) = %s", 
            (today_str,)
        )['cnt']
        fatigue_alerts = db.fetch_one(
            "SELECT COUNT(*) as cnt FROM detection_record WHERE result='fatigue' AND DATE(timestamp) = %s",
            (today_str,)
        )['cnt']
        # 系统资源可用静态或模拟数据
        cpu_usage = 45
        memory_usage = 62
        disk_usage = 28
        return jsonify({'success': True, 'data': {
            'total_users': total_users,
            'online_drivers': online_drivers,
            'today_detections': today_detections,
            'fatigue_alerts': fatigue_alerts,
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'disk_usage': disk_usage
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取仪表盘数据失败: {e}'}), 500

# 用户管理
@app.route('/api/users', methods=['GET'])
@login_required
@role_required(['admin'])
def get_users():
    """获取用户列表，支持搜索"""
    try:
        search = request.args.get('search', '').strip()
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        if search:
            sql = "SELECT id, username, role, 'active' as status FROM login_user WHERE username LIKE %s"
            users = db.fetch_all(sql, (f'%{search}%',))
        else:
            sql = "SELECT id, username, role, 'active' as status FROM login_user"
            users = db.fetch_all(sql)
        return jsonify({'success': True, 'data': users})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户列表失败: {e}'}), 500

@app.route('/api/users', methods=['POST'])
@login_required
@role_required(['admin'])
def add_user():
    """添加用户"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'driver')
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT id FROM login_user WHERE username = %s"
        existing_user = db.fetch_one(check_sql, (username,))
        if existing_user:
            return jsonify({'success': False, 'message': '用户名已存在'}), 400
        insert_sql = "INSERT INTO login_user (username, password, role) VALUES (%s, %s, %s)"
        db.execute(insert_sql, (username, password, role))

        # 记录操作日志
        log_action(session['username'], session['role'], "添加用户", f"添加用户: {username}, 角色: {role}")

        return jsonify({'success': True, 'message': '用户创建成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加用户失败: {e}'}), 500

@app.route('/api/users/<int:user_id>/role', methods=['PUT'])
@login_required
@role_required(['admin'])
def update_user_role(user_id):
    """更新用户角色"""
    try:
        data = request.get_json()
        new_role = data.get('role', '').strip()
        if not new_role or new_role not in ['admin', 'monitor', 'driver']:
            return jsonify({'success': False, 'message': '无效的角色类型'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT username FROM login_user WHERE id = %s"
        user = db.fetch_one(check_sql, (user_id,))
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        update_sql = "UPDATE login_user SET role = %s WHERE id = %s"
        db.execute(update_sql, (new_role, user_id))

        # 记录操作日志
        log_action(session['username'], session['role'], "修改用户角色", f"修改用户 {user['username']} 角色为: {new_role}")

        return jsonify({'success': True, 'message': '用户角色更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新用户角色失败: {e}'}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def delete_user(user_id):
    """删除用户"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT username FROM login_user WHERE id = %s"
        user = db.fetch_one(check_sql, (user_id,))
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        delete_sql = "DELETE FROM login_user WHERE id = %s"
        db.execute(delete_sql, (user_id,))

        # 记录操作日志
        log_action(session['username'], session['role'], "删除用户", f"删除用户: {user['username']}")

        return jsonify({'success': True, 'message': '用户删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除用户失败: {e}'}), 500

# 检测记录管理
@app.route('/api/records', methods=['GET'])
@login_required
@role_required(['admin'])
def get_records():
    """获取检测记录，支持筛选"""
    try:
        result = request.args.get('result', '').strip()
        driver_id = request.args.get('driver_id', '').strip()
        date_range = request.args.get('date_range', '').strip()

        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        # 构建SQL查询 - 包含所有字段
        sql = """
        SELECT id, username, timestamp, method, result, fatigue_level, status,
               remark, details, duration, confidence
        FROM detection_record
        WHERE 1=1
        """
        params = []

        if result:
            sql += " AND result = %s"
            params.append(result)
        if driver_id:
            sql += " AND driver_id = %s"
            params.append(driver_id)
        if date_range:
            try:
                start, end = [d.strip() for d in date_range.split('-')]
                sql += " AND timestamp BETWEEN %s AND %s"
                params.extend([start + ' 00:00:00', end + ' 23:59:59'])
            except Exception as e:
                logger.warning(f"日期范围解析失败: {e}")

        sql += " ORDER BY timestamp DESC LIMIT 200"

        try:
            if params:
                records = db.fetch_all(sql, tuple(params))
            else:
                records = db.fetch_all(sql)

            # 处理返回数据
            if records:
                for record in records:
                    # 格式化时间字段
                    if record.get('timestamp'):
                        if hasattr(record['timestamp'], 'strftime'):
                            record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

                    # 确保所有字段都有默认值
                    record['remark'] = record.get('remark') or ''
                    record['details'] = record.get('details') or ''
                    record['duration'] = record.get('duration') or 0
                    record['confidence'] = record.get('confidence') or 0.0
                    record['fatigue_level'] = record.get('fatigue_level') or 0
                    record['method'] = record.get('method') or 'camera'
                    record['status'] = record.get('status') or 'pending'
                    record['result'] = record.get('result') or 'normal'

            return jsonify({'success': True, 'data': records if records else []})
        except Exception as e:
            logger.error(f"查询检测记录失败: {e}")
            return jsonify({'success': True, 'data': []})
    except Exception as e:
        logger.error(f"获取检测记录失败: {e}")
        return jsonify({'success': False, 'message': f'获取检测记录失败: {str(e)}'}), 500

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def delete_record(record_id):
    """删除检测记录"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT id FROM detection_record WHERE id = %s"
        record = db.fetch_one(check_sql, (record_id,))
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        delete_sql = "DELETE FROM detection_record WHERE id = %s"
        db.execute(delete_sql, (record_id,))
        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除记录失败: {e}'}), 500

@app.route('/api/records/<int:record_id>', methods=['PUT'])
@login_required
@role_required(['admin'])
def update_record(record_id):
    """修改检测记录"""
    try:
        data = request.get_json()
        fatigue_level = data.get('fatigue_level', '').strip()
        
        if not fatigue_level:
            return jsonify({'success': False, 'message': '疲劳程度不能为空'}), 400
            
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
        # 检查记录是否存在
        check_sql = "SELECT id FROM detection_record WHERE id = %s"
        record = db.fetch_one(check_sql, (record_id,))
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404
            
        # 更新记录
        update_sql = "UPDATE detection_record SET fatigue_level = %s WHERE id = %s"
        db.execute(update_sql, (fatigue_level, record_id))
        
        # 记录操作日志
        log_action(session['username'], session['role'], "修改检测记录", f"修改记录ID {record_id} 的疲劳程度为: {fatigue_level}")
        
        return jsonify({'success': True, 'message': '记录修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改记录失败: {e}'}), 500

@app.route('/api/records/export', methods=['GET'])
@login_required
@role_required(['admin'])
def export_records():
    """导出检测记录（返回CSV）"""
    import csv
    from io import StringIO
    from flask import Response
    try:
        result = request.args.get('result', '').strip()
        driver_id = request.args.get('driver_id', '').strip()
        date_range = request.args.get('date_range', '').strip()

        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        # 构建SQL查询
        sql = """
        SELECT id, username, timestamp, method, result, fatigue_level, status,
               remark, details, duration, confidence
        FROM detection_record
        WHERE 1=1
        """
        params = []

        if result:
            sql += " AND result = %s"
            params.append(result)
        if driver_id:
            sql += " AND driver_id = %s"
            params.append(driver_id)
        if date_range:
            try:
                start, end = [d.strip() for d in date_range.split('-')]
                sql += " AND timestamp BETWEEN %s AND %s"
                params.extend([start + ' 00:00:00', end + ' 23:59:59'])
            except Exception as e:
                logger.warning(f"日期范围解析失败: {e}")

        sql += " ORDER BY timestamp DESC"

        if params:
            records = db.fetch_all(sql, tuple(params))
        else:
            records = db.fetch_all(sql)

        # 生成CSV
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', '驾驶员', '检测时间', '检测方式', '检测结果', '疲劳程度', '处理状态', '备注', '详情', '持续时间', '置信度'])

        for r in records:
            # 格式化时间
            timestamp = r.get('timestamp', '')
            if hasattr(timestamp, 'strftime'):
                timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

            cw.writerow([
                r.get('id', ''),
                r.get('username', ''),
                timestamp,
                r.get('method', ''),
                r.get('result', ''),
                r.get('fatigue_level', 0),
                r.get('status', ''),
                r.get('remark', ''),
                r.get('details', ''),
                r.get('duration', 0),
                r.get('confidence', 0.0)
            ])

        output = si.getvalue().encode('utf-8-sig')

        # 记录操作日志
        log_action(session['username'], session['role'], "导出检测记录", f"导出了 {len(records)} 条检测记录")

        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=detection_records.csv'
            }
        )
    except Exception as e:
        logger.error(f"导出检测记录失败: {e}")
        return jsonify({'success': False, 'message': f'导出检测记录失败: {str(e)}'}), 500

# 系统日志管理
@app.route('/api/logs', methods=['GET'])
@login_required
@role_required(['admin'])
def get_logs():
    """获取系统日志，支持筛选"""
    try:
        role = request.args.get('role', '').strip()
        action = request.args.get('action', '').strip()
        date_range = request.args.get('date_range', '').strip()
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, role, action, details, ip_address, timestamp FROM system_log WHERE 1=1"
        params = []
        if role:
            sql += " AND role = %s"
            params.append(role)
        if action:
            sql += " AND action = %s"
            params.append(action)
        if date_range:
            # 假设 date_range 格式为 'YYYY-MM-DD - YYYY-MM-DD'
            try:
                start, end = [d.strip() for d in date_range.split('-')]
                sql += " AND timestamp BETWEEN %s AND %s"
                params.extend([start + ' 00:00:00', end + ' 23:59:59'])
            except Exception:
                pass
        sql += " ORDER BY timestamp DESC"
        logs = db.fetch_all(sql, tuple(params))
        return jsonify({'success': True, 'data': logs})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取系统日志失败: {e}'}), 500

@app.route('/api/logs/clear', methods=['DELETE'])
@login_required
@role_required(['admin'])
def clear_logs():
    """清空系统日志"""
    try:
        logger.info(f"开始清空系统日志，用户: {session.get('username')}, 角色: {session.get('role')}")
        
        # 直接操作数据库清空日志
        db = get_db()
        if db is None:
            logger.error("数据库连接失败")
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        # 检查system_log表是否存在
        try:
            check_table_sql = "SHOW TABLES LIKE 'system_log'"
            table_result = db.fetch_one(check_table_sql)
            if not table_result:
                logger.error("system_log表不存在")
                return jsonify({'success': False, 'message': 'system_log表不存在'}), 500
            logger.info("system_log表存在")
        except Exception as e:
            logger.error(f"检查system_log表失败: {e}")
            return jsonify({'success': False, 'message': f'检查system_log表失败: {str(e)}'}), 500

        # 获取清空前的日志数量
        try:
            count_result = db.fetch_one("SELECT COUNT(*) as count FROM system_log")
            log_count = count_result['count'] if count_result else 0
            logger.info(f"当前日志数量: {log_count}")
        except Exception as e:
            logger.error(f"获取日志数量失败: {e}")
            return jsonify({'success': False, 'message': f'获取日志数量失败: {str(e)}'}), 500

        # 执行删除操作
        try:
            rows_affected = db.execute("DELETE FROM system_log")
            logger.info(f"删除操作影响行数: {rows_affected}")
        except Exception as e:
            logger.error(f"删除日志失败: {e}")
            return jsonify({'success': False, 'message': f'删除日志失败: {str(e)}'}), 500

        if rows_affected >= 0:  # 删除成功（包括删除0行的情况）
            logger.info(f"日志删除成功，共删除 {log_count} 条记录")
            
            # 记录清空日志操作（在清空之后记录新的日志）
            try:
                log_action(session['username'], session['role'], "清空系统日志",
                          f"管理员清空了 {log_count} 条系统日志记录")
                logger.info("清空日志操作已记录到新日志")
            except Exception as e:
                logger.error(f"记录清空日志操作失败: {e}")

            return jsonify({'success': True, 'message': f'系统日志清空成功，共清空 {log_count} 条记录'})
        else:
            logger.error("删除操作返回负数，表示操作失败")
            return jsonify({'success': False, 'message': '清空操作失败'}), 500

    except Exception as e:
        # 记录错误日志
        try:
            log_action(session['username'], session['role'], "清空系统日志失败", f"清空日志时发生错误: {str(e)}")
        except:
            pass  # 如果记录日志也失败，忽略错误

        logger.error(f"清空系统日志失败: {e}")
        return jsonify({'success': False, 'message': f'系统日志清空失败: {str(e)}'}), 500

@app.route('/api/logs/export', methods=['GET'])
@login_required
@role_required(['admin'])
def export_logs():
    """导出系统日志（返回CSV）"""
    import csv
    from io import StringIO
    from flask import Response
    try:
        role = request.args.get('role', '').strip()
        action = request.args.get('action', '').strip()
        date_range = request.args.get('date_range', '').strip()
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, role, action, details, ip_address, timestamp FROM system_log WHERE 1=1"
        params = []
        if role:
            sql += " AND role = %s"
            params.append(role)
        if action:
            sql += " AND action = %s"
            params.append(action)
        if date_range:
            try:
                start, end = [d.strip() for d in date_range.split('-')]
                sql += " AND timestamp BETWEEN %s AND %s"
                params.extend([start + ' 00:00:00', end + ' 23:59:59'])
            except Exception:
                pass
        sql += " ORDER BY timestamp DESC"
        logs = db.fetch_all(sql, tuple(params))
        # 生成CSV
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', '用户名', '角色', '操作', '详情', 'IP地址', '时间'])
        for log in logs:
            cw.writerow([
                log.get('id'), log.get('username'), log.get('role'), log.get('action'),
                log.get('details', ''), log.get('ip_address', ''), log.get('timestamp')
            ])
        output = si.getvalue().encode('utf-8-sig')

        # 记录操作日志
        log_action(session['username'], session['role'], "导出系统日志", f"导出了 {len(logs)} 条日志记录")

        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=system_logs.csv'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'导出系统日志失败: {e}'}), 500

# 最近活动
@app.route('/api/recent-activities', methods=['GET'])
@login_required
@role_required(['admin'])
def recent_activities():
    """获取最近活动日志"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': True, 'data': []})

        try:
            sql = "SELECT timestamp, username, action, details, ip_address FROM system_log ORDER BY timestamp DESC LIMIT 3"
            logs = db.fetch_all(sql)
            return jsonify({'success': True, 'data': logs if logs else []})
        except Exception as e:
            print(f"查询最近活动失败: {e}")
            return jsonify({'success': True, 'data': []})
    except Exception as e:
        print(f"获取最近活动失败: {e}")
        return jsonify({'success': True, 'data': []})

# 公告管理
@app.route('/api/announcements', methods=['GET'])
@login_required
@role_required(['admin'])
def get_announcements():
    """获取公告列表"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': True, 'data': []})

        try:
            sql = "SELECT id, title, content, created_at FROM announcement ORDER BY created_at DESC"
            data = db.fetch_all(sql)
            return jsonify({'success': True, 'data': data if data else []})
        except Exception as e:
            print(f"查询公告失败: {e}")
            return jsonify({'success': True, 'data': []})
    except Exception as e:
        print(f"获取公告失败: {e}")
        return jsonify({'success': True, 'data': []})

@app.route('/api/announcements', methods=['POST'])
@login_required
@role_required(['admin'])
def add_announcement():
    """发布公告"""
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        if not title or not content:
            return jsonify({'success': False, 'message': '标题和内容不能为空'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        # 生成东八区北京时间
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = datetime.now(beijing_tz)
        beijing_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        sql = "INSERT INTO announcement (title, content, created_at) VALUES (%s, %s, %s)"
        db.execute(sql, (title, content, beijing_str))

        # 记录操作日志
        log_action(session['username'], session['role'], "发布公告", f"发布公告: {title}")

        return jsonify({'success': True, 'message': '公告发布成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'公告发布失败: {e}'}), 500

@app.route('/api/announcements/<int:announcement_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def delete_announcement(announcement_id):
    """删除公告"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT title FROM announcement WHERE id = %s"
        announcement = db.fetch_one(check_sql, (announcement_id,))
        if not announcement:
            return jsonify({'success': False, 'message': '公告不存在'}), 404
        delete_sql = "DELETE FROM announcement WHERE id = %s"
        db.execute(delete_sql, (announcement_id,))

        # 记录操作日志
        log_action(session['username'], session['role'], "删除公告", f"删除公告: {announcement['title']}")

        return jsonify({'success': True, 'message': '公告删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除公告失败: {e}'}), 500

# 驾驶员列表
@app.route('/api/drivers', methods=['GET'])
@login_required
@role_required(['admin'])
def get_drivers():
    """获取驾驶员列表"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username FROM login_user WHERE role='driver'"
        drivers = db.fetch_all(sql)
        return jsonify({'success': True, 'data': drivers})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取驾驶员列表失败: {e}'}), 500

# 个人信息
@app.route('/api/profile', methods=['GET'])
@login_required
@role_required(['admin'])
def admin_profile():
    """获取管理员个人信息"""
    try:
        # 按照原系统实现，直接查询第一个admin用户
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, role, register_time, last_login FROM login_user WHERE role='admin' LIMIT 1"
        user = db.fetch_one(sql)
        if not user:
            return jsonify({'success': False, 'message': '未找到管理员信息'}), 404
        return jsonify({'success': True, 'data': user})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取个人信息失败: {e}'}), 500



# 测试数据插入（仅用于调试）
@app.route('/api/init-test-data', methods=['POST'])
@login_required
@role_required(['admin'])
def init_test_data():
    """初始化测试数据"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        # 插入测试检测记录
        test_records = [
            ('driver1', '2024-01-15 10:30:00', 'camera', 'normal', 0, 'processed', '正常驾驶', '检测正常', 300, 95.5),
            ('driver1', '2024-01-15 14:20:00', 'camera', 'fatigue', 3, 'processed', '轻度疲劳', '检测到眼部疲劳', 180, 87.2),
            ('driver2', '2024-01-15 16:45:00', 'camera', 'normal', 0, 'processed', '正常驾驶', '检测正常', 420, 92.8),
            ('driver2', '2024-01-15 18:30:00', 'camera', 'fatigue', 5, 'pending', '中度疲劳', '检测到打哈欠', 120, 89.6),
        ]

        for record in test_records:
            try:
                sql = """
                INSERT INTO detection_record
                (username, timestamp, method, result, fatigue_level, status, remark, details, duration, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                db.execute(sql, record)
            except Exception as e:
                logger.error(f"插入测试记录失败: {e}")

        # 记录操作日志
        log_action(session['username'], session['role'], "初始化测试数据", "插入测试检测记录")

        return jsonify({'success': True, 'message': '测试数据初始化成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'初始化测试数据失败: {e}'}), 500

# 健康检查
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return {'status': 'healthy', 'service': 'admin_system'}

# 调试接口 - 检查数据库状态
@app.route('/api/debug/db-status', methods=['GET'])
@login_required
@role_required(['admin'])
def debug_db_status():
    """调试接口：检查数据库状态"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        # 检查数据库连接
        try:
            db.execute("SELECT 1")
            db_status = "连接正常"
        except Exception as e:
            db_status = f"连接异常: {str(e)}"
        
        # 检查system_log表
        try:
            table_result = db.fetch_one("SHOW TABLES LIKE 'system_log'")
            table_exists = table_result is not None
        except Exception as e:
            table_exists = False
            table_error = str(e)
        
        # 获取system_log表结构
        table_structure = None
        if table_exists:
            try:
                structure_result = db.fetch_all("DESCRIBE system_log")
                table_structure = structure_result
            except Exception as e:
                table_structure = f"获取表结构失败: {str(e)}"
        
        # 获取日志数量
        log_count = 0
        if table_exists:
            try:
                count_result = db.fetch_one("SELECT COUNT(*) as count FROM system_log")
                log_count = count_result['count'] if count_result else 0
            except Exception as e:
                log_count = f"获取数量失败: {str(e)}"
        
        # 获取最近的几条日志
        recent_logs = []
        if table_exists and isinstance(log_count, int) and log_count > 0:
            try:
                recent_logs = db.fetch_all("SELECT * FROM system_log ORDER BY timestamp DESC LIMIT 3")
            except Exception as e:
                recent_logs = f"获取最近日志失败: {str(e)}"
        
        return jsonify({
            'success': True,
            'data': {
                'database_status': db_status,
                'system_log_table_exists': table_exists,
                'table_structure': table_structure,
                'log_count': log_count,
                'recent_logs': recent_logs,
                'session_info': {
                    'username': session.get('username'),
                    'role': session.get('role'),
                    'user_id': session.get('user_id')
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'检查数据库状态失败: {str(e)}'}), 500

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not Found', 'message': '页面不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal Server Error', 'message': '服务器内部错误'}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 独立管理员系统启动中...")
    print("=" * 60)
    print("🌐 管理员系统地址: http://127.0.0.1:8080")
    print("🔍 健康检查: http://127.0.0.1:8080/health")
    print("📊 控制台: http://127.0.0.1:8080/admin/dashboard")
    print("🔐 登录页面: http://127.0.0.1:8080/login")
    print("📝 注册页面: http://127.0.0.1:8080/register")
    print("=" * 60)
    print("💡 提示: 按 Ctrl+C 停止服务")
    print("=" * 60)

    try:
        app.run(
            debug=True,
            host='0.0.0.0',
            port=8080,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 独立管理员系统已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)








