from flask import Blueprint, request, jsonify
from ..utils.database import get_db
from datetime import datetime, timezone, timedelta

admin_api = Blueprint('admin_api', __name__)

# 用户管理
@admin_api.route('/api/admin/users', methods=['GET'])
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

@admin_api.route('/api/admin/users', methods=['POST'])
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
        return jsonify({'success': True, 'message': '用户创建成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加用户失败: {e}'}), 500

@admin_api.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
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
        check_sql = "SELECT id FROM login_user WHERE id = %s"
        user = db.fetch_one(check_sql, (user_id,))
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        update_sql = "UPDATE login_user SET role = %s WHERE id = %s"
        db.execute(update_sql, (new_role, user_id))
        return jsonify({'success': True, 'message': '用户角色更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新用户角色失败: {e}'}), 500

@admin_api.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """删除用户"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT id FROM login_user WHERE id = %s"
        user = db.fetch_one(check_sql, (user_id,))
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        delete_sql = "DELETE FROM login_user WHERE id = %s"
        db.execute(delete_sql, (user_id,))
        return jsonify({'success': True, 'message': '用户删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除用户失败: {e}'}), 500

# 日志管理
@admin_api.route('/api/admin/logs', methods=['GET'])
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

@admin_api.route('/api/admin/logs/clear', methods=['DELETE'])
def clear_logs():
    """清空系统日志"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        db.execute("DELETE FROM system_log")
        return jsonify({'success': True, 'message': '系统日志清空成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'系统日志清空失败: {e}'}), 500

@admin_api.route('/api/admin/logs/export', methods=['GET'])
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
        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=system_logs.csv'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'导出系统日志失败: {e}'}), 500

# 检测记录管理
@admin_api.route('/api/admin/records', methods=['GET'])
def admin_records():
    """获取所有检测记录"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        # 获取筛选参数
        result_filter = request.args.get('result', '').strip()
        driver_id = request.args.get('driver_id', '').strip()
        date_range = request.args.get('date_range', '').strip()
        
        # 构建SQL查询
        sql = """
        SELECT id, username, timestamp, method, result, fatigue_level, status,
               remark, details, duration, confidence 
        FROM detection_record 
        WHERE 1=1
        """
        params = []
        
        if result_filter:
            sql += " AND result = %s"
            params.append(result_filter)
        
        if driver_id:
            sql += " AND driver_id = %s"
            params.append(driver_id)
        
        if date_range:
            # 这里可以根据需要解析日期范围
            pass
        
        sql += " ORDER BY timestamp DESC LIMIT 200"
        
        records = db.fetch_all(sql, params) if params else db.fetch_all(sql)
        
        # 格式化时间字段
        for record in records:
            if record.get('timestamp'):
                # 如果timestamp是datetime对象，转换为字符串
                if hasattr(record['timestamp'], 'strftime'):
                    record['timestamp'] = record['timestamp'].strftime('%Y-%mgrxx-%d %H:%M:%S')
                # 如果已经是字符串，保持原样
        
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取检测记录失败: {e}'}), 500

@admin_api.route('/api/admin/records/<int:record_id>', methods=['DELETE'])
def delete_admin_record(record_id):
    """删除管理员记录"""
    try:
        print(f"[DEBUG] 管理员删除记录请求: ID={record_id}")
        db = get_db()
        if not db:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        # 先获取记录信息，以便删除相关文件
        record = db.fetch_one("SELECT * FROM detection_record WHERE id = %s", (record_id,))
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        
        # 删除数据库记录
        db.execute("DELETE FROM detection_record WHERE id = %s", (record_id,))
        print(f"[DEBUG] 管理员记录删除成功: ID={record_id}")
        
        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        print(f"[ERROR] 删除管理员记录失败: {e}")
        return jsonify({'success': False, 'message': '删除记录失败'}), 500

@admin_api.route('/api/admin/logs', methods=['POST'])
def create_log():
    """写入系统日志"""
    try:
        data = request.get_json()
        username = data.get('username')
        role = data.get('role')
        action = data.get('action')
        details = data.get('details', '')
        ip_address = request.remote_addr
        if not all([username, role, action]):
            return jsonify({'success': False, 'message': '用户名、角色和操作不能为空'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "INSERT INTO system_log (username, role, action, details, ip_address) VALUES (%s, %s, %s, %s, %s)"
        db.execute(sql, (username, role, action, details, ip_address))
        return jsonify({'success': True, 'message': '日志创建成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建系统日志失败: {e}'}), 500

# 仪表盘统计
@admin_api.route('/api/admin/dashboard-stats', methods=['GET'])
def dashboard_stats():
    """获取仪表盘统计数据"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        total_users = db.fetch_one("SELECT COUNT(*) as cnt FROM login_user")['cnt']
        online_drivers = db.fetch_one("SELECT COUNT(*) as cnt FROM login_user WHERE role='driver'")['cnt']
        today_detections = db.fetch_one("SELECT COUNT(*) as cnt FROM detection_record WHERE DATE(timestamp) = CURDATE()")['cnt']
        fatigue_alerts = db.fetch_one("SELECT COUNT(*) as cnt FROM detection_record WHERE result='fatigue' AND DATE(timestamp) = CURDATE()")['cnt']
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

# 最近活动
@admin_api.route('/api/admin/recent-activities', methods=['GET'])
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

# 公告
@admin_api.route('/api/admin/announcements', methods=['GET'])
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

@admin_api.route('/api/admin/announcements', methods=['POST'])
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
        return jsonify({'success': True, 'message': '公告发布成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'公告发布失败: {e}'}), 500

@admin_api.route('/api/admin/announcements/<int:announcement_id>', methods=['DELETE'])
def delete_announcement(announcement_id):
    """删除公告"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        check_sql = "SELECT id FROM announcement WHERE id = %s"
        announcement = db.fetch_one(check_sql, (announcement_id,))
        if not announcement:
            return jsonify({'success': False, 'message': '公告不存在'}), 404
        delete_sql = "DELETE FROM announcement WHERE id = %s"
        db.execute(delete_sql, (announcement_id,))
        return jsonify({'success': True, 'message': '公告删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除公告失败: {e}'}), 500

# 检测记录
@admin_api.route('/api/admin/records', methods=['GET'])
def get_records():
    """获取检测记录，支持筛选"""
    try:
        result = request.args.get('result', '').strip()
        driver_id = request.args.get('driver_id', '').strip()
        date_range = request.args.get('date_range', '').strip()
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, timestamp, method, result, fatigue_level, status FROM detection_record WHERE 1=1"
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
            except Exception:
                pass
        sql += " ORDER BY timestamp DESC"
        records = db.fetch_all(sql, tuple(params))
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取检测记录失败: {e}'}), 500

@admin_api.route('/api/admin/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    """修改检测记录"""
    try:
        data = request.get_json()
        fatigue_level = data.get('fatigue_level')
        status = data.get('status')
        
        if not fatigue_level and not status:
            return jsonify({'success': False, 'message': '至少需要提供一个要修改的字段'}), 400
        
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        # 检查记录是否存在
        check_sql = "SELECT id FROM detection_record WHERE id = %s"
        record = db.fetch_one(check_sql, (record_id,))
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        
        # 构建更新SQL
        update_fields = []
        params = []
        
        if fatigue_level:
            update_fields.append("fatigue_level = %s")
            params.append(fatigue_level)
        
        if status:
            update_fields.append("status = %s")
            params.append(status)
        
        if update_fields:
            params.append(record_id)
            update_sql = f"UPDATE detection_record SET {', '.join(update_fields)} WHERE id = %s"
            db.execute(update_sql, tuple(params))
        
        return jsonify({'success': True, 'message': '记录修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改记录失败: {e}'}), 500

@admin_api.route('/api/admin/records/<int:record_id>', methods=['DELETE'])
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

@admin_api.route('/api/admin/records/export', methods=['GET'])
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
        sql = "SELECT id, username, timestamp, method, result, fatigue_level, status FROM detection_record WHERE 1=1"
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
            except Exception:
                pass
        sql += " ORDER BY timestamp DESC"
        records = db.fetch_all(sql, tuple(params))
        # 生成CSV
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', '驾驶员', '检测时间', '检测方式', '检测结果', '疲劳程度', '处理状态'])
        for r in records:
            cw.writerow([
                r.get('id'), r.get('username'), r.get('timestamp'), r.get('method'),
                r.get('result'), r.get('fatigue_level'), r.get('status')
            ])
        output = si.getvalue().encode('utf-8-sig')
        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=records.csv'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'导出检测记录失败: {e}'}), 500

# 驾驶员列表
@admin_api.route('/api/admin/drivers', methods=['GET'])
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

# 其它
@admin_api.route('/api/admin/profile', methods=['GET'])
def admin_profile():
    """获取管理员个人信息"""
    try:
        # 假设管理员信息通过 session 或 token 获取，这里简化为取第一个 admin
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

@admin_api.route('/api/admin/change-password', methods=['POST'])
def admin_change_password():
    """管理员修改密码"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        current_password = data.get('current_password', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        if not username or not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': '所有字段均不能为空'}), 400
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': '两次输入的新密码不一致'}), 400
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT password FROM login_user WHERE username = %s AND role='admin'"
        user = db.fetch_one(sql, (username,))
        if not user or user['password'] != current_password:
            return jsonify({'success': False, 'message': '当前密码错误'}), 400
        update_sql = "UPDATE login_user SET password = %s WHERE username = %s AND role='admin'"
        db.execute(update_sql, (new_password, username))
        return jsonify({'success': True, 'message': '密码修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'密码修改失败: {e}'}), 500

@admin_api.route('/api/admin/change-username', methods=['POST'])
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
        sql = "SELECT password FROM login_user WHERE username = %s AND role='admin'"
        user = db.fetch_one(sql, (old_username,))
        if not user or user['password'] != confirm_password:
            return jsonify({'success': False, 'message': '密码确认错误'}), 400
        # 检查新用户名是否已存在
        check_sql = "SELECT id FROM login_user WHERE username = %s"
        if db.fetch_one(check_sql, (new_username,)):
            return jsonify({'success': False, 'message': '新用户名已存在'}), 400
        update_sql = "UPDATE login_user SET username = %s WHERE username = %s AND role='admin'"
        db.execute(update_sql, (new_username, old_username))
        return jsonify({'success': True, 'message': '用户名修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'用户名修改失败: {e}'}), 500

@admin_api.route('/api/admin/system-settings', methods=['POST'])
def system_settings():
    """保存系统设置（这里只做示例，实际应存入配置表）"""
    try:
        data = request.get_json()
        # 假设有 system_name, detection_threshold, detection_interval, log_retention
        # 实际应存入数据库配置表，这里仅返回成功
        return jsonify({'success': True, 'message': '系统设置保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'系统设置保存失败: {e}'}), 500

# @admin_api.route('/api/admin/export-data', methods=['GET'])
# def export_data():
#     """导出系统全部数据（示例，实际可导出多表）"""
#     import csv
#     from io import StringIO
#     from flask import Response
#     try:
#         db = get_db()
#         if db is None:
#             return jsonify({'success': False, 'message': '数据库连接失败'}), 500
#         # 这里只导出用户表为例
#         users = db.fetch_all("SELECT id, username, role, register_time, last_login FROM login_user")
#         si = StringIO()
#         cw = csv.writer(si)
#         cw.writerow(['ID', '用户名', '角色', '注册时间', '最后登录'])
#         for u in users:
#             cw.writerow([u.get('id'), u.get('username'), u.get('role'), u.get('register_time'), u.get('last_login')])
#         output = si.getvalue().encode('utf-8-sig')
#         return Response(
#             output,
#             mimetype='text/csv',
#             headers={
#                 'Content-Disposition': 'attachment; filename=all_users.csv'
#             }
#         )
#     except Exception as e:
#         return jsonify({'success': False, 'message': f'导出数据失败: {e}'}), 500

# @admin_api.route('/api/admin/system-backup', methods=['POST'])
# def system_backup():
#     """系统备份（示例，实际应调用备份脚本）"""
#     try:
#         # 这里只做示例，实际应调用备份脚本或服务
#         return jsonify({'success': True, 'message': '系统备份创建成功'})
#     except Exception as e:
#         return jsonify({'success': False, 'message': f'系统备份失败: {e}'}), 500 