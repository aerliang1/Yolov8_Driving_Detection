# 独立管理员系统

这是一个完全独立的管理员系统，从原疲劳驾驶检测系统中分离出来，包含完整的前后端功能，运行在独立的端口上。

## 🏗️ 系统架构

```
admin_system/
├── app.py                      # 主应用程序（Flask后端）
├── start.py                    # 启动脚本
├── requirements.txt            # Python依赖
├── Dockerfile                  # Docker镜像构建文件
├── docker-compose.yml          # Docker编排文件
├── README.md                   # 说明文档
├── templates/                  # 前端模板
│   ├── common/
│   │   └── base.html          # 基础模板
│   └── admin/
│       ├── dashboard.html      # 控制台
│       ├── permissions.html    # 权限管理
│       ├── records.html        # 检测记录
│       ├── system_log.html     # 系统日志
│       └── profile.html        # 个人信息
└── static/                     # 静态资源
    ├── css/
    │   └── layui.css          # LayUI样式
    ├── js/
    └── layui.js               # LayUI脚本
```

## 🚀 快速启动

### 方法一：使用启动脚本（推荐）
```bash
cd admin_system
python start.py
```

### 方法二：直接启动
```bash
cd admin_system
python app.py
```

### 方法三：使用Docker
```bash
cd admin_system
docker-compose up -d
```

## 📋 系统要求

- Python 3.6+
- MySQL数据库
- 网络连接（用于加载LayUI资源）

## 🔧 配置说明

### 数据库配置
在 `app.py` 中修改数据库配置：

```python
DB_CONFIG = {
    'host': 'localhost',        # 数据库主机
    'port': 3306,              # 数据库端口
    'user': 'root',            # 数据库用户名
    'password': '你的密码',     # 数据库密码
    'database': 'demo01',      # 数据库名
    'charset': 'utf8mb4'
}
```

### Docker配置
在 `docker-compose.yml` 中修改环境变量：

```yaml
environment:
  - DB_HOST=mysql
  - DB_PORT=3306
  - DB_USER=root
  - DB_PASSWORD=你的密码
  - DB_NAME=你的数据库名
```

## 🌐 访问地址

启动成功后，访问以下地址：

- **管理员系统**: http://127.0.0.1:8080
- **控制台**: http://127.0.0.1:8080/admin/dashboard
- **权限管理**: http://127.0.0.1:8080/admin/permissions
- **检测记录**: http://127.0.0.1:8080/admin/records
- **系统日志**: http://127.0.0.1:8080/admin/system_log
- **个人信息**: http://127.0.0.1:8080/admin/profile
- **健康检查**: http://127.0.0.1:8080/health

### Docker访问地址
- **管理员系统**: http://127.0.0.1:8080
- **phpMyAdmin**: http://127.0.0.1:8081

## 📊 功能特性

### 仪表盘统计
- 总用户数统计
- 在线驾驶员数量
- 今日检测次数
- 疲劳警报数量
- 系统资源监控（CPU、内存、磁盘）

### 用户管理
- 查看用户列表
- 搜索用户
- 添加新用户
- 修改用户角色（admin/monitor/driver）
- 删除用户

### 检测记录管理
- 查看所有检测记录
- 按结果筛选（正常/疲劳）
- 按驾驶员筛选
- 实时数据更新

### 系统日志
- 查看系统操作日志
- 按角色筛选日志
- 按操作类型筛选
- 操作历史追踪

### 最近活动
- 显示最近的系统活动
- 自动刷新（每30秒）
- 活动详情展示

## 🔌 API接口

### 统计数据
- `GET /api/dashboard-stats` - 获取仪表盘统计

### 用户管理
- `GET /api/users` - 获取用户列表
- `POST /api/users` - 添加用户
- `PUT /api/users/{id}/role` - 修改用户角色
- `DELETE /api/users/{id}` - 删除用户

### 检测记录
- `GET /api/records` - 获取检测记录

### 系统日志
- `GET /api/logs` - 获取系统日志
- `GET /api/recent-activities` - 获取最近活动

### 其他
- `GET /api/drivers` - 获取驾驶员列表
- `GET /api/profile` - 获取管理员信息
- `GET /health` - 健康检查

## 🐳 Docker部署

### 构建镜像
```bash
docker build -t admin-system .
```

### 使用docker-compose
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

### 数据持久化
- MySQL数据存储在Docker卷中
- 日志文件映射到本地 `./logs` 目录

## 🔒 安全说明

1. **数据库密码**: 请确保数据库密码安全，不要在代码中硬编码
2. **网络访问**: 默认监听所有网络接口(0.0.0.0)，生产环境请修改为具体IP
3. **CORS设置**: 当前允许所有来源访问，生产环境请限制来源
4. **Docker安全**: 使用非root用户运行应用

## 🐛 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查数据库配置是否正确
   - 确认数据库服务是否启动
   - 验证用户名密码是否正确

2. **端口被占用**
   - 修改 `app.py` 中的端口号
   - 或者停止占用8080端口的其他服务

3. **依赖包缺失**
   - 运行 `pip install -r requirements.txt`
   - 或使用 `start.py` 自动安装

4. **页面样式异常**
   - 检查网络连接，确保能访问LayUI CDN
   - 或下载LayUI到本地使用

5. **Docker问题**
   - 检查Docker和docker-compose是否正确安装
   - 确认端口没有被占用
   - 查看容器日志: `docker-compose logs`

### 日志查看

服务器启动后会在控制台显示详细日志，包括：
- 数据库连接状态
- API请求日志
- 错误信息

Docker部署时日志存储在 `./logs` 目录中。

## 🔄 与原系统的关系

这个独立管理员系统：
- ✅ 完全独立运行，不依赖原系统
- ✅ 使用相同的数据库，数据保持同步
- ✅ 独立的端口(8080)，不冲突
- ✅ 完整的前后端功能
- ✅ 可以与原系统同时运行
- ✅ 支持Docker部署

## 📝 更新日志

### v1.0.0
- 初始版本
- 完整的管理员功能
- 独立部署支持
- Docker支持

## 🤝 技术支持

如有问题，请检查：
1. 数据库连接配置
2. Python依赖包安装
3. 网络连接状态
4. 控制台错误日志
5. Docker容器状态（如使用Docker）
