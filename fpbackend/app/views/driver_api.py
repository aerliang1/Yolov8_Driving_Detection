from flask import Blueprint, request, jsonify
from ..utils.database import get_db

driver_api = Blueprint('driver_api', __name__)

# 检测（这里只做接口骨架，实际检测逻辑需对接AI/算法服务）
@driver_api.route('/api/driver/detect/camera', methods=['POST'])
def detect_camera():
    return jsonify({'success': True, 'result': 'normal', 'fatigue_level': 'low', 'message': '摄像头检测功能开发中'})

# 检测记录
@driver_api.route('/api/driver/records', methods=['GET'])
def driver_records():
    try:
        print("[DEBUG] 驾驶员记录API被调用")

        # 从请求参数获取用户名（前端传递）
        username = request.args.get('username', '').strip()
        if not username:
            print("[DEBUG] 缺少用户名参数")
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        print(f"[DEBUG] 获取用户记录，用户名: {username}")

        db = get_db()
        if db is None:
            print("[DEBUG] 数据库连接失败")
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        print(f"[DEBUG] 数据库连接成功，执行查询... 用户名: {username}")
        sql = """
        SELECT id, username, timestamp, method, result, fatigue_level, status,
               remark, details, duration, confidence
        FROM detection_record
        WHERE username = %s
        ORDER BY timestamp DESC LIMIT 100
        """
        records = db.fetch_all(sql, (username,))
        print(f"[DEBUG] 查询结果：找到 {len(records)} 条记录")

        # 格式化时间字段
        for record in records:
            if record.get('timestamp'):
                # 如果timestamp是datetime对象，转换为字符串
                if hasattr(record['timestamp'], 'strftime'):
                    record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                elif not isinstance(record['timestamp'], str):
                    record['timestamp'] = str(record['timestamp'])

        if len(records) > 0:
            print(f"[DEBUG] 第一条记录示例: {records[0]}")
        else:
            print("[DEBUG] 数据库中没有记录")

        return jsonify({'success': True, 'data': records})

    except Exception as e:
        print(f"[DEBUG] 获取检测记录异常: {e}")
        return jsonify({'success': False, 'message': f'获取检测记录失败: {e}'}), 500

# 个人信息
@driver_api.route('/api/driver/profile', methods=['GET'])
def driver_profile():
    try:
        username = request.args.get('username', '').strip()
        if not username:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, role, register_time, last_login FROM login_user WHERE username = %s AND role='driver'"
        user = db.fetch_one(sql, (username,))
        if not user:
            return jsonify({'success': False, 'message': '未找到驾驶员信息'}), 404
        return jsonify({'success': True, 'data': user})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取个人信息失败: {e}'}), 500