from flask import Blueprint, request, jsonify
from app.utils.database import get_db

common_api = Blueprint('common_api', __name__)

# 修改密码
@common_api.route('/api/user/change-password', methods=['POST'])
def change_password():
    try:
        # 兼容 JSON 和表单
        data = request.get_json(silent=True)
        if not data:
            data = request.form
        username = data.get('username', '').strip()
        current_password = data.get('current_password', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        if not username or not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': '所有字段均不能为空'}), 400
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': '两次输入的新密码不一致'}), 400
        if len(new_password) < 6 or len(new_password) > 20:
            return jsonify({'success': False, 'message': '密码长度必须在6-20位之间'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT password FROM login_user WHERE username = %s"
        user = db.fetch_one(sql, (username,))
        if not user or user['password'] != current_password:
            return jsonify({'success': False, 'message': '当前密码错误'}), 400
        update_sql = "UPDATE login_user SET password = %s WHERE username = %s"
        db.execute(update_sql, (new_password, username))
        return jsonify({'success': True, 'message': '密码修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'因为网络问题无法修改，请稍等: {e}'}), 500

# 修改用户名
@common_api.route('/api/user/change-username', methods=['POST'])
def change_username():
    try:
        # 兼容 JSON 和表单
        data = request.get_json(silent=True)
        if not data:
            data = request.form
        old_username = data.get('username', '').strip()  # 兼容前端和app.py传递的字段
        new_username = data.get('new_username', '').strip()
        confirm_password = data.get('confirm_password_username', '').strip()
        if not old_username or not new_username or not confirm_password:
            return jsonify({'success': False, 'message': '所有字段均不能为空'}), 400
        if len(new_username) < 3 or len(new_username) > 20:
            return jsonify({'success': False, 'message': '用户名长度必须在3-20位之间'}), 400
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
            return jsonify({'success': False, 'message': '用户名只能包含字母、数字和下划线'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT password FROM login_user WHERE username = %s"
        user = db.fetch_one(sql, (old_username,))
        if not user or user['password'] != confirm_password:
            return jsonify({'success': False, 'message': '密码确认错误'}), 400
        # 检查新用户名是否已存在
        check_sql = "SELECT id FROM login_user WHERE username = %s"
        if db.fetch_one(check_sql, (new_username,)):
            return jsonify({'success': False, 'message': '新用户名已存在'}), 400

        # 开始批量更新用户名
        try:
            # 暂时关闭外键检查，避免更新顺序导致约束冲突
            db.execute("SET FOREIGN_KEY_CHECKS=0;")

            # 需要更新的表列表
            tables_to_update = [
                'login_user',  # 用户信息表
                'detection_record',  # 检测记录表
                'system_log',  # 系统操作日志表
                'modify_log'  # 修改日志表
            ]

            for tbl in tables_to_update:
                update_sql = f"UPDATE {tbl} SET username = %s WHERE username = %s"
                db.execute(update_sql, (new_username, old_username))

            # 更新完成后重新开启外键检查
            db.execute("SET FOREIGN_KEY_CHECKS=1;")
        except Exception as e:
            # 如果更新失败，恢复外键检查并抛出异常
            db.execute("SET FOREIGN_KEY_CHECKS=1;")
            raise

        return jsonify({'success': True, 'message': '用户名修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'用户名修改失败: {e}'}), 500

# 查询今日是否已修改
@common_api.route('/api/user/modify-status', methods=['GET'])
def modify_status():
    try:
        username = request.args.get('username', '').strip()
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        # 假设有 modify_log 表记录修改历史
        sql = "SELECT type FROM modify_log WHERE username = %s AND DATE(modify_time) = CURDATE()"
        logs = db.fetch_all(sql, (username,))
        password_modified_today = any(l['type'] == 'password' for l in logs)
        username_modified_today = any(l['type'] == 'username' for l in logs)
        return jsonify({'success': True, 'data': {
            'password_modified_today': password_modified_today,
            'username_modified_today': username_modified_today
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': f'查询修改状态失败: {e}'}), 500

# 获取修改历史
@common_api.route('/api/user/modify-history', methods=['GET'])
def modify_history():
    try:
        username = request.args.get('username', '').strip()
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT modify_time, type, content, ip_address FROM modify_log WHERE username = %s ORDER BY modify_time DESC LIMIT 50"
        logs = db.fetch_all(sql, (username,))
        return jsonify({'success': True, 'data': logs})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取修改历史失败: {e}'}), 500

# 登录接口
@common_api.route('/api/auth/login', methods=['POST'])
def login():
    try:
        # 兼容 JSON 和表单
        data = request.get_json(silent=True)
        if not data:
            data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, password, role, register_time, last_login FROM login_user WHERE username = %s"
        user = db.fetch_one(sql, (username,))
        if not user or user['password'] != password:
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 400
        # 更新最后登录时间
        db.execute("UPDATE login_user SET last_login = NOW() WHERE id = %s", (user['id'],))
        return jsonify({'success': True, 'data': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'register_time': user['register_time'],
            'last_login': user['last_login']
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': f'登录失败: {e}'}), 500

# 注册接口
@common_api.route('/api/auth/register', methods=['POST'])
def register():
    try:
        # 兼容 JSON 和表单
        data = request.get_json(silent=True)
        if not data:
            data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'driver')
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT id FROM login_user WHERE username = %s"
        if db.fetch_one(check_sql, (username,)):
            return jsonify({'success': False, 'message': '用户名已存在'}), 400
        insert_sql = "INSERT INTO login_user (username, password, role, register_time) VALUES (%s, %s, %s, NOW())"
        db.execute(insert_sql, (username, password, role))
        return jsonify({'success': True, 'message': '注册成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'注册失败: {e}'}), 500 