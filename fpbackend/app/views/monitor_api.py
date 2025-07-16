from flask import Blueprint, request, jsonify
from ..utils.database import get_db
from ..utils.yolo_detector import detector
import os
import tempfile
from datetime import datetime

monitor_api = Blueprint('monitor_api', __name__)

# 图片检测
@monitor_api.route('/api/monitor/detect/image', methods=['POST'])
def detect_image():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        # 检查文件类型
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
        if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
            return jsonify({'success': False, 'message': '不支持的文件格式'})
        
        # 保存上传的文件
        upload_dir = 'static/uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"upload_{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # 执行检测
        result = detector.detect_image(file_path, upload_dir)
        
        if result['success']:
            # 记录检测结果到数据库
            try:
                db = get_db()
                if db:
                    sql = """
                    INSERT INTO detection_record 
                    (username, timestamp, method, result, fatigue_level, status, details) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    fatigue_level = 'high' if result['detection_info']['fatigue_indicators'] else 'low'
                    details = str(result['detection_info'])
                    db.execute(sql, (
                        '监控检测',
                        datetime.now(),
                        'image',
                        'normal',
                        fatigue_level,
                        'completed',
                        details
                    ))
            except Exception as e:
                print(f"记录检测结果失败: {e}")
            
            return jsonify({
                'success': True,
                'result': 'normal',
                'fatigue_level': 'high' if result['detection_info']['fatigue_indicators'] else 'low',
                'message': '图片检测完成',
                'output_path': result['output_path'],
                'detection_info': result['detection_info']
            })
        else:
            return jsonify({'success': False, 'message': result['message']})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'图片检测失败: {e}'})

# 视频检测
@monitor_api.route('/api/monitor/detect/video', methods=['POST'])
def detect_video():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        # 检查文件类型
        allowed_extensions = {'mp4', 'avi', 'mov', 'mkv', 'wmv'}
        if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
            return jsonify({'success': False, 'message': '不支持的文件格式'})
        
        # 保存上传的文件
        upload_dir = 'static/uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"upload_{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # 执行检测
        result = detector.detect_video(file_path, upload_dir)
        
        if result['success']:
            # 记录检测结果到数据库
            try:
                db = get_db()
                if db:
                    sql = """
                    INSERT INTO detection_record 
                    (username, timestamp, method, result, fatigue_level, status, details) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    fatigue_level = 'high' if result['detection_info']['fatigue_indicators'] else 'low'
                    details = str(result['detection_info'])
                    db.execute(sql, (
                        '监控检测',
                        datetime.now(),
                        'video',
                        'normal',
                        fatigue_level,
                        'completed',
                        details
                    ))
            except Exception as e:
                print(f"记录检测结果失败: {e}")
            
            return jsonify({
                'success': True,
                'result': 'normal',
                'fatigue_level': 'high' if result['detection_info']['fatigue_indicators'] else 'low',
                'message': '视频检测完成',
                'output_path': result['output_path'],
                'detection_info': result['detection_info']
            })
        else:
            return jsonify({'success': False, 'message': result['message']})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'视频检测失败: {e}'})

# 摄像头检测
@monitor_api.route('/api/monitor/detect/camera', methods=['POST'])
def detect_camera():
    return jsonify({'success': True, 'result': 'normal', 'fatigue_level': 'low', 'message': '摄像头检测功能开发中'})

# 远程摄像头检测
@monitor_api.route('/api/monitor/detect/remote', methods=['POST'])
def detect_remote():
    return jsonify({'success': True, 'result': 'normal', 'fatigue_level': 'low', 'message': '远程摄像头检测功能开发中'})

# 检测记录
@monitor_api.route('/api/monitor/records', methods=['GET'])
def monitor_records():
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = """
        SELECT id, username, timestamp, method, result, fatigue_level, status,
               remark, details, duration, confidence 
        FROM detection_record 
        ORDER BY timestamp DESC LIMIT 100
        """
        records = db.fetch_all(sql)
        
        # 格式化时间字段
        for record in records:
            if record.get('timestamp'):
                # 如果timestamp是datetime对象，转换为字符串
                if hasattr(record['timestamp'], 'strftime'):
                    record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                # 如果已经是字符串，保持原样
        
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取检测记录失败: {e}'}), 500


@monitor_api.route('/api/monitor/records/<int:record_id>', methods=['DELETE'])
def delete_monitor_record(record_id):
    """删除监控记录"""
    try:
        print(f"[DEBUG] 监控删除记录请求: ID={record_id}")
        db = get_db()
        if not db:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        # 先获取记录信息，以便删除相关文件
        record = db.fetch_one("SELECT * FROM detection_record WHERE id = %s", (record_id,))
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404

        # 删除数据库记录
        db.execute("DELETE FROM detection_record WHERE id = %s", (record_id,))
        print(f"[DEBUG] 监控记录删除成功: ID={record_id}")

        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        print(f"[ERROR] 删除监控记录失败: {e}")
        return jsonify({'success': False, 'message': '删除记录失败'}), 500


@monitor_api.route('/api/monitor/records/<int:record_id>/fatigue-level', methods=['PUT'])
def update_monitor_record(record_id):
    """更新检测记录的疲劳程度"""
    try:
        data = request.get_json(silent=True) or {}
        new_level = str(data.get('fatigue_level', '')).strip().lower()
        if not new_level:
            return jsonify({'success': False, 'message': 'fatigue_level 不能为空'}), 400

        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500

        sql = "UPDATE detection_record SET fatigue_level = %s WHERE id = %s"
        db.execute(sql, (new_level, record_id))
        return jsonify({'success': True, 'message': '记录更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新记录失败: {e}'}), 500


# 个人信息
@monitor_api.route('/api/monitor/profile', methods=['GET'])
def monitor_profile():
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        sql = "SELECT id, username, role, register_time, last_login FROM login_user WHERE role='monitor' LIMIT 1"
        user = db.fetch_one(sql)
        if not user:
            return jsonify({'success': False, 'message': '未找到监控人员信息'}), 404
        return jsonify({'success': True, 'data': user})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取个人信息失败: {e}'}), 500 