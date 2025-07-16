import os
import cv2
import numpy as np
from ultralytics import YOLO
from PIL import Image
import tempfile
import uuid
from datetime import datetime
import string
import time
from collections import defaultdict, deque

# 全局变量 - 语音播报控制
tplay = 0  # 语音上次播放时间


class YOLODetector:
    def __init__(self, model_path=None):
        """
        初始化YOLO检测器
        :param model_path: 模型路径，如果为None则使用默认模型
        """
        try:
            if model_path and os.path.exists(model_path):
                self.model = YOLO(model_path)
            else:
                # 使用默认的YOLOv8n模型
                self.model = YOLO('best.pt')
            print("YOLO模型加载成功")

            # 疲劳检测相关 - 修复数据结构类型
            self.fatigue_counters = defaultdict(lambda: {
                'closed_eyes': deque(maxlen=100),
                'open_mouth': deque(maxlen=100),
                'last_check': 0.0,
                'fatigue_level': 'low'
            })

        except Exception as e:
            print(f"YOLO模型加载失败: {e}")
            self.model = None

    def secure_filename(self, filename):
        """
        安全文件名处理，移除或替换无效字符
        """
        if filename is None:
            return None

        # 替换空格为下划线
        for sep in os.path.sep, os.path.altsep:
            if sep:
                filename = filename.replace(sep, '_')

        # 去掉前后空格
        filename = filename.strip()
        # 去掉前面可能存在的.
        filename = filename.lstrip('.')

        # 将不合理路径修改
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        cleaned_filename = ''.join(c for c in filename if c in valid_chars)
        return cleaned_filename

    def analyze_fatigue_level(self, results, session_id='default'):
        """
        分析疲劳程度 - 根据用户标签：0=闭眼，1=闭嘴，2=睁眼，3=张嘴
        :param results: YOLO检测结果
        :param session_id: 会话ID，用于区分不同的检测会话
        :return: 疲劳程度 ('low', 'medium', 'high')
        """
        current_time = time.time()
        counter = self.fatigue_counters[session_id]

        closed_eyes_count = 0
        open_mouth_count = 0

        # 分析YOLO检测结果 - 根据用户的标签定义
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])

                    # 根据用户提供的标签映射：
                    # 0=闭眼，1=闭嘴，2=睁眼，3=张嘴
                    if cls == 0 and conf > 0.5:  # 闭眼
                        closed_eyes_count += 1
                    elif cls == 3 and conf > 0.5:  # 张嘴（疲劳指标）
                        open_mouth_count += 1
                    # cls == 1 (闭嘴) 和 cls == 2 (睁眼) 是正常状态，不计入疲劳指标

        # 记录检测结果
        counter['closed_eyes'].append((current_time, closed_eyes_count))
        counter['open_mouth'].append((current_time, open_mouth_count))

        # 每10秒进行一次疲劳程度判断
        if current_time - counter['last_check'] >= 10:
            counter['last_check'] = current_time

            # 统计最近10秒的疲劳指标
            recent_time = current_time - 10
            recent_closed_eyes = sum(count for timestamp, count in counter['closed_eyes'] if timestamp > recent_time)
            recent_open_mouth = sum(count for timestamp, count in counter['open_mouth'] if timestamp > recent_time)

            # 疲劳程度判断逻辑 - 三个等级：低等、中等、高等
            if recent_closed_eyes >= 5 or recent_open_mouth >= 3:
                counter['fatigue_level'] = 'high'  # 高等疲劳
            elif recent_closed_eyes >= 3 or recent_open_mouth >= 2:
                counter['fatigue_level'] = 'medium'  # 中等疲劳
            else:
                counter['fatigue_level'] = 'low'  # 低等疲劳（正常）

        return counter['fatigue_level']

    def get_fatigue_statistics(self, session_id='default'):
        """
        获取疲劳统计信息
        """
        counter = self.fatigue_counters[session_id]
        current_time = time.time()
        recent_time = current_time - 60  # 最近1分钟

        recent_closed_eyes = len([1 for timestamp, count in counter['closed_eyes']
                                  if timestamp > recent_time and count > 0])
        recent_open_mouth = len([1 for timestamp, count in counter['open_mouth']
                                 if timestamp > recent_time and count > 0])

        return {
            'fatigue_level': counter['fatigue_level'],
            'closed_eyes_count': recent_closed_eyes,
            'open_mouth_count': recent_open_mouth,
            'last_check': counter['last_check']
        }

    def detect_image(self, image_path, output_dir='static/uploads', session_id=None):
        """
        检测图片
        :param image_path: 输入图片路径
        :param output_dir: 输出目录
        :param session_id: 会话ID
        :return: 检测结果字典
        """
        if not self.model:
            return {'success': False, 'message': '模型未加载'}

        if session_id is None:
            session_id = str(uuid.uuid4())

        try:
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 生成输出文件名
            filename = self.secure_filename(os.path.basename(image_path))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"detected_{timestamp}_{filename}"
            output_path = os.path.join(output_dir, output_filename)

            # 执行检测
            results = self.model(image_path)

            # 分析疲劳程度
            fatigue_level = self.analyze_fatigue_level(results, session_id)

            # 保存检测结果图片
            for result in results:
                # 绘制检测结果
                annotated_img = result.plot()
                cv2.imwrite(output_path, annotated_img)

            # 分析检测结果
            detection_info = self._analyze_detection_results(results)
            detection_info['fatigue_level'] = fatigue_level

            return {
                'success': True,
                'output_path': output_path,
                'detection_info': detection_info,
                'fatigue_level': fatigue_level,
                'session_id': session_id,
                'message': '图片检测完成'
            }

        except Exception as e:
            return {'success': False, 'message': f'图片检测失败: {e}'}

    def detect_video(self, video_path, output_dir='static/uploads', session_id=None):
        """
        检测视频
        :param video_path: 输入视频路径
        :param output_dir: 输出目录
        :param session_id: 会话ID
        :return: 检测结果字典
        """
        if not self.model:
            return {'success': False, 'message': '模型未加载'}

        if session_id is None:
            session_id = str(uuid.uuid4())

        try:
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 生成输出文件名
            filename = self.secure_filename(os.path.basename(video_path))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"detected_{timestamp}_{filename}"
            output_path = os.path.join(output_dir, output_filename)

            # 执行视频检测（逐帧处理）
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # 视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            frame_results = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 检测当前帧
                results = self.model(frame, verbose=False)
                frame_results.extend(results)

                # 分析疲劳程度
                fatigue_level = self.analyze_fatigue_level(results, session_id)

                # 绘制检测结果
                annotated_frame = results[0].plot()

                # 添加疲劳状态信息
                cv2.putText(annotated_frame, f"Fatigue: {fatigue_level}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                out.write(annotated_frame)

            cap.release()
            out.release()

            # 分析检测结果
            detection_info = self._analyze_video_results(frame_results)
            final_fatigue_level = self.fatigue_counters[session_id]['fatigue_level']
            detection_info['fatigue_level'] = final_fatigue_level

            return {
                'success': True,
                'output_path': output_path,
                'detection_info': detection_info,
                'fatigue_level': final_fatigue_level,
                'session_id': session_id,
                'message': '视频检测完成'
            }

        except Exception as e:
            return {'success': False, 'message': f'视频检测失败: {e}'}

    def detect_frame(self, frame, session_id='default'):
        """
        检测单帧图像
        :param frame: numpy数组格式的图像帧
        :param session_id: 会话ID
        :return: 检测结果
        """
        if not self.model:
            return None
        try:
            results = self.model(frame, verbose=False)
            # 分析疲劳程度
            fatigue_level = self.analyze_fatigue_level(results, session_id)
            print(f"[DEBUG] 当前疲劳等级: {fatigue_level}")  # 添加调试信息
            # 仅保留疲劳等级分析和检测结果返回，删除音频播报相关逻辑
            return {
                'results': results[0] if results else None,
                'fatigue_level': fatigue_level,
                'session_id': session_id
            }
        except Exception as e:
            print(f"帧检测失败: {e}")
            return None

    def _analyze_detection_results(self, results):
        """
        分析检测结果 - 根据用户标签定义
        """
        detection_info = {
            'total_objects': 0,
            'objects_detected': [],
            'fatigue_indicators': []
        }

        # 标签映射：0=闭眼，1=闭嘴，2=睁眼，3=张嘴
        class_names = {0: 'closed_eyes', 1: 'closed_mouth', 2: 'open_eyes', 3: 'open_mouth'}

        for result in results:
            if result.boxes is not None:
                boxes = result.boxes
                detection_info['total_objects'] = len(boxes)

                for box in boxes:
                    # 获取类别和置信度
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = class_names.get(cls, f'class_{cls}')

                    detection_info['objects_detected'].append({
                        'class': class_name,
                        'confidence': conf,
                        'class_id': cls
                    })

                    # 疲劳指标：闭眼(0)和张嘴(3)
                    if cls in [0, 3]:  # 闭眼或张嘴
                        detection_info['fatigue_indicators'].append({
                            'type': class_name,
                            'confidence': conf
                        })

        return detection_info

    def _analyze_video_results(self, results):
        """
        分析视频检测结果
        """
        detection_info = {
            'total_frames': len(results),
            'frames_with_detections': 0,
            'total_objects': 0,
            'fatigue_indicators': []
        }

        for result in results:
            if result.boxes is not None and len(result.boxes) > 0:
                detection_info['frames_with_detections'] += 1
                detection_info['total_objects'] += len(result.boxes)

                # 分析每一帧的检测结果
                frame_info = self._analyze_detection_results([result])
                detection_info['fatigue_indicators'].extend(frame_info['fatigue_indicators'])

        return detection_info


# 全局检测器实例
detector = YOLODetector() 