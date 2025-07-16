from flask import Blueprint, request, jsonify, Response, stream_with_context, session
from app.utils.database import get_db
from app.utils.yolo_detector import detector
import os
import cv2
import uuid
import shutil
from datetime import datetime
from ultralytics import YOLO
import tempfile
import json
import time
from collections import defaultdict, deque

detect_api = Blueprint('detect_api', __name__)

# 全局变量用于存储检测状态和结果
# 摄像头检测数据，累计统计
camera_detection_data = {}  
# 视频检测数据，累计统计
video_detection_data = {}   
# 摄像头检测开始时间
camera_start_times = {}     
# 存储实时检测结果
real_time_detection_results = {}
# 缓存已加载模型，避免重复加载耗时
_model_cache = {}
# 在文件顶部添加全局变量
last_play_time = 0

# 实时检测数据存储 - 每0.5秒更新一次
real_time_detection_data = defaultdict(lambda: {
    'closed_eyes': deque(maxlen=200),  # 最多保存100秒的数据(200 * 0.5s)
    'open_mouth': deque(maxlen=200),
    'open_eyes': deque(maxlen=200),
    'closed_mouth': deque(maxlen=200),
    'last_update': 0.0,
    'last_fatigue_check': 0.0,
    'current_fatigue_level': 'low',
    'detection_active': False
})

# 每5秒生成的完整检测记录
fatigue_records = defaultdict(list)

# 添加全局session管理
current_detection_session = {
    'session_id': None,
    'username': 'camera_user',
    'start_time': None
}

# 全局变量控制检测流状态
camera_stream_control = {}

def _get_model(model_filename):
    """按文件名加载或复用YOLO模型"""
    if model_filename in _model_cache:
        return _model_cache[model_filename]
    
    # 在fpbackend中查找模型文件
    model_paths = [
        os.path.join('models', 'uploads', model_filename),
        os.path.join('..', 'fpdemo', 'models', 'uploads', model_filename),
        model_filename
    ]
    
    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            break
    
    if not model_path:
        raise FileNotFoundError(f"模型文件不存在: {model_filename}")
    
    model = YOLO(model_path)
    _model_cache[model_filename] = model
    return model

def _analyze_fatigue_level_camera(total_seconds, closed_eyes_count, open_mouth_count):
    """摄像头检测疲劳分析 - 基于每秒行为频率的四级判断"""
    if total_seconds <= 0:
        return 'none'
    
    # 计算每秒的行为频率
    closed_eyes_per_second = closed_eyes_count / total_seconds
    open_mouth_per_second = open_mouth_count / total_seconds
    
    print(f"[DEBUG] 疲劳分析: 检测时长={total_seconds:.1f}秒, 闭眼={closed_eyes_count}次({closed_eyes_per_second:.2f}/秒), 张嘴={open_mouth_count}次({open_mouth_per_second:.2f}/秒)")
    
    # 放松闭眼检测标准，因为人需要眨眼
    # 重度疲劳：每秒闭眼≥8次或张嘴≥2次 (非常严重的疲劳状态)
    if closed_eyes_per_second >= 6.0 or open_mouth_per_second >= 2.0:
        return 'severe'
    
    # 中度疲劳：每秒闭眼≥6次或张嘴≥1.5次 (明显疲劳)
    elif closed_eyes_per_second >= 4.0 or open_mouth_per_second >= 1.5:
        return 'moderate'
    
    # 轻度疲劳：每秒闭眼≥4次或张嘴≥0.8次 (轻微疲劳)
    elif closed_eyes_per_second >= 2.0 or open_mouth_per_second >= 0.8:
        return 'mild'
    
    # 不疲劳：低于轻度疲劳标准
    else:
        return 'none'

def _analyze_fatigue_level_simple(results):
    """
    简单的疲劳程度分析 - 用于图片和视频检测
    不依赖时间序列数据，只分析当前检测结果
    """
    # 当前帧的检测统计
    current_stats = {
        'closed_eyes': 0,
        'open_mouth': 0, 
        'open_eyes': 0,
        'closed_mouth': 0,
        'total_objects': 0
    }
    
    # 分析YOLO检测结果 - 根据用户标签：0=闭眼，1=闭嘴，2=睁眼，3=张嘴
    for result in results:
        if result.boxes is not None:
            current_stats['total_objects'] = len(result.boxes)
            for box in result.boxes:
                # 安全地访问tensor数据
                try:
                    cls = int(box.cls.item()) if hasattr(box.cls, 'item') else int(box.cls[0] if len(box.cls.shape) > 0 else box.cls)
                    conf = float(box.conf.item()) if hasattr(box.conf, 'item') else float(box.conf[0] if len(box.conf.shape) > 0 else box.conf)
                    
                    if conf > 0.5:  # 置信度阈值
                        if cls == 0:  # 闭眼
                            current_stats['closed_eyes'] += 1
                        elif cls == 1:  # 闭嘴
                            current_stats['closed_mouth'] += 1
                        elif cls == 2:  # 睁眼
                            current_stats['open_eyes'] += 1
                        elif cls == 3:  # 张嘴
                            current_stats['open_mouth'] += 1
                except (IndexError, RuntimeError, ValueError) as e:
                    print(f"[DEBUG] 跳过无效的检测结果: {e}")
                    continue
    
    # 简单的疲劳程度判断 - 基于当前检测结果
    if current_stats['closed_eyes'] >= 2 or current_stats['open_mouth'] >= 1:
        fatigue_level = 'high'
    elif current_stats['closed_eyes'] >= 1:
        fatigue_level = 'medium'
    else:
        fatigue_level = 'low'
    
    # 生成疲劳指标
    fatigue_indicators = []
    if current_stats['closed_eyes'] > 0:
        fatigue_indicators.append({'type': 'closed_eyes', 'count': current_stats['closed_eyes']})
    if current_stats['open_mouth'] > 0:
        fatigue_indicators.append({'type': 'open_mouth', 'count': current_stats['open_mouth']})
    
    return {
        'fatigue_level': fatigue_level,
        'current_stats': current_stats,
        'fatigue_indicators': fatigue_indicators
    }




def _get_video_detection_stats(session_id):
    """获取视频检测统计数据"""
    if session_id not in video_detection_data:
        return {
            'total_detections': 0,
            'closed_eyes_count': 0,
            'open_mouth_count': 0,
            'open_eyes_count': 0,
            'closed_mouth_count': 0,
            'fatigue_indicators': [],
            'detection_active': False,
            'total_frames': 0,
            'fatigue_level': 'none'
        }
    
    stats = video_detection_data[session_id]
    
    # 基于总帧数和FPS估算总时长
    total_seconds = stats['total_frames'] / 25.0  # 假设25FPS
    
    # 计算疲劳等级
    fatigue_level = _analyze_fatigue_level_camera(
        total_seconds,
        stats['closed_eyes_count'],
        stats['open_mouth_count']
    )
    
    # 生成疲劳指标
    fatigue_indicators = []
    if stats['closed_eyes_count'] > 0:
        fatigue_indicators.append({'type': 'closed_eyes', 'count': stats['closed_eyes_count']})
    if stats['open_mouth_count'] > 0:
        fatigue_indicators.append({'type': 'open_mouth', 'count': stats['open_mouth_count']})
    
    return {
        'total_detections': stats['total_detections'],
        'closed_eyes_count': stats['closed_eyes_count'],
        'open_mouth_count': stats['open_mouth_count'],
        'open_eyes_count': stats['open_eyes_count'],
        'closed_mouth_count': stats['closed_mouth_count'],
        'fatigue_indicators': fatigue_indicators,
        'detection_active': stats['detection_active'],
        'total_frames': stats['total_frames'],
        'fatigue_level': fatigue_level
    }

def _save_detection_result(username, method, result, fatigue_level, details, confidence=0.0, duration=0.0):
    """保存检测结果到数据库"""
    try:
        db = get_db()
        if db:
            sql = """
            INSERT INTO detection_record 
            (username, timestamp, method, result, fatigue_level, status, details, confidence, duration) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db.execute(sql, (
                username,
                datetime.now(),
                method,
                result,
                fatigue_level,
                'completed',
                details,
                confidence,
                duration
            ))
            return True
    except Exception as e:
        print(f"保存检测结果失败: {e}")
        return False

@detect_api.route('/api/detect', methods=['POST'])
def detect_file():
    """通用检测接口：支持图片/视频文件，使用指定.pt模型"""
    try:
        upload_file = request.files.get('file')
        stream_url = request.form.get('url', '').strip()
        model_name = request.form.get('model', '').strip()
        
        # 获取用户信息
        username = request.form.get('username', '').strip()
        user_role = request.form.get('user_role', '').strip()
        
        if not upload_file and not stream_url:
            return jsonify({'success': False, 'message': '未检测到上传文件或URL'}), 400
        
        if not model_name:
            return jsonify({'success': False, 'message': '缺少模型文件名'}), 400
        
        if not username:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        # 准备临时路径
        tmp_dir = 'static/uploads'
        os.makedirs(tmp_dir, exist_ok=True)
        
        # 如果是文件上传
        if upload_file:
            if upload_file.filename == '':
                return jsonify({'success': False, 'message': '文件名为空'}), 400
            
            print(f"[DEBUG] 上传文件名: {upload_file.filename}")
            ext = os.path.splitext(upload_file.filename)[1].lower()
            print(f"[DEBUG] 提取的扩展名: '{ext}'")
            
            if ext == '':
                mime = upload_file.mimetype or ''
                print(f"[DEBUG] 文件MIME类型: {mime}")
                if mime.startswith('image/'):
                    ext = '.jpg'
                elif mime.startswith('video/'):
                    ext = '.mp4'
                print(f"[DEBUG] 根据MIME设置的扩展名: '{ext}'")
            
            supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.mp4', '.avi', '.mov', '.mkv'}
            print(f"[DEBUG] 支持的格式: {supported_formats}")
            print(f"[DEBUG] 当前扩展名是否在支持列表中: {ext in supported_formats}")
            
            if ext not in supported_formats:
                return jsonify({'success': False, 'message': f'不支持的文件格式: {ext}，支持的格式: {list(supported_formats)}'}), 400
            
            tmp_filename = f"detect_{uuid.uuid4().hex}{ext}"
            tmp_path = os.path.join(tmp_dir, tmp_filename)
            upload_file.save(tmp_path)
        else:
            # 通过 URL 下载
            import requests as _req
            ext = os.path.splitext(stream_url.split('?')[0])[1].lower()
            if ext == '' or ext not in {'.jpg', '.jpeg', '.png', '.bmp', '.mp4', '.avi', '.mov', '.mkv'}:
                ext = '.jpg'  # 默认按图片处理
            
            tmp_filename = f"detect_{uuid.uuid4().hex}{ext}"
            tmp_path = os.path.join(tmp_dir, tmp_filename)
            
            try:
                r = _req.get(stream_url, timeout=10, stream=True)
                r.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as dl_e:
                return jsonify({'success': False, 'message': f'URL 下载失败: {dl_e}'}), 400
        
        # 判断是否为视频文件
        video_exts = {'.mp4', '.avi', '.mov', '.mkv'}
        is_video = os.path.splitext(tmp_path)[1].lower() in video_exts
        
        model = _get_model(model_name)
        session_id = str(uuid.uuid4())
        
        if is_video:
            # 视频检测
            static_dest_dir = os.path.join('static', 'uploads', 'results')
            processed_path = _predict_video(tmp_path, model, static_dest_dir, session_id)
            
            # 生成相对于后端服务的URL路径
            relative_path = os.path.relpath(processed_path, 'static').replace('\\', '/')
            output_url = f'/static/{relative_path}'
            
            # 获取视频检测的最终统计结果
            final_stats = _get_video_detection_stats(session_id)
            
            # 判断疲劳级别 - 使用统一的分析函数
            total_frames = final_stats.get('total_frames', 0)
            total_seconds = total_frames / 25.0  # 假设25FPS
            fatigue_level = _analyze_fatigue_level_camera(
                total_seconds,
                final_stats['closed_eyes_count'],
                final_stats['open_mouth_count']
            )
            
            # 保存检测结果（所有用户都可以保存）
            _save_detection_result(
                username,
                'video',
                'completed',
                fatigue_level,
                f'视频检测完成，文件: {upload_file.filename if upload_file else stream_url}',
                0.8,
                0.0
            )
            
            return jsonify({
                'success': True,
                'message': '视频检测完成',
                'output_path': output_url,
                'fatigue_level': fatigue_level,
                'detection_info': final_stats,
                'method': 'video',
                'session_id': session_id
            })
        
        # 图片检测
        results = model.predict(source=tmp_path, save=True, conf=0.5, imgsz=(640, 640), show_conf=True)
        
        # 分析疲劳程度 - 使用简单分析方法
        analysis_result = _analyze_fatigue_level_simple(results)
        fatigue_level = analysis_result['fatigue_level']
        
        # 处理图片检测结果
        output_url = None
        
        # YOLO 会把输出保存到 runs/detect/predict* 目录，找到最新生成的文件
        output_dir = None
        run_root = os.path.join(os.getcwd(), 'runs', 'detect')
        if os.path.exists(run_root):
            output_dirs = sorted([os.path.join(run_root, d) for d in os.listdir(run_root)], 
                               key=os.path.getmtime, reverse=True)
            if output_dirs:
                output_dir = output_dirs[0]
        
        if output_dir:
            # 创建结果目录
            static_dest_dir = os.path.join('static', 'uploads', 'results')
            os.makedirs(static_dest_dir, exist_ok=True)
            
            # 查找并复制检测结果图片
            for fname in os.listdir(output_dir):
                if fname.startswith(os.path.splitext(os.path.basename(tmp_path))[0]):
                    output_path = os.path.join(output_dir, fname)
                    
                    # 生成新的文件名，避免冲突
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_filename = f"result_{timestamp}_{fname}"
                    dest_path = os.path.join(static_dest_dir, new_filename)
                    
                    # 复制文件
                    shutil.copy(output_path, dest_path)
                    
                    # 生成相对于后端服务的URL路径
                    relative_path = os.path.relpath(dest_path, 'static').replace('\\', '/')
                    output_url = f'/static/{relative_path}'
                    break
        
        # 如果没有找到YOLO输出，使用原始图片
        if not output_url:
            # 直接使用原始图片作为输出
            static_dest_dir = os.path.join('static', 'uploads', 'results')
            os.makedirs(static_dest_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"result_{timestamp}_{os.path.basename(tmp_path)}"
            dest_path = os.path.join(static_dest_dir, new_filename)
            
            shutil.copy(tmp_path, dest_path)
            
            relative_path = os.path.relpath(dest_path, 'static').replace('\\', '/')
            output_url = f'/static/{relative_path}'
        
        # 保存检测结果（所有用户都可以保存）
        _save_detection_result(
            username,
            'image',
            'completed',
            fatigue_level,
            f'图片检测完成，文件: {upload_file.filename if upload_file else stream_url}',
            0.8,
            0.0
        )
        
        return jsonify({
            'success': True,
            'message': '图片检测完成',
            'output_path': output_url,
            'fatigue_level': fatigue_level,
            'detection_info': {
                'total_objects': analysis_result['current_stats']['total_objects'],
                'objects_detected': [
                    {'class': 'closed_eyes', 'confidence': 0.8} for _ in range(analysis_result['current_stats']['closed_eyes'])
                ] + [
                    {'class': 'open_mouth', 'confidence': 0.8} for _ in range(analysis_result['current_stats']['open_mouth'])
                ] + [
                    {'class': 'open_eyes', 'confidence': 0.8} for _ in range(analysis_result['current_stats']['open_eyes'])
                ] + [
                    {'class': 'closed_mouth', 'confidence': 0.8} for _ in range(analysis_result['current_stats']['closed_mouth'])
                ],
                'fatigue_indicators': analysis_result['fatigue_indicators']
            }
        })
        
    except Exception as e:
        print(f"检测失败: {e}")
        return jsonify({'success': False, 'message': f'检测失败: {e}'}), 500

def _predict_video(video_path: str, model, dest_dir: str, session_id: str) -> str:
    """逐帧推理视频并累计统计，返回结果视频绝对路径"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("无法打开视频文件")
    
    # 获取视频参数
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps < 1 or fps > 240:
        fps = 25.0  # 默认FPS
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    os.makedirs(dest_dir, exist_ok=True)
    out_name = os.path.splitext(os.path.basename(video_path))[0] + '_result.mp4'
    out_path = os.path.join(dest_dir, out_name)
    
    # 视频编码器
    fourcc_h264 = cv2.VideoWriter_fourcc(*'avc1')
    writer = cv2.VideoWriter(out_path, fourcc_h264, fps, (width, height))
    if not writer.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    
    frame_count = 0
    start_time = time.time()
    
    # 初始化累计统计
    if session_id not in video_detection_data:
        video_detection_data[session_id] = {
            'closed_eyes_count': 0,
            'open_mouth_count': 0,
            'open_eyes_count': 0,
            'closed_mouth_count': 0,
            'total_detections': 0,
            'total_frames': 0,
            'detection_active': True
        }
    
    print(f"[DEBUG] 开始视频检测，会话ID: {session_id}")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        current_time = time.time()
        
        # 使用模型进行检测
        result = model.predict(source=frame, conf=0.5, imgsz=(640, 640), verbose=False)
        
        # 提取检测结果并累计统计
        detection_results = []
        for res in result:
            if res.boxes is not None:
                for box in res.boxes:
                    # 安全地访问tensor数据
                    try:
                        cls = int(box.cls.item()) if hasattr(box.cls, 'item') else int(box.cls[0] if len(box.cls.shape) > 0 else box.cls)
                        conf = float(box.conf.item()) if hasattr(box.conf, 'item') else float(box.conf[0] if len(box.conf.shape) > 0 else box.conf)
                        
                        if conf > 0.5:  # 置信度阈值
                            detection_results.append({
                                'class': cls,
                                'confidence': conf
                            })
                            
                            # 累计统计
                            stats = video_detection_data[session_id]
                            if cls == 0:  # 闭眼
                                stats['closed_eyes_count'] += 1
                            elif cls == 1:  # 闭嘴
                                stats['closed_mouth_count'] += 1
                            elif cls == 2:  # 睁眼
                                stats['open_eyes_count'] += 1
                            elif cls == 3:  # 张嘴
                                stats['open_mouth_count'] += 1
                            
                            stats['total_detections'] += 1
                            
                    except (IndexError, RuntimeError, ValueError) as e:
                        print(f"[DEBUG] 跳过无效的检测结果: {e}")
                        continue
        
        # 在帧上绘制检测结果
        annotated = result[0].plot()
        
        # 添加统计信息到视频帧
        stats = video_detection_data[session_id]
        stats['total_frames'] = frame_count + 1
        
        # 计算视频总时长（基于帧数和FPS）
        total_seconds = (frame_count + 1) / fps
        
        # 计算疲劳等级
        fatigue_level = _analyze_fatigue_level_camera(
            total_seconds,
            stats['closed_eyes_count'],
            stats['open_mouth_count']
        )
        
        # 在视频上显示统计信息
        cv2.putText(annotated, f"Frame: {frame_count+1}/{int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated, f"Time: {total_seconds:.1f}s", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated, f"Total: {stats['total_detections']}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated, f"Eyes: {stats['closed_eyes_count']}/{stats['open_eyes_count']}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated, f"Mouth: {stats['open_mouth_count']}/{stats['closed_mouth_count']}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # 显示疲劳等级
        fatigue_colors = {
            'none': (0, 255, 0),      # 绿色 - 不疲劳
            'mild': (0, 255, 255),    # 黄色 - 轻度疲劳
            'moderate': (0, 165, 255), # 橙色 - 中度疲劳
            'severe': (0, 0, 255)     # 红色 - 重度疲劳
        }
        
        fatigue_text = {
            'none': 'No Fatigue',
            'mild': 'Mild Fatigue', 
            'moderate': 'Moderate Fatigue',
            'severe': 'Severe Fatigue'
        }.get(fatigue_level, fatigue_level)
        
        color = fatigue_colors.get(fatigue_level, (255, 255, 255))
        cv2.putText(annotated, fatigue_text, (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        
        writer.write(annotated)
        frame_count += 1
    
    cap.release()
    writer.release()
    
    print(f"[DEBUG] 视频处理完成，总帧数: {frame_count}")
    print(f"[DEBUG] 最终统计: {video_detection_data[session_id]}")
    
    return out_path

def _gen_stream(cap, model, session_id):
    """生成视频流 - 逐帧检测并累计统计"""
    frame_count = 0
    start_time = time.time()
    
    print(f"[DEBUG] 开始摄像头流，会话ID: {session_id}")
    
    # 初始化流控制状态
    camera_stream_control[session_id] = {
        'active': True,
        'start_time': start_time
    }
    
    # 初始化累计统计 - 如果数据不存在或者需要重新初始化
    if session_id not in camera_detection_data:
        print(f"[DEBUG] 首次初始化摄像头检测数据: {session_id}")
        camera_detection_data[session_id] = {
            'closed_eyes_count': 0,
            'open_mouth_count': 0,
            'open_eyes_count': 0,
            'closed_mouth_count': 0,
            'total_detections': 0,
            'start_time': start_time,
            'last_update': start_time
        }
    else:
        # 如果数据已存在，检查是否需要重新初始化开始时间
        # 这处理了重置后重新启动检测流的情况
        existing_data = camera_detection_data[session_id]
        if existing_data.get('start_time', 0) > start_time - 2:  # 如果开始时间是最近2秒内设置的，说明是重置后的重新启动
            print(f"[DEBUG] 检测到重置后重新启动，使用现有数据: {session_id}")
            print(f"[DEBUG] 现有数据: {existing_data}")
        else:
            print(f"[DEBUG] 长时间会话，保持现有数据: {session_id}")
    
    print(f"[DEBUG] 当前会话数据: {camera_detection_data[session_id]}")
    
    try:
        while True:
            # 检查流控制状态 - 如果被标记为停止，则退出循环
            if session_id in camera_stream_control and not camera_stream_control[session_id].get('active', True):
                print(f"[DEBUG] 检测流被停止，会话ID: {session_id}")
                break
                
            ret, frame = cap.read()
            if not ret:
                print(f"[DEBUG] 摄像头读取失败，结束流: {session_id}")
                break
        
            current_time = time.time()
        
            # 使用模型进行检测
            results = model(frame)
        
            # 提取检测结果并累计统计
            detection_results = []
        
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        # 安全地访问tensor数据
                        try:
                            cls = int(box.cls.item()) if hasattr(box.cls, 'item') else int(box.cls[0] if len(box.cls.shape) > 0 else box.cls)
                            conf = float(box.conf.item()) if hasattr(box.conf, 'item') else float(box.conf[0] if len(box.conf.shape) > 0 else box.conf)
                            
                            if conf > 0.5:  # 置信度阈值
                                detection_results.append({
                                    'class': cls,
                                    'confidence': conf
                                })
                                
                                # 累计统计
                                stats = camera_detection_data[session_id]
                                if cls == 0:  # 闭眼
                                    stats['closed_eyes_count'] += 1
                                elif cls == 1:  # 闭嘴
                                    stats['closed_mouth_count'] += 1
                                elif cls == 2:  # 睁眼
                                    stats['open_eyes_count'] += 1
                                elif cls == 3:  # 张嘴
                                    stats['open_mouth_count'] += 1
                                
                                stats['total_detections'] += 1
                                stats['last_update'] = current_time
                                
                        except (IndexError, RuntimeError, ValueError) as e:
                            print(f"[DEBUG] 跳过无效的检测结果: {e}")
                            continue
        
            # 存储最新检测结果
            real_time_detection_results[session_id] = {
                'results': detection_results,
                'timestamp': current_time,
                'frame_count': frame_count
            }
            
            # 在帧上绘制检测结果
            annotated = results[0].plot()
            
            # 添加统计信息到视频帧
            stats = camera_detection_data[session_id]
            total_seconds = current_time - stats['start_time']
            
            # 计算疲劳等级
            fatigue_level = _analyze_fatigue_level_camera(
                total_seconds, 
                stats['closed_eyes_count'], 
                stats['open_mouth_count']
            )
            
            # 在视频上显示统计信息
            cv2.putText(annotated, f"Frame: {frame_count+1}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(annotated, f"Time: {total_seconds:.1f}s", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(annotated, f"Total: {stats['total_detections']}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(annotated, f"Eyes: {stats['closed_eyes_count']}/{stats['open_eyes_count']}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(annotated, f"Mouth: {stats['open_mouth_count']}/{stats['closed_mouth_count']}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # 显示疲劳等级
            fatigue_colors = {
                'none': (0, 255, 0),      # 绿色 - 不疲劳
                'mild': (0, 255, 255),    # 黄色 - 轻度疲劳
                'moderate': (0, 165, 255), # 橙色 - 中度疲劳
                'severe': (0, 0, 255)     # 红色 - 重度疲劳
            }
            
            fatigue_text = {
                'none': 'No Fatigue',
                'mild': 'Mild Fatigue', 
                'moderate': 'Moderate Fatigue',
                'severe': 'Severe Fatigue'
            }.get(fatigue_level, fatigue_level)
            
            color = fatigue_colors.get(fatigue_level, (255, 255, 255))
            cv2.putText(annotated, fatigue_text, (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            _, jpeg = cv2.imencode('.jpg', annotated)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                   + jpeg.tobytes() + b'\r\n')
            
            frame_count += 1
    
    finally:
        # 清理资源
        print(f"[DEBUG] 清理摄像头流资源: {session_id}")
        cap.release()
        
        # 标记流为非活跃状态
        if session_id in camera_stream_control:
            camera_stream_control[session_id]['active'] = False
            print(f"[DEBUG] 标记流为非活跃: {session_id}")

@detect_api.route('/api/stream/camera')
def stream_camera():
    """实时摄像头流"""
    index = int(request.args.get('index', 0))
    model_name = request.args.get('model', '')
    username = request.args.get('username', '')
    
    if not model_name:
        return 'Missing model parameter', 400
    
    try:
        model = _get_model(model_name)
        # 使用与统计API一致的session_id格式
        session_id = f"camera_{username}"
        
        print(f"[DEBUG] 启动摄像头流，用户: {username}, 会话ID: {session_id}")
        
        # Windows 用 CAP_DSHOW
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        
        return Response(
            stream_with_context(_gen_stream(cap, model, session_id)),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        return f'stream error: {e}', 500

@detect_api.route('/api/stream/video')
def stream_video():
    """实时视频文件流"""
    video_path = request.args.get('path', '')
    model_name = request.args.get('model', '')
    
    if not video_path or not os.path.exists(video_path):
        return 'video not found', 404
    
    if not model_name:
        return 'Missing model parameter', 400
    
    try:
        model = _get_model(model_name)
        session_id = str(uuid.uuid4())
        
        cap = cv2.VideoCapture(os.path.abspath(video_path))
        
        return Response(
            stream_with_context(_gen_stream(cap, model, session_id)),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        return f'stream error: {e}', 500

@detect_api.route('/api/detect/camera/stop', methods=['POST'])
def stop_camera_detection():
    """停止摄像头检测"""
    try:
        data = request.get_json() or {}
        username = data.get('username', 'camera_user')
        session_id = f"camera_{username}"
        
        print(f"[DEBUG] 停止摄像头检测，用户: {username}, 会话ID: {session_id}")
        
        # 标记流为非活跃，这会让_gen_stream循环退出
        if session_id in camera_stream_control:
            camera_stream_control[session_id]['active'] = False
            print(f"[DEBUG] 已停止检测流: {session_id}")
        
        return jsonify({'success': True, 'message': '摄像头检测已停止'})
        
    except Exception as e:
        print(f"[ERROR] 停止摄像头检测失败: {str(e)}")
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'})

# @detect_api.route('/api/camera/update_stats', methods=['POST'])
# def update_camera_stats():
#     """独立的摄像头统计更新API"""
#     try:
#         data = request.get_json()
#         username = data.get('username', 'camera_user')
#         session_id = f"camera_{username}"
        
#         print(f"[DEBUG] 更新摄像头统计，会话ID: {session_id}")
        
#         # 模拟检测结果（实际中这里会接收真实的检测数据）
#         mock_results = []
        
#         # 使用分析函数处理统计
#         fatigue_level, detection_info = _analyze_fatigue_level_realtime(mock_results, session_id)
        
#         return jsonify({
#             'success': True,
#             'fatigue_level': fatigue_level,
#             'detection_info': detection_info
#         })
        
#     except Exception as e:
#         print(f"[ERROR] 更新摄像头统计失败: {str(e)}")
#         return jsonify({
#             'success': False,
#             'message': f'更新统计失败: {str(e)}'
#         })

@detect_api.route('/api/get_detected_objects')
def get_detected_objects():
    global last_play_time
    try:
        print(f"[DEBUG] 收到获取检测对象统计的请求")
        
        # 从请求参数中获取用户名
        username = request.args.get('username', 'unknown_user')
        session_id = f"camera_{username}"
        
        print(f"[DEBUG] 用户: {username}, 会话ID: {session_id}")
        
        # 检查是否有检测数据
        if session_id not in camera_detection_data:
            print(f"[DEBUG] 没有找到摄像头检测数据")
            return jsonify({
                'success': True,
                'fatigue_level': 'none',
                'detection_info': {
                    'total_detections': 0,
                    'closed_eyes_count': 0,
                    'open_mouth_count': 0,
                    'open_eyes_count': 0,
                    'closed_mouth_count': 0,
                    'fatigue_indicators': [],
                    'detection_active': False,
                    'total_seconds': 0
                }
            })
        
        # 获取累计统计数据
        stats = camera_detection_data[session_id]
        current_time = time.time()
        total_seconds = current_time - stats['start_time']
        
        # 计算疲劳等级
        fatigue_level = _analyze_fatigue_level_camera(
            total_seconds,
            stats['closed_eyes_count'],
            stats['open_mouth_count']
        )
        
        # 生成疲劳指标
        fatigue_indicators = []
        if stats['closed_eyes_count'] > 0:
            fatigue_indicators.append({'type': 'closed_eyes', 'count': stats['closed_eyes_count']})
        if stats['open_mouth_count'] > 0:
            fatigue_indicators.append({'type': 'open_mouth', 'count': stats['open_mouth_count']})
        
        detection_info = {
            'total_detections': stats['total_detections'],
            'closed_eyes_count': stats['closed_eyes_count'],
            'open_mouth_count': stats['open_mouth_count'],
            'open_eyes_count': stats['open_eyes_count'],
            'closed_mouth_count': stats['closed_mouth_count'],
            'fatigue_indicators': fatigue_indicators,
            'detection_active': True,
            'total_seconds': round(total_seconds, 1)
        }
        
        print(f"[DEBUG] 返回摄像头检测统计:")
        print(f"[DEBUG] 疲劳级别: {fatigue_level}")
        print(f"[DEBUG] 检测信息: {detection_info}")
        
        # === 语音播报逻辑 ===
        if fatigue_level in ['high', 'severe']:
            now = time.time()
            if now - last_play_time > 5:  # 5秒内只播报一次
                try:
                    os.system('start /b "" "D:/study/Junior-year/shixun/ffmpeg-n7.1-latest-win64-gpl-7.1/ffmpeg-n7.1-latest-win64-gpl-7.1/bin/ffplay.exe" -autoexit -nodisp "D:/study/Junior-year/final4/fp/fp/fp/fpbackend/请勿疲劳驾驶.mp3"')
                    last_play_time = now
                    print("[DEBUG] 语音播报成功")
                except Exception as e:
                    print(f"[ERROR] 语音播报失败: {e}")
        # === 语音播报逻辑结束 ===
        
        return jsonify({
            'success': True,
            'fatigue_level': fatigue_level,
            'detection_info': detection_info
        })
        
    except Exception as e:
        print(f"[ERROR] 获取检测对象统计失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取统计失败: {str(e)}',
            'fatigue_level': 'none',
            'detection_info': {
                'total_detections': 0,
                'closed_eyes_count': 0,
                'open_mouth_count': 0,
                'open_eyes_count': 0,
                'closed_mouth_count': 0,
                'fatigue_indicators': [],
                'detection_active': False,
                'total_seconds': 0
            }
        })

@detect_api.route('/api/get_video_stats', methods=['GET'])
def get_video_stats():
    """获取视频检测统计信息（用于实时显示）"""
    try:
        print("[DEBUG] get_video_stats API 被调用")
        
        session_id = request.args.get('session_id', '')
        if not session_id:
            print("[DEBUG] 缺少session_id参数")
            return jsonify({
                'success': False,
                'message': '缺少session_id参数'
            }), 400
        
        # 如果没有对应的视频检测会话，返回默认值
        if session_id not in video_detection_data:
            print(f"[DEBUG] 没有找到视频检测会话: {session_id}")
            return jsonify({
                'success': True,
                'fatigue_level': 'low',
                'detection_info': {
                    'closed_eyes_count': 0,
                    'open_mouth_count': 0,
                    'open_eyes_count': 0,
                    'closed_mouth_count': 0,
                    'total_detections': 0,
                    'fatigue_indicators': [],
                    'detection_active': False,
                    'total_frames': 0,
                    'frames_with_detections': 0
                }
            })
        
        # 使用视频统计函数
        stats = _get_video_detection_stats(session_id)
        
        print(f"[DEBUG] 视频检测统计: {stats}")
        
        return jsonify({
            'success': True,
            'fatigue_level': stats['fatigue_level'],
            'detection_info': {
                'closed_eyes_count': stats['closed_eyes_count'],
                'open_mouth_count': stats['open_mouth_count'],
                'open_eyes_count': stats['open_eyes_count'],
                'closed_mouth_count': stats['closed_mouth_count'],
                'total_detections': stats['total_detections'],
                'fatigue_indicators': stats['fatigue_indicators'],
                'detection_active': stats['detection_active'],
                'total_frames': stats['total_frames'],
                'frames_with_detections': stats['frames_with_detections']
            }
        })
    except Exception as e:
        print(f"[ERROR] get_video_stats 失败: {e}")
        return jsonify({
            'success': False,
            'fatigue_level': 'low',
            'detection_info': {
                'closed_eyes_count': 0,
                'open_mouth_count': 0,
                'open_eyes_count': 0,
                'closed_mouth_count': 0,
                'total_detections': 0,
                'fatigue_indicators': [],
                'detection_active': False,
                'total_frames': 0,
                'frames_with_detections': 0
            }
        })

@detect_api.route('/api/models', methods=['GET'])
def get_models():
    """获取所有可用的模型列表"""
    try:
        models = []
        
        # 查找模型文件的多个路径
        model_paths = [
            'models/uploads',
            os.path.join('..', 'fpdemo', 'models', 'uploads'),
            '.'
        ]
        
        for model_dir in model_paths:
            if os.path.exists(model_dir):
                for filename in os.listdir(model_dir):
                    if filename.endswith('.pt'):
                        file_path = os.path.join(model_dir, filename)
                        file_size = os.path.getsize(file_path)
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        models.append({
                            'name': filename,
                            'size': file_size,
                            'size_mb': round(file_size / (1024 * 1024), 2),
                            'upload_time': file_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'path': file_path,
                            'timestamp': os.path.getmtime(file_path)
                        })
        
        # 去重并按时间排序
        unique_models = {}
        for model in models:
            if model['name'] not in unique_models:
                unique_models[model['name']] = model
        
        models = list(unique_models.values())
        models.sort(key=lambda x: x['timestamp'])
        
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        print(f"获取模型列表失败: {e}")
        return jsonify({'success': False, 'message': '获取模型列表失败'})

@detect_api.route('/api/models/current', methods=['GET'])
def get_current_model():
    """获取当前使用的模型"""
    # 这里可以从配置文件或数据库获取
    return jsonify({
        'success': True,
        'current_model': 'best.pt'  # 默认模型
    })

@detect_api.route('/api/models/current', methods=['POST'])
def set_current_model():
    """设置当前使用的模型"""
    try:
        data = request.get_json()
        model_name = data.get('model_name', '')
        
        if not model_name:
            return jsonify({'success': False, 'message': '模型名称不能为空'})
        
        # 这里可以保存到配置文件或数据库
        return jsonify({
            'success': True,
            'message': '模型切换成功',
            'current_model': model_name
        })
    except Exception as e:
        return jsonify({'success': False, 'message': '设置当前模型失败'})


@detect_api.route('/api/camera/save_recording', methods=['POST'])
def save_camera_recording():
    """保存摄像头录制视频"""
    try:
        data = request.get_json()
        username = data.get('username', 'camera_user')
        session_id = f"camera_{username}"
        
        print(f"[DEBUG] 保存摄像头录制，用户: {username}, 会话ID: {session_id}")
        
        # 检查是否有检测数据，如果没有则创建默认数据
        if session_id not in camera_detection_data:
            print(f"[DEBUG] 没有找到检测数据，创建默认数据")
            camera_detection_data[session_id] = {
                'closed_eyes_count': 0,
                'open_mouth_count': 0,
                'open_eyes_count': 0,
                'closed_mouth_count': 0,
                'total_detections': 0,
                'start_time': time.time() - 10,  # 假设运行了10秒
                'detection_active': False
            }
        
        # 获取统计数据
        stats = camera_detection_data[session_id]
        current_time = time.time()
        total_seconds = current_time - stats['start_time']
        
        # 计算疲劳等级
        fatigue_level = _analyze_fatigue_level_camera(
            total_seconds,
            stats['closed_eyes_count'],
            stats['open_mouth_count']
        )
        
        # 生成详细信息
        details = {
            'session_id': session_id,
            'total_seconds': round(total_seconds, 1),
            'closed_eyes_count': stats['closed_eyes_count'],
            'open_mouth_count': stats['open_mouth_count'],
            'open_eyes_count': stats['open_eyes_count'],
            'closed_mouth_count': stats['closed_mouth_count'],
            'total_detections': stats['total_detections'],
            'closed_eyes_per_sec': round(stats['closed_eyes_count'] / total_seconds, 2) if total_seconds > 0 else 0,
            'open_mouth_per_sec': round(stats['open_mouth_count'] / total_seconds, 2) if total_seconds > 0 else 0
        }
        
        # 保存检测结果到数据库
        _save_detection_result(
            username,
            'camera',
            'completed',
            fatigue_level,
            f'摄像头检测完成，时长: {total_seconds:.1f}秒',
            0.9,
            total_seconds
        )
        
        # 清理检测数据
        if session_id in camera_detection_data:
            del camera_detection_data[session_id]
        if session_id in real_time_detection_results:
            del real_time_detection_results[session_id]
        
        return jsonify({
            'success': True,
            'message': '录制保存成功',
            'fatigue_level': fatigue_level,
            'details': details
        })
        
    except Exception as e:
        print(f"[ERROR] 保存摄像头录制失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'保存失败: {str(e)}'
        })

@detect_api.route('/api/camera/reset', methods=['POST'])
def reset_camera_detection():
    try:
        data = request.get_json()
        username = data.get('username', 'camera_user')
        session_id = f"camera_{username}"
        print(f"[DEBUG] 重置摄像头检测数据，用户: {username}, 会话ID: {session_id}")
        stats = camera_detection_data.get(session_id)
        if stats:
            start_time = stats.get('start_time', None)
            if start_time:
                duration = time.time() - start_time
            else:
                duration = stats.get('total_seconds', 0)
            closed_eyes_count = stats.get('closed_eyes_count', 0)
            open_mouth_count = stats.get('open_mouth_count', 0)
            open_eyes_count = stats.get('open_eyes_count', 0)
            closed_mouth_count = stats.get('closed_mouth_count', 0)
            total_detections = stats.get('total_detections', 0)
            fatigue_level = _analyze_fatigue_level_camera(
                duration,
                closed_eyes_count,
                open_mouth_count
            )
            details = json.dumps({
                'closed_eyes_count': closed_eyes_count,
                'open_mouth_count': open_mouth_count,
                'open_eyes_count': open_eyes_count,
                'closed_mouth_count': closed_mouth_count,
                'total_detections': total_detections,
                'duration': duration
            }, ensure_ascii=False)
            print(f"[DEBUG] reset_camera_detection: 即将保存检测结果 username={username}, fatigue_level={fatigue_level}, duration={duration}")
            save_result = _save_detection_result(
                username=username,
                method='camera',
                result='completed',
                fatigue_level=fatigue_level,
                details=details,
                confidence=0.0,
                duration=duration
            )
            if save_result:
                print(f"[DEBUG] reset_camera_detection: 检测结果成功写入数据库，用户: {username}, 疲劳等级: {fatigue_level}, 时长: {duration}")
            else:
                print(f"[ERROR] reset_camera_detection: 检测结果写入数据库失败，用户: {username}")
        else:
            print(f"[DEBUG] reset_camera_detection: 未找到检测统计数据，未保存记录")
        # 实际清理和重置数据
        print(f"[DEBUG] 开始清理和重置数据，会话ID: {session_id}")

        # 1. 重置摄像头检测数据
        if session_id in camera_detection_data:
            print(f"[DEBUG] 重置前的数据: {camera_detection_data[session_id]}")
            camera_detection_data[session_id] = {
                'closed_eyes_count': 0,
                'open_mouth_count': 0,
                'open_eyes_count': 0,
                'closed_mouth_count': 0,
                'total_detections': 0,
                'start_time': time.time(),
                'last_update': time.time()
            }
            print(f"[DEBUG] 重置后的数据: {camera_detection_data[session_id]}")

        # 2. 重置实时检测数据
        if session_id in real_time_detection_data:
            print(f"[DEBUG] 清理实时检测数据: {session_id}")
            real_time_detection_data[session_id] = {
                'closed_eyes': deque(maxlen=200),
                'open_mouth': deque(maxlen=200),
                'open_eyes': deque(maxlen=200),
                'closed_mouth': deque(maxlen=200),
                'last_update': 0.0,
                'last_fatigue_check': 0.0,
                'current_fatigue_level': 'low',
                'detection_active': False
            }

        # 3. 清理实时检测结果
        if session_id in real_time_detection_results:
            print(f"[DEBUG] 清理实时检测结果: {session_id}")
            del real_time_detection_results[session_id]

        # 4. 清理疲劳记录
        if session_id in fatigue_records:
            print(f"[DEBUG] 清理疲劳记录: {session_id}")
            fatigue_records[session_id] = []

        # 5. 重置摄像头开始时间
        if session_id in camera_start_times:
            print(f"[DEBUG] 重置摄像头开始时间: {session_id}")
            camera_start_times[session_id] = time.time()

        print(f"[DEBUG] 数据重置完成，会话ID: {session_id}")

        return jsonify({
            'success': True,
            'message': '检测数据已重置，相当于重新启动检测',
            'restart_detection': True,  # 告诉前端需要重新启动检测流
            'reset_data': {
                'closed_eyes_count': 0,
                'open_mouth_count': 0,
                'open_eyes_count': 0,
                'closed_mouth_count': 0,
                'total_detections': 0,
                'total_seconds': 0,
                'start_time': time.time()
            }
        })
    except Exception as e:
        print(f"[ERROR] 重置摄像头检测数据失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'重置失败: {str(e)}'
        })

@detect_api.route('/api/camera/upload_recording', methods=['POST'])
def upload_camera_recording():
    """上传摄像头录制的视频文件"""
    try:
        print(f"[DEBUG] 收到摄像头录制上传请求")
        
        # 获取上传的文件
        video_file = request.files.get('video_file')
        if not video_file:
            return jsonify({
                'success': False,
                'message': '没有找到视频文件'
            })
        
        # 获取其他参数
        username = request.form.get('username', 'camera_user')
        detection_stats_str = request.form.get('detection_stats', '{}')
        fatigue_level = request.form.get('fatigue_level', 'none')
        
        try:
            detection_stats = json.loads(detection_stats_str)
        except:
            detection_stats = {}
        
        print(f"[DEBUG] 用户: {username}, 疲劳等级: {fatigue_level}")
        print(f"[DEBUG] 文件: {video_file.filename}, 大小: {video_file.content_length}")
        
        # 创建上传目录
        upload_dir = os.path.join('static', 'uploads', 'recordings')
        os.makedirs(upload_dir, exist_ok=True)
        
        # 生成安全的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"camera_recording_{username}_{timestamp}.webm"
        file_path = os.path.join(upload_dir, safe_filename)
        
        # 保存文件
        video_file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        print(f"[DEBUG] 文件已保存: {file_path}, 大小: {file_size} bytes")
        
        # 保存检测结果到数据库
        details = {
            'filename': safe_filename,
            'file_path': file_path,
            'file_size': file_size,
            'detection_stats': detection_stats,
            'recording_type': 'camera_live'
        }
        
        _save_detection_result(
            username,
            'camera_recording',
            'completed',
            fatigue_level,
            f'摄像头录制保存完成，文件: {safe_filename}',
            0.9,
            detection_stats.get('total_seconds', 0)
        )
        
        return jsonify({
            'success': True,
            'message': '录制上传成功',
            'fatigue_level': fatigue_level,
            'details': {
                'filename': safe_filename,
                'file_size': file_size,
                'total_detections': detection_stats.get('total_detections', 0),
                'total_seconds': detection_stats.get('total_seconds', 0)
            }
        })
        
    except Exception as e:
        print(f"[ERROR] 上传摄像头录制失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'上传失败: {str(e)}'
        })

 