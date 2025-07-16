#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
疲劳检测系统后端服务
基于YOLOv8的图片和视频检测功能
"""

import os
import sys
from flask import Flask, render_template, request, redirect, session, send_from_directory
from flask_cors import CORS

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 导入API蓝图
from app.views.admin_api import admin_api
from app.views.monitor_api import monitor_api
from app.views.driver_api import driver_api
from app.views.common_api import common_api
from app.views.detect_api import detect_api

# 创建Flask应用
app = Flask(__name__)

# 配置应用
app.config['SECRET_KEY'] = 'fatigue_detection_backend_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB最大文件上传

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'results'), exist_ok=True)

# 启用CORS
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/static/*": {"origins": "*"}})

# 注册蓝图
app.register_blueprint(admin_api)
app.register_blueprint(monitor_api)
app.register_blueprint(driver_api)
app.register_blueprint(common_api)
app.register_blueprint(detect_api)

# 静态文件服务
@app.route('/static/<path:filename>')
def static_files(filename):
    """提供静态文件访问"""
    try:
        static_dir = os.path.join(current_dir, 'static')
        return send_from_directory(static_dir, filename)
    except Exception as e:
        print(f"静态文件访问失败: {e}")
        return {'error': 'File not found'}, 404

# 健康检查接口
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return {'status': 'healthy', 'service': 'fatigue_detection_backend'}

# 根路径重定向
@app.route('/', methods=['GET'])
def root():
    """根路径重定向到健康检查"""
    return redirect('/health')

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return {'error': 'Not Found', 'message': '接口不存在'}, 404

@app.errorhandler(500)
def internal_error(error):
    return {'error': 'Internal Server Error', 'message': '服务器内部错误'}, 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 疲劳检测系统后端服务启动中...")
    print("=" * 60)
    print("📁 项目路径:", current_dir)
    print("🌐 服务地址: http://127.0.0.1:5001")
    print("🔍 健康检查: http://127.0.0.1:5001/health")
    print("📤 上传目录:", app.config['UPLOAD_FOLDER'])
    print("🖼️  静态文件: http://127.0.0.1:5001/static/")
    print("=" * 60)
    print("💡 提示: 按 Ctrl+C 停止服务")
    print("=" * 60)
    
    try:
        # 启动服务
        app.run(
            debug=True,           # 调试模式
            host='0.0.0.0',      # 监听所有网络接口
            port=5001,           # 端口号
            threaded=True        # 启用多线程
        )
    except KeyboardInterrupt:
        print("\n�� 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)