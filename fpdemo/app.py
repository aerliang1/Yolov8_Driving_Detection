from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify, Response, stream_with_context
import requests
import os
import sys
from datetime import datetime, timezone, timedelta

# 设置控制台编码，解决Windows中文显示问题
if sys.platform.startswith('win'):
    try:
        import locale
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except:
        pass


# 后端API地址
BACKEND_URL = 'http://127.0.0.1:5001'
# BACKEND_URL ='http://10.236.12.10:5001'

app = Flask(__name__)
app.secret_key = 'fatigue_detection_system'  # 用于加密会话数据
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # 上传文件存储路径
app.config['MODEL_FOLDER'] = 'models/uploads'  # 模型文件存储路径
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MODEL_FOLDER'], exist_ok=True)


# 角色名称映射
def get_role_name(role):
    role_names = {
        'admin': '管理员',
        'monitor': '监控人员',
        'driver': '驾驶员'
    }
    return role_names.get(role, role)


# 通用的消息提示页面，增加按钮控制和自动跳转功能
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
        <title>操作结果</title>
        <link rel="stylesheet" href="/static/css/layui.css">
    </head>
    <body>
        <div style="width: 500px; margin: 100px auto; text-align: center;">
            <div class="layui-card">
                <div class="layui-card-header">操作结果</div>
                <div class="layui-card-body">
                    <p class="layui-text layui-text-center" style="font-size: 18px; margin: 20px 0;">{message}</p>
                    {button_html}
                </div>
            </div>
        </div>
        <script src="/static/layui.js"></script>
        {auto_redirect}
    </body>
    </html>
    '''


# 登录验证装饰器
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('hello_login'))
        return f(*args, **kwargs)

    return decorated_function


# 角色验证装饰器
def role_required(roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                return show_message("权限不足", "/admin", show_button=True, button_text="返回主界面")
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# 系统日志记录功能（转发到后端）
def log_action(username, role, action):
    try:
        requests.post(f'{BACKEND_URL}/api/admin/logs',
            json={'username': username, 'role': role, 'action': action},
            timeout=2
        )
    except Exception as e:
        print(f"Failed to log action: {e}")


@app.route('/')
def hello_index():

    return redirect('/login')


@app.route('/register', methods=["GET", "POST"])
def hello_register():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'driver')  # 默认角色为驾驶员

        try:
            # 调用后端API注册用户
            response = requests.post(f'{BACKEND_URL}/api/auth/register', json={
                'username': username,
                'password': password,
                'role': role
            })

            result = response.json()
            if result.get('success'):
                # 记录注册日志
                log_action(username, role, "用户注册")
                return show_message("注册成功", "/login", show_button=True, button_text="前往登录")
            else:
                return show_message(result.get('message', "注册失败"), "/register", show_button=True, button_text="返回注册")
        except Exception as e:
            print(f"Registration error: {e}")
            return show_message("系统错误，请稍后重试", "/register", show_button=True, button_text="返回注册")
    else:
        return render_template('register.html')


@app.route('/login', methods=["GET", "POST"])
def hello_login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            # 调用后端API登录，添加超时设置
            response = requests.post(f'{BACKEND_URL}/api/auth/login',
                json={'username': username, 'password': password},
                timeout=3  # 3秒超时
            )

            result = response.json()
            if result.get('success'):
                user_data = result.get('data', {})
                session['username'] = username  # 记录登录状态
                session['role'] = user_data.get('role')  # 记录用户角色
                session['register_time'] = user_data.get('register_time')  # 记录注册时间
                # 获取东八区当前时间，保持原格式
                beijing_tz = timezone(timedelta(hours=8))
                beijing_time = datetime.now(beijing_tz)
                session['last_login'] = beijing_time.strftime("%a, %d %b %Y %H:%M:%S GMT")  # 东八区时间，保持原格式
                # 清除之前的上传记录
                session.pop('uploaded_filename', None)

                # 记录登录日志
                role = user_data.get('role')
                log_action(username, role, "用户登录")

                # 根据角色跳转到不同的主界面
                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif role == 'monitor':
                    return redirect(url_for('monitor_dashboard'))
                else:  # driver
                    return redirect(url_for('driver_dashboard'))
            else:
                return show_message(result.get('message', "登录失败"), "/login", show_button=True, button_text="返回登录")
        except requests.exceptions.Timeout:
            print("登录超时：后端API响应超时")
            return show_message("登录超时，请检查后端服务是否正常", "/login", show_button=True, button_text="返回登录")
        except requests.exceptions.ConnectionError:
            print("登录错误：无法连接到后端API")
            return show_message("无法连接到后端服务，请确保后端已启动", "/login", show_button=True, button_text="返回登录")
        except Exception as e:
            print(f"Login error: {e}")
            return show_message("系统错误，请稍后重试", "/login", show_button=True, button_text="返回登录")
    else:
        return render_template('login.html')

@app.route('/driver/dashboard')
@login_required
@role_required(['driver'])  # 只有驾驶员可以访问
def driver_dashboard():
    resp = make_response(
        render_template('driver/dashboard.html', username=session['username'], role=session['role'], role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/monitor/dashboard')
@login_required
@role_required(['monitor'])  # 只有监控人员可以访问
def monitor_dashboard():
    resp = make_response(
        render_template('monitor/dashboard.html', username=session['username'], role=session['role'], role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/driver/records')
@login_required
@role_required(['driver'])
def driver_records():
    """驾驶员检测记录页面 - 通过后端API获取数据"""
    try:
        username = session['username']

        # 调用后端API获取记录
        response = requests.get(
            f'{BACKEND_URL}/api/driver/records',
            params={'username': username},
            timeout=10
        )

        records = []
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                records = result.get('data', [])
            else:
                print(f"后端API返回错误: {result.get('message', '未知错误')}")
        else:
            print(f"后端API请求失败，状态码: {response.status_code}")

    except Exception as e:
        print(f"获取驾驶员记录失败: {e}")
        records = []

    # 渲染页面
    resp = make_response(
        render_template('driver/records.html',
                       username=session['username'],
                       role=session['role'],
                       role_name=get_role_name(session['role']),
                       records=records))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/driver/profile')
@login_required
@role_required(['driver'])
def driver_profile():
    # 简化用户信息获取
    profile_data = {
        'username': session['username'],
        'role': session['role'],
        'role_name': get_role_name(session['role']),
        'register_time': session['register_time'],
        'last_login': session['last_login']
    }

    resp = make_response(
        render_template('driver/profile.html',
            username=session['username'],
            role=session['role'],
            role_name=get_role_name(session['role']),
            user_info=profile_data
        ))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# 监控人员页面路由
@app.route('/monitor/records')
@login_required
@role_required(['monitor'])
def monitor_records():
    # 直接从后端获取检测记录
    records = []
    try:
        response = requests.get(f'{BACKEND_URL}/api/monitor/records', timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                records = result.get('data', [])
                # 处理时间格式，确保timestamp是字符串
                for record in records:
                    if record.get('timestamp'):
                        # 如果timestamp是datetime对象，转换为字符串
                        if hasattr(record['timestamp'], 'strftime'):
                            record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                        # 如果已经是字符串，保持原样
                        elif not isinstance(record['timestamp'], str):
                            record['timestamp'] = str(record['timestamp'])
                print(f"[DEBUG] Retrieved {len(records)} records from monitor")
            else:
                print(f"[DEBUG] Backend returned error: {result.get('message')}")
        else:
            print(f"[DEBUG] Backend returned status code: {response.status_code}")
    except Exception as e:
        print(f"[DEBUG] Failed to retrieve records: {e}")
    
    resp = make_response(
        render_template('monitor/records.html', 
                       username=session['username'], 
                       role=session['role'], 
                       role_name=get_role_name(session['role']),
                       records=records))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/monitor/profile')
@login_required
@role_required(['monitor'])
def monitor_profile():
    # 简化用户信息获取
    profile_data = {
        'username': session['username'],
        'role': session['role'],
        'role_name': get_role_name(session['role']),
        'register_time': session['register_time'],
        'last_login': session['last_login']
    }

    resp = make_response(
        render_template('monitor/profile.html',
            username=session['username'],
            role=session['role'],
            role_name=get_role_name(session['role']),
            user_info=profile_data
        ))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# 管理员页面路由
@app.route('/admin/dashboard')
@login_required
@role_required(['admin'])
def admin_dashboard():
    resp = make_response(
        render_template('admin/dashboard.html', username=session['username'], role=session['role'], role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/admin/permissions')
@login_required
@role_required(['admin'])
def admin_permissions():
    resp = make_response(
        render_template('admin/permissions.html', username=session['username'], role=session['role'], role_name=get_role_name(session['role'])))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/admin/records')
@login_required
@role_required(['admin'])
def admin_records():
    # 直接从后端获取检测记录
    records = []
    try:
        response = requests.get(f'{BACKEND_URL}/api/admin/records', timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                records = result.get('data', [])
                # 处理时间格式，确保timestamp是字符串
                for record in records:
                    if record.get('timestamp'):
                        # 如果timestamp是datetime对象，转换为字符串
                        if hasattr(record['timestamp'], 'strftime'):
                            record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                        # 如果已经是字符串，保持原样
                        elif not isinstance(record['timestamp'], str):
                            record['timestamp'] = str(record['timestamp'])
                print(f"[DEBUG] Retrieved {len(records)} records from admin")
            else:
                print(f"[DEBUG] Backend returned error: {result.get('message')}")
        else:
            print(f"[DEBUG] Backend returned status code: {response.status_code}")
    except Exception as e:
        print(f"[DEBUG] Failed to retrieve records: {e}")
    
    resp = make_response(
        render_template('admin/records.html', 
                       username=session['username'], 
                       role=session['role'], 
                       role_name=get_role_name(session['role']),
                       records=records))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/admin/profile')
@login_required
@role_required(['admin'])
def admin_profile():
    # 简化用户信息获取
    profile_data = {
        'username': session['username'],
        'role': session['role'],
        'role_name': get_role_name(session['role']),
        'register_time': session['register_time'],
        'last_login': session['last_login']
    }

    resp = make_response(
        render_template('admin/profile.html',
            username=session['username'],
            role=session['role'],
            role_name=get_role_name(session['role']),
            user_info=profile_data
        ))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/upload', methods=['POST'])
@login_required  # 登录验证
def upload_file():
    if 'file' not in request.files:
        log_action(session['username'], session['role'], "用户上传文件时未选择文件")
        return show_message("未选择文件", "/admin", show_button=True, button_text="返回主界面")

    file = request.files['file']
    if file.filename == '':
        log_action(session['username'], session['role'], "用户上传文件时未选择文件")
        return show_message("未选择文件", "/admin", show_button=True, button_text="返回主界面")

    if file:
        # 保存文件
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        # 保存上传的文件名到会话中
        session['uploaded_filename'] = file.filename

        log_action(session['username'], session['role'], f"用户上传文件: {file.filename}")

        # 直接返回JSON响应，让前端处理图片显示
        return 'success'

    log_action(session['username'], session['role'], "用户上传文件失败")
    return show_message("文件上传失败", "/admin", show_button=True, button_text="返回主界面")


@app.route('/logout')
def logout():
    # 清除会话中的用户名和上传的文件名
    username = session.pop('username', None)
    role = session.pop('role', None)
    uploaded_filename = session.pop('uploaded_filename', None)
    if username and role:
        log_action(username, role, "用户退出登录")

    # 设置响应头禁止浏览器缓存
    resp = redirect(url_for('hello_login'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/admin/system_log')
@login_required
@role_required(['admin'])  # 只有管理员可以查看系统日志
def system_log():
    # 直接从本地数据库读取日志
    from test import con_my_sql
    sql = "SELECT * FROM system_log ORDER BY timestamp DESC LIMIT 200"
    cursor = con_my_sql(sql)
    logs = cursor.fetchall() if cursor and not isinstance(cursor, tuple) else []

    def get_role_badge(role):
        badges = {
            'driver': '<span class="layui-badge layui-bg-blue">驾驶员</span>',
            'monitor': '<span class="layui-badge layui-bg-green">监控人员</span>',
            'admin': '<span class="layui-badge layui-bg-red">管理员</span>'
        }
        return badges.get(role, '<span class="layui-badge">未知</span>')

    def get_action_badge(action):
        badges = {
            'login': '<span class="layui-badge layui-bg-green">登录</span>',
            'logout': '<span class="layui-badge layui-bg-gray">退出</span>',
            'detection': '<span class="layui-badge layui-bg-blue">检测</span>',
            'upload': '<span class="layui-badge layui-bg-orange">上传</span>',
            'delete': '<span class="layui-badge layui-bg-red">删除</span>',
            'modify': '<span class="layui-badge layui-bg-cyan">修改</span>'
        }
        return badges.get(action, '<span class="layui-badge">' + action + '</span>')

    resp = make_response(render_template('admin/system_log.html',
        logs=logs,
        username=session['username'],
        role=session['role'],
        role_name=get_role_name(session['role']),
        getRoleBadge=get_role_badge,
        getActionBadge=get_action_badge
    ))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/log_camera_action', methods=['POST'])
@login_required
def log_camera_action():
    action = request.form.get('action')
    username = session['username']
    role = session['role']
    if action == 'open':
        log_action(username, role, "摄像头已打开")
    elif action == 'close':
        log_action(username, role, "摄像头已关闭")
    return 'success'

# ===================== 新版通用检测接口 =====================
# 前端转发到后端检测

@app.route('/api/detect', methods=['POST'])
@login_required
def detect_file():
    """通用检测接口：转发到后端进行检测"""
    try:
        # 构建转发到后端的请求
        files = {}
        if 'file' in request.files:
            uploaded_file = request.files['file']
            print(f"[Frontend DEBUG] Received filename: {uploaded_file.filename}")
            print(f"[Frontend DEBUG] File MIME type: {uploaded_file.mimetype}")
            
            # 确保文件指针在开始位置
            uploaded_file.seek(0)
            
            # 重新创建文件对象，保持原始文件名和MIME类型
            files['file'] = (uploaded_file.filename, uploaded_file.stream, uploaded_file.mimetype)
        
        data = {
            'model': request.form.get('model', ''),
            'url': request.form.get('url', ''),
            'username': session.get('username', ''),
            'user_role': session.get('role', '')
        }
        
        print(f"[Frontend DEBUG] Forward data: {data}")
        
        # 转发到后端
        response = requests.post(
            f'{BACKEND_URL}/api/detect',
            files=files,
            data=data,
            timeout=60  # 增加超时时间，因为检测可能需要较长时间
        )
        
        # 记录检测日志
        username = session.get('username', 'unknown_user')
        role = session.get('role', 'unknown_role')
        
        # 获取文件名用于日志记录
        filename_for_log = ''
        if 'file' in request.files and request.files['file'].filename:
            filename_for_log = request.files['file'].filename
            method = 'Image detection' if filename_for_log.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')) else 'Video detection'
        else:
            filename_for_log = data.get('url', '')
            method = 'URL detection'
        
        log_action(username, role, f"{method}: {filename_for_log}")
        
        # 处理后端响应
        result = response.json()
        
        # 如果检测成功，转换图片路径
        if result.get('success') and result.get('output_path'):
            backend_path = result['output_path']
            print(f"[Frontend DEBUG] Backend returned path: {backend_path}")
            
            # 将后端的相对路径转换为后端服务器的完整URL
            if backend_path.startswith('/static/'):
                # 后端返回的是 /static/... 格式的路径
                backend_url = f"{BACKEND_URL}{backend_path}"
                result['output_path'] = backend_url
                print(f"[Frontend DEBUG] Converted URL: {backend_url}")
            elif not backend_path.startswith('http'):
                # 如果不是完整URL，添加后端服务器前缀
                if backend_path.startswith('/'):
                    backend_url = f"{BACKEND_URL}{backend_path}"
                else:
                    backend_url = f"{BACKEND_URL}/{backend_path}"
                result['output_path'] = backend_url
                print(f"[Frontend DEBUG] Converted URL: {backend_url}")
        
        return jsonify(result)
        
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'Detection timeout, please try again later'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': 'Cannot connect to backend detection service'}), 500
    except Exception as e:
        print(f"Detection forwarding failed: {e}")
        return jsonify({'success': False, 'message': f'Detection failed: {e}'}), 500


# 个人信息相关API接口
# 删除旧的API接口，使用新的转发接口


# 删除旧的API接口，使用新的转发接口


# ==================== API转发接口 ====================

# 检测记录API接口
@app.route('/api/driver/records', methods=['GET'])
@login_required
@role_required(['driver'])
def proxy_driver_records():
    try:
        print(f"[DEBUG] Forwarding driver records request to: {BACKEND_URL}/api/driver/records")
        response = requests.get(f'{BACKEND_URL}/api/driver/records', timeout=10)
        print(f"[DEBUG] Backend response status: {response.status_code}")
        print(f"[DEBUG] Backend response content: {response.text[:500]}...")
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            print(f"[DEBUG] Backend returned error status: {response.status_code}")
            return jsonify({'success': False, 'message': f'Backend service error: {response.status_code}'}), 500
    except requests.exceptions.ConnectionError:
        print(f"[DEBUG] Cannot connect to backend service: {BACKEND_URL}")
        return jsonify({'success': False, 'message': 'Cannot connect to backend service, please ensure backend is running'}), 500
    except Exception as e:
        print(f"[DEBUG] Failed to get driver records: {e}")
        return jsonify({'success': False, 'message': f'Failed to get detection records: {e}'}), 500

@app.route('/api/monitor/records', methods=['GET'])
@login_required
@role_required(['monitor'])
def proxy_monitor_records():
    try:
        response = requests.get(f'{BACKEND_URL}/api/monitor/records')
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get monitor records: {e}")
        return jsonify({'success': False, 'message': 'Failed to get detection records'}), 500

@app.route('/api/admin/records', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_admin_records():
    try:
        params = {
            'result': request.args.get('result', ''),
            'driver_id': request.args.get('driver_id', ''),
            'date_range': request.args.get('date_range', '')
        }
        response = requests.get(f'{BACKEND_URL}/api/admin/records', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get admin records: {e}")
        return jsonify({'success': False, 'message': 'Failed to get detection records'}), 500


# 删除记录的API接口（只有管理员和监控人员可以删除）

@app.route('/api/monitor/records/<int:record_id>', methods=['DELETE'])
@login_required
@role_required(['monitor'])
def proxy_delete_monitor_record(record_id):
    try:
        response = requests.delete(f'{BACKEND_URL}/api/monitor/records/{record_id}')
        result = response.json()
        if result.get('success'):
            log_action(session['username'], session['role'], f"Delete detection record: ID {record_id}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to delete monitor record: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete record'}), 500

@app.route('/api/admin/records/<int:record_id>', methods=['PUT'])
@login_required
@role_required(['admin'])
def proxy_update_admin_record(record_id):
    try:
        data = request.get_json()
        response = requests.put(f'{BACKEND_URL}/api/admin/records/{record_id}', json=data)
        result = response.json()
        if result.get('success'):
            log_action(session['username'], session['role'], f"Update detection record: ID {record_id}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to update admin record: {e}")
        return jsonify({'success': False, 'message': 'Failed to update record'}), 500

@app.route('/api/admin/records/<int:record_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def proxy_delete_admin_record(record_id):
    try:
        response = requests.delete(f'{BACKEND_URL}/api/admin/records/{record_id}')
        result = response.json()
        if result.get('success'):
            log_action(session['username'], session['role'], f"Delete detection record: ID {record_id}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to delete admin record: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete record'}), 500

# 管理员API接口 - 获取用户列表
@app.route('/api/admin/users', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_get_users():
    try:
        search = request.args.get('search', '').strip()
        params = {'search': search} if search else {}

        response = requests.get(f'{BACKEND_URL}/api/admin/users', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get user list: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get user list'
        }), 500

# 管理员API接口 - 添加用户
@app.route('/api/admin/users', methods=['POST'])
@login_required
@role_required(['admin'])
def proxy_add_user():
    try:
        data = request.get_json()
        data['admin_username'] = session['username']

        response = requests.post(f'{BACKEND_URL}/api/admin/users', json=data)
        result = response.json()
        if result.get('success'):
            # 记录添加用户日志
            log_action(session['username'], session['role'], f"Add user: {data.get('username', 'unknown')}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to add user: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to add user'
        }), 500

# 管理员API接口 - 修改用户角色
@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@login_required
@role_required(['admin'])
def proxy_update_user_role(user_id):
    try:
        data = request.get_json()
        data['admin_username'] = session['username']

        response = requests.put(f'{BACKEND_URL}/api/admin/users/{user_id}/role', json=data)
        result = response.json()
        if result.get('success'):
            # 记录修改用户角色日志
            log_action(session['username'], session['role'], f"Modify user role: User ID {user_id} -> {data.get('role', 'unknown')}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to modify user role: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to modify user role'
        }), 500

# 管理员API接口 - 删除用户
@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def proxy_delete_user(user_id):
    try:
        params = {'admin_username': session['username']}

        response = requests.delete(f'{BACKEND_URL}/api/admin/users/{user_id}', params=params)
        result = response.json()
        if result.get('success'):
            # 记录删除用户日志
            log_action(session['username'], session['role'], f"Delete user: User ID {user_id}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to delete user: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete user'
        }), 500


# 用户信息API接口
@app.route('/api/user/profile', methods=['GET'])
@login_required
def proxy_get_user_profile():
    try:
        username = session['username']
        params = {'username': username}
        response = requests.get(f'{BACKEND_URL}/api/user/profile', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get user info: {e}")
        return jsonify({'success': False, 'message': 'Failed to get user info'}), 500

# 修改密码API接口
@app.route('/api/user/change-password', methods=['POST'])
@login_required
def proxy_change_password():
    try:
        username = session['username']
        data = request.form.to_dict()
        data['username'] = username
        response = requests.post(f'{BACKEND_URL}/api/user/change-password', data=data)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to change password: {e}")
        return jsonify({'success': False, 'message': 'Failed to change password'}), 500

# 修改用户名API接口
@app.route('/api/user/change-username', methods=['POST'])
@login_required
def proxy_change_username():
    try:
        current_username = session['username']
        data = request.form.to_dict()
        data['username'] = current_username
        response = requests.post(f'{BACKEND_URL}/api/user/change-username', data=data)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to change username: {e}")
        return jsonify({'success': False, 'message': 'Failed to change username'}), 500

# 获取修改状态API接口
@app.route('/api/user/modify-status', methods=['GET'])
@login_required
def proxy_get_modify_status():
    try:
        username = session['username']
        params = {'username': username}
        response = requests.get(f'{BACKEND_URL}/api/user/modify-status', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get modify status: {e}")
        return jsonify({'success': False, 'message': 'Failed to get modify status'}), 500

# 获取修改历史API接口
@app.route('/api/user/modify-history', methods=['GET'])
@login_required
def proxy_get_modify_history():
    try:
        username = session['username']
        params = {'username': username}
        response = requests.get(f'{BACKEND_URL}/api/user/modify-history', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get modify history: {e}")
        return jsonify({'success': False, 'message': 'Failed to get modify history'}), 500


# 系统日志API接口
@app.route('/api/admin/logs', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_get_logs():
    try:
        role = request.args.get('role', '').strip()
        action = request.args.get('action', '').strip()
        date_range = request.args.get('date_range', '').strip()

        params = {}
        if role:
            params['role'] = role
        if action:
            params['action'] = action
        if date_range:
            params['date_range'] = date_range

        response = requests.get(f'{BACKEND_URL}/api/admin/logs', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get system logs: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get system logs'
        }), 500


@app.route('/api/admin/logs/clear', methods=['DELETE'])
@login_required
@role_required(['admin'])
def proxy_clear_logs():
    try:
        response = requests.delete(f'{BACKEND_URL}/api/admin/logs/clear')
        result = response.json()
        if result.get('success'):
            # 记录清空日志操作
            log_action(session['username'], session['role'], "清空系统日志")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to clear system logs: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to clear system logs'
        }), 500


@app.route('/api/admin/logs/export', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_export_logs():
    try:
        role = request.args.get('role', '').strip()
        action = request.args.get('action', '').strip()
        date_range = request.args.get('date_range', '').strip()

        params = {}
        if role:
            params['role'] = role
        if action:
            params['action'] = action
        if date_range:
            params['date_range'] = date_range

        response = requests.get(f'{BACKEND_URL}/api/admin/logs/export', params=params)

        # 如果是CSV文件，直接返回
        if response.headers.get('content-type') == 'text/csv':
            return Response(
                response.content,
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; filename=system_logs.csv'
                }
            )

        result = response.json()
        if result.get('success'):
            # 记录导出日志操作
            log_action(session['username'], session['role'], "导出系统日志")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to export system logs: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to export system logs'
        }), 500

# 系统日志API接口
@app.route('/api/admin/system_log', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_get_system_logs():
    try:
        limit = request.args.get('limit', 100, type=int)
        params = {'limit': limit}

        response = requests.get(f'{BACKEND_URL}/api/logs', params=params)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get system logs: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get system logs'
        }), 500

# 模型管理相关API（转发到后端）
@app.route('/api/models', methods=['GET'])
@login_required
def get_models():
    """获取所有可用的模型列表（转发到后端）"""
    try:
        response = requests.get(f'{BACKEND_URL}/api/models', timeout=10)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get model list: {e}")
        return jsonify({'success': False, 'message': 'Failed to get model list'})


@app.route('/api/models/upload', methods=['POST'])
@login_required
@role_required(['admin', 'monitor'])  # 管理员和监控人员可以上传模型
def upload_model():
    """上传模型文件"""
    try:
        if 'model_file' not in request.files:
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        file = request.files['model_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        if not file.filename.endswith('.pt'):
            return jsonify({'success': False, 'message': '只支持.pt格式的模型文件'})
        
        # 检查文件大小（限制为500MB）
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        file.seek(0)  # 重置到文件开头
        
        if file_size > 500 * 1024 * 1024:  # 500MB
            return jsonify({'success': False, 'message': '文件大小不能超过500MB'})
        
        # 保存文件
        filename = file.filename
        file_path = os.path.join(app.config['MODEL_FOLDER'], filename)
        
        # 如果文件已存在，添加时间戳
        if os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}{ext}"
            file_path = os.path.join(app.config['MODEL_FOLDER'], filename)
        
        file.save(file_path)
        
        # 记录日志
        log_action(session['username'], session['role'], f'上传模型文件: {filename}')
        
        return jsonify({
            'success': True,
            'message': '模型上传成功',
            'filename': filename
        })
        
    except Exception as e:
        print(f"Failed to upload model: {e}")
        return jsonify({'success': False, 'message': 'Failed to upload model'})


@app.route('/api/models/<filename>', methods=['DELETE'])
@login_required
@role_required(['admin'])  # 只有管理员可以删除模型
def delete_model(filename):
    """删除模型文件"""
    try:
        file_path = os.path.join(app.config['MODEL_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '模型文件不存在'})
        
        # 安全检查：确保文件在模型文件夹内
        if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['MODEL_FOLDER'])):
            return jsonify({'success': False, 'message': '无效的文件路径'})
        
        os.remove(file_path)
        
        # 记录日志
        log_action(session['username'], session['role'], f'删除模型文件: {filename}')
        
        return jsonify({
            'success': True,
            'message': '模型删除成功'
        })
        
    except Exception as e:
        print(f"Failed to delete model: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete model'})


@app.route('/api/models/current', methods=['GET'])
@login_required
def get_current_model():
    """获取当前使用的模型（转发到后端）"""
    try:
        response = requests.get(f'{BACKEND_URL}/api/models/current', timeout=10)
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get current model: {e}")
        return jsonify({'success': False, 'message': 'Failed to get current model'})


@app.route('/api/models/current', methods=['POST'])
@login_required
@role_required(['admin', 'monitor', 'driver'])  # 管理员、监控、驾驶员都可以选择模型
def set_current_model():
    """设置当前使用的模型（转发到后端）"""
    try:
        data = request.get_json()
        
        # 转发到后端
        response = requests.post(
            f'{BACKEND_URL}/api/models/current',
            json=data,
            timeout=10
        )
        
        result = response.json()
        if result.get('success'):
        # 记录日志
            model_name = data.get('model_name', '')
        log_action(session['username'], session['role'], f'切换模型: {model_name}')
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Failed to set current model: {e}")
        return jsonify({'success': False, 'message': 'Failed to set current model'})

# 获取检测到的目标信息（转发到后端）
@app.route('/api/get_detected_objects', methods=['GET'])
@login_required
def get_detected_objects():
    """转发获取检测结果请求到后端"""
    try:
        # 获取前端传递的用户名参数，如果没有则使用当前会话用户名
        username = request.args.get('username', session.get('username', 'unknown_user'))
        
        # 转发请求到后端，传递用户名参数
        response = requests.get(
            f'{BACKEND_URL}/api/get_detected_objects',
            params={'username': username},
            timeout=10
        )
        
        result = response.json()
        
        # 记录检测统计获取日志（只在成功且有数据时记录，避免刷屏）
        if result.get('success') and result.get('detection_info', {}).get('total_detections', 0) > 0:
            detection_info = result.get('detection_info', {})
            log_action(session['username'], session['role'], 
                f'获取实时检测统计: 总检测{detection_info.get("total_detections", 0)}次')
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Failed to get detection stats: {e}")
        return jsonify({
            'success': False,
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

# 仪表板统计数据API接口
@app.route('/api/admin/dashboard-stats', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_get_dashboard_stats():
    """获取仪表板统计数据"""
    try:
        response = requests.get(f'{BACKEND_URL}/api/admin/dashboard-stats')
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get dashboard stats: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get dashboard stats'
        }), 500
# ===== 实时视频文件流 =====
@app.route('/api/stream/video')
@login_required
def stream_video():
    """转发视频流请求到后端"""
    video_path = request.args.get('path', '')
    model_name = request.args.get('model', '')
    
    try:
        # 转发到后端
        response = requests.get(
            f'{BACKEND_URL}/api/stream/video',
            params={'path': video_path, 'model': model_name},
            stream=True,
            timeout=30
        )
        
        return Response(
            stream_with_context(response.iter_content(chunk_size=1024)),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        return f'stream error: {e}', 500


# ===== 实时摄像头流 =====
@app.route('/api/stream/camera')
@login_required
def stream_camera():
    """转发摄像头流请求到后端"""
    index = request.args.get('index', '0')
    model_name = request.args.get('model', '')
    username = request.args.get('username', '')  # 获取username参数
    
    try:
        # 转发到后端，包含username参数
        response = requests.get(
            f'{BACKEND_URL}/api/stream/camera',
            params={
                'index': index, 
                'model': model_name,
                'username': username  # 添加username参数
            },
            stream=True,
            timeout=30
        )
        
        return Response(
            stream_with_context(response.iter_content(chunk_size=1024)),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        return f'stream error: {e}', 500



# ===== 摄像头录制相关API =====
@app.route('/api/camera/save_recording', methods=['POST'])
@login_required
def save_camera_recording():
    """转发摄像头录制保存请求到后端"""
    try:
        # 检查是否有文件上传
        if 'video' not in request.files:
            return jsonify({'success': False, 'message': '没有视频文件'})
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        # 准备转发到后端的文件
        files = {'video': (file.filename, file.stream, file.content_type)}
        data = {
            'username': session['username']
        }
        
        # 转发到后端
        response = requests.post(
            f'{BACKEND_URL}/api/camera/save_recording',
            files=files,
            data=data,
            timeout=30
        )
        
        result = response.json()
        if result.get('success'):
            # 记录日志
            log_action(session['username'], session['role'], '保存摄像头录制')
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Failed to save recording: {e}")
        return jsonify({'success': False, 'message': 'Failed to save recording'})


@app.route('/api/camera/reset', methods=['POST'])
@login_required
def reset_camera_data():
    """转发摄像头数据重置请求到后端"""
    try:
        data = {
            'username': session['username']
        }
        
        # 转发到后端
        response = requests.post(
            f'{BACKEND_URL}/api/camera/reset',
            json=data,
            timeout=10
        )
        
        result = response.json()
        if result.get('success'):
            # 记录日志
            log_action(session['username'], session['role'], '重置摄像头检测数据')
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Failed to reset data: {e}")
        return jsonify({'success': False, 'message': 'Failed to reset data'})

@app.route('/api/admin/recent-activities', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_get_recent_activities():
    """获取最近活动"""
    try:
        response = requests.get(f'{BACKEND_URL}/api/admin/recent-activities')
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get recent activities: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get recent activities'
        }), 500

# 公告API接口
@app.route('/api/admin/announcements', methods=['GET'])
@login_required
@role_required(['admin'])
def proxy_get_announcements():
    """获取公告列表"""
    try:
        response = requests.get(f'{BACKEND_URL}/api/admin/announcements')
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get announcements: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get announcements'
        }), 500

@app.route('/api/admin/announcements', methods=['POST'])
@login_required
@role_required(['admin'])
def proxy_add_announcement():
    """发布公告"""
    try:
        data = request.get_json()
        print(f"Received announcement data: {data}")
        
        # 检查数据格式
        if not data:
            print("Error: No JSON data received")
            return jsonify({
                'success': False,
                'message': 'No data received'
            }), 400
        
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        
        if not title or not content:
            print(f"Error: Title or content is empty - title: '{title}', content: '{content}'")
            return jsonify({
                'success': False,
                'message': 'Title and content cannot be empty'
            }), 400
        
        print(f"Preparing to send to backend: title='{title}', content='{content}'")
        
        # 发送到后端
        response = requests.post(
            f'{BACKEND_URL}/api/admin/announcements', 
            json={'title': title, 'content': content},
            timeout=10
        )
        
        print(f"Backend response status code: {response.status_code}")
        print(f"Backend response content: {response.text}")
        
        return jsonify(response.json())
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {e}")
        return jsonify({
            'success': False,
            'message': 'Cannot connect to backend service, please ensure backend is running'
        }), 500
    except requests.exceptions.Timeout as e:
        print(f"Request timeout: {e}")
        return jsonify({
            'success': False,
            'message': 'Request timeout, please try again later'
        }), 500
    except Exception as e:
        print(f"Failed to add announcement: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to add announcement: {str(e)}'
        }), 500

# 驾驶员公告API接口
@app.route('/api/driver/announcements', methods=['GET'])
@login_required
@role_required(['driver'])
def proxy_driver_get_announcements():
    """驾驶员获取公告列表"""
    try:
        response = requests.get(f'{BACKEND_URL}/api/admin/announcements')
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to get driver announcements: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get announcements'
        }), 500

@app.route('/api/admin/announcements/<int:announcement_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def proxy_delete_announcement(announcement_id):
    """删除公告"""
    try:
        response = requests.delete(f'{BACKEND_URL}/api/admin/announcements/{announcement_id}')
        return jsonify(response.json())
    except Exception as e:
        print(f"Failed to delete announcement: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete announcement'
        }), 500


@app.route('/api/monitor/records/<int:record_id>/fatigue-level', methods=['PUT'])
@login_required
@role_required(['monitor'])
def proxy_update_monitor_record(record_id):
    try:
        data = request.get_json()
        response = requests.put(f'{BACKEND_URL}/api/monitor/records/{record_id}/fatigue-level', json=data)
        result = response.json()
        if result.get('success'):
            log_action(session['username'], session['role'], f"修改检测记录: ID {record_id}")
        return jsonify(result)
    except Exception as e:
        print(f"Failed to update monitor record: {e}")
        return jsonify({'success': False, 'message': 'Failed to update record'}), 500


# 健康检查路由
@app.route('/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'service': 'fatigue-detection-frontend',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0'
    })

if __name__ == '__main__':
    # Docker容器中需要绑定到0.0.0.0，否则外部无法访问
    app.run(host='0.0.0.0', port=5000, debug=True)
