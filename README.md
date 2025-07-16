# 疲劳驾驶检测系统

一个基于深度学习的疲劳驾驶检测系统，包含前端界面、后端API服务和独立管理员系统。

## 📋 项目概述

本系统通过摄像头实时监测驾驶员的面部特征，识别疲劳驾驶行为，并提供完整的管理和监控功能。

### 🏗️ 系统架构

```
疲劳驾驶检测系统/
├── fpdemo/           # 前端界面 (Flask + HTML/CSS/JS)
├── fpbackend/        # 后端API服务 (Flask + MySQL)
├── admin_system/     # 独立管理员系统 (Flask + 完整前后端)
└── README.md         # 项目说明文档
```

## 🚀 功能特性

### 核心功能
- **实时疲劳检测**: 基于面部特征的疲劳状态识别
- **多种检测方式**: 支持摄像头实时检测和图片上传检测
- **智能预警系统**: 多级疲劳预警机制
- **数据统计分析**: 完整的检测数据统计和分析

### 管理功能
- **用户权限管理**: 支持管理员、监控员、驾驶员三级权限
- **检测记录管理**: 完整的检测历史记录和导出功能
- **系统日志监控**: 详细的操作日志和系统监控
- **公告通知系统**: 系统公告发布和管理

## 📁 项目结构

### fpdemo (前端界面)
```
fpdemo/
├── app.py                 # Flask应用主文件
├── templates/             # HTML模板文件
│   ├── index.html        # 主页面
│   ├── login.html        # 登录页面
│   ├── register.html     # 注册页面
│   ├── detection.html    # 检测页面
│   └── admin/            # 管理员页面
├── static/               # 静态资源
│   ├── css/             # 样式文件
│   ├── js/              # JavaScript文件
│   └── images/          # 图片资源
└── requirements.txt      # Python依赖
```

### fpbackend (后端API服务)
```
fpbackend/
├── app/
│   ├── __init__.py
│   ├── models/          # 数据模型
│   ├── views/           # API视图
│   │   ├── auth_api.py  # 认证API
│   │   ├── detect_api.py # 检测API
│   │   └── admin_api.py # 管理API
│   └── utils/           # 工具类
│       ├── database.py  # 数据库工具
│       └── detection.py # 检测算法
├── config.py            # 配置文件
├── run.py              # 启动文件
└── requirements.txt     # Python依赖
```

### admin_system (独立管理员系统)
```
admin_system/
├── app.py              # 完整的Flask应用
├── templates/          # 管理员界面模板
│   ├── login.html     # 登录页面
│   ├── register.html  # 注册页面
│   ├── common/        # 公共模板
│   └── admin/         # 管理页面
│       ├── dashboard.html    # 仪表盘
│       ├── permissions.html  # 权限管理
│       ├── records.html     # 检测记录
│       ├── system_log.html  # 系统日志
│       └── profile.html     # 个人信息
├── static/            # 静态资源
├── init_database.py   # 数据库初始化
├── Dockerfile         # Docker配置
├── docker-compose.yml # Docker编排
└── requirements.txt   # Python依赖
```

## 🛠️ 技术栈

### 后端技术
- **Python 3.12+**: 主要开发语言
- **Flask**: Web框架
- **MySQL**: 数据库
- **PyMySQL**: 数据库连接
- **OpenCV**: 图像处理
- **TensorFlow/PyTorch**: 深度学习框架

### 前端技术
- **HTML5/CSS3**: 页面结构和样式
- **JavaScript**: 交互逻辑
- **Layui**: UI框架
- **jQuery**: JavaScript库
- **Chart.js**: 数据可视化

### 部署技术
- **Docker**: 容器化部署
- **Nginx**: 反向代理
- **Gunicorn**: WSGI服务器

## 📦 安装部署

### 环境要求
- Python 3.8+
- MySQL 5.7+
- Node.js (可选，用于前端构建)

### 1. 克隆项目
```bash
git clone <repository-url>
cd fp
```

### 2. 数据库配置
```sql
-- 创建数据库
CREATE DATABASE demo01 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 后端部署
```bash
cd fpbackend
pip install -r requirements.txt
python run.py
```

### 4. 前端部署
```bash
cd fpdemo
pip install -r requirements.txt
python app.py
```

### 5. 独立管理员系统部署
```bash
cd admin_system
pip install -r requirements.txt
#直接进入
python app.py
```

## 🌐 访问地址

### 本地部署
- **前端界面**: http://localhost:5000
- **后端API**: http://localhost:5001
- **管理员系统**: http://localhost:8080

### 云服务器部署
- **前端界面**: http://your-server-ip:5000
- **后端API**: http://your-server-ip:5001
- **管理员系统**: http://your-server-ip:8080

### 公网数据库部署
- **前端界面**: http://your-domain.com:5000 (连接公网数据库)
- **后端API**: http://your-domain.com:5001 (连接公网数据库)
- **管理员系统**: http://your-domain.com:8080 (连接公网数据库)

## 🔧 配置说明

### 数据库配置

#### 本地数据库配置
在各个模块中修改数据库连接配置：
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',
    'database': 'demo01',  # 或 'test'
    'charset': 'utf8mb4'
}
```

#### 公网数据库配置
支持连接公网MySQL数据库（如阿里云RDS、腾讯云CDB等）：
```python
DB_CONFIG = {
    'host': 'your-db-host.mysql.rds.aliyuncs.com',  # 公网数据库地址
    'port': 3306,
    'user': 'your_username',
    'password': 'your_password',
    'database': 'demo01',
    'charset': 'utf8mb4'
}
```

**公网数据库优势**：
- ✅ 多服务器共享数据
- ✅ 数据备份和恢复
- ✅ 高可用性保障
- ✅ 专业运维支持

### 端口配置
- 前端默认端口: 5000
- 后端默认端口: 5001
- 管理员系统默认端口: 8080

可在各模块的启动文件中修改端口配置。

## 👥 用户角色

### 管理员 (admin)
- 完整的系统管理权限
- 用户管理和权限分配
- 系统配置和维护
- 数据导出和备份

### 监控员 (monitor)
- 查看检测记录
- 监控系统状态
- 生成统计报告

### 驾驶员 (driver)
- 进行疲劳检测
- 查看个人检测历史
- 接收预警通知

## 🐳 Docker部署

### 独立管理员系统Docker部署
```bash
cd admin_system
# 构建镜像
docker build -t admin-system .
# 运行容器
docker run -d -p 8080:8080 admin-system
```

### 使用Docker Compose（本地）
```bash
cd admin_system
docker-compose up -d
```

### Docker镜像上传到仓库
```bash
# 构建镜像
docker build -t your-username/admin-system:latest .

# 登录Docker Hub
docker login

# 推送镜像
docker push your-username/admin-system:latest

# 在云服务器上拉取使用
docker pull your-username/admin-system:latest
```

## 📊 API文档

### 认证API
- `POST /api/login` - 用户登录
- `POST /api/register` - 用户注册
- `POST /api/logout` - 用户登出

### 检测API
- `POST /api/detect` - 疲劳检测
- `GET /api/records` - 获取检测记录
- `DELETE /api/records/{id}` - 删除检测记录

### 管理API
- `GET /api/users` - 获取用户列表
- `POST /api/users` - 创建用户
- `PUT /api/users/{id}/role` - 修改用户角色
- `DELETE /api/users/{id}` - 删除用户

## 🔒 安全特性

- **身份认证**: Session-based认证机制
- **权限控制**: 基于角色的访问控制(RBAC)
- **数据加密**: 敏感数据加密存储
- **SQL注入防护**: 参数化查询防止SQL注入
- **XSS防护**: 输入输出过滤防止XSS攻击

## 📈 监控和日志

- **系统日志**: 完整的操作日志记录
- **性能监控**: 系统资源使用监控
- **错误追踪**: 详细的错误日志和堆栈跟踪
- **数据统计**: 检测数据统计和分析

## 🚀 部署到云服务器

### 方案一：传统部署

#### 1. 服务器准备
```bash
# 安装Python和MySQL
sudo apt update
sudo apt install python3 python3-pip mysql-server

# 安装Nginx (可选)
sudo apt install nginx
```

#### 2. 端口映射配置
```bash
# 开放端口
sudo ufw allow 5000
sudo ufw allow 5001
sudo ufw allow 8080
```

#### 3. 进程管理
使用supervisor或systemd管理应用进程：
```bash
# 安装supervisor
sudo apt install supervisor

# 配置服务
sudo vim /etc/supervisor/conf.d/admin-system.conf
```

### 方案二：XShell远程 + Docker部署（推荐）

#### 1. 准备工作
- 购买云服务器（阿里云、腾讯云、华为云等）
- 获取服务器公网IP和SSH登录信息
- 安装XShell或其他SSH客户端

#### 2. XShell远程连接
```bash
# 使用XShell连接到云服务器
ssh username@your-server-ip
# 或使用密钥文件
ssh -i your-key.pem username@your-server-ip
```

#### 3. 服务器环境准备
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker
```

#### 4. 部署独立管理员系统

**方法A：直接拉取Docker镜像**
```bash
# 拉取预构建的镜像（如果已上传到Docker Hub）
docker pull your-username/admin-system:latest

# 运行容器
docker run -d \
  --name admin-system \
  -p 8080:8080 \
  -e DB_HOST=your-db-host \
  -e DB_USER=your-db-user \
  -e DB_PASSWORD=your-db-password \
  -e DB_NAME=demo01 \
  your-username/admin-system:latest
```

**方法B：上传代码并构建**
```bash
# 创建项目目录
mkdir -p /opt/admin-system
cd /opt/admin-system

# 上传代码（使用scp或git）
scp -r ./admin_system/* username@your-server-ip:/opt/admin-system/
# 或者使用git
git clone https://github.com/your-username/fp.git
cd fp/admin_system

# 构建Docker镜像
docker build -t admin-system .

# 运行容器
docker run -d \
  --name admin-system \
  -p 8080:8080 \
  --restart unless-stopped \
  admin-system
```

**方法C：使用Docker Compose（推荐）**
```bash
# 创建docker-compose.yml文件
cat > docker-compose.yml << EOF
version: '3.8'
services:
  admin-system:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DB_HOST=your-db-host.mysql.rds.aliyuncs.com
      - DB_PORT=3306
      - DB_USER=your-db-user
      - DB_PASSWORD=your-db-password
      - DB_NAME=demo01
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
EOF

# 启动服务
docker-compose up -d
```

#### 5. 配置防火墙和安全组
```bash
# 服务器防火墙配置
sudo ufw allow 8080
sudo ufw enable

# 云服务器安全组配置（在云服务商控制台）
# 开放端口：8080
# 协议：TCP
# 源地址：0.0.0.0/0 (或指定IP段)
```

#### 6. 域名配置（可选）
```bash
# 安装Nginx作为反向代理
sudo apt install nginx

# 配置Nginx
sudo vim /etc/nginx/sites-available/admin-system
```

Nginx配置示例：
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/admin-system /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 方案三：公网数据库 + 多服务器部署

#### 1. 创建公网数据库
- **阿里云RDS**: https://ecs.console.aliyun.com/
- **腾讯云CDB**: https://console.cloud.tencent.com/
- **华为云RDS**: https://console.huaweicloud.com/

#### 2. 数据库配置
```python
# 在admin_system/app.py中配置
DB_CONFIG = {
    'host': 'rm-xxxxxxxx.mysql.rds.aliyuncs.com',  # RDS实例地址
    'port': 3306,
    'user': 'admin_user',
    'password': 'your_secure_password',
    'database': 'demo01',
    'charset': 'utf8mb4'
}
```

#### 3. 多服务器部署
```bash
# 服务器A：部署前端和后端
# 服务器B：部署独立管理员系统
# 数据库：使用公网RDS

# 所有服务器都连接同一个公网数据库
# 实现数据共享和高可用
```

### 🔧 部署后验证

#### 1. 检查服务状态
```bash
# 检查Docker容器状态
docker ps

# 查看日志
docker logs admin-system

# 检查端口监听
netstat -tlnp | grep 8080
```

#### 2. 访问测试
- 浏览器访问：http://your-server-ip:8080
- 或域名访问：http://your-domain.com
- 测试登录注册功能
- 测试管理员功能

#### 3. 监控和维护
```bash
# 查看系统资源
htop
df -h

# 备份数据
docker exec admin-system mysqldump -h db_host -u user -p database > backup.sql

# 更新应用
docker-compose pull
docker-compose up -d
```

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

- 项目维护者: 重庆大学实训小组
- 邮箱: 951893790@qq.com
- 项目链接: [https://github.com/yourusername/fp](https://github.com/yourusername/fp)

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者和用户。

---

## 🌟 独立管理员系统特色

### 完全独立部署
- ✅ **独立运行**: 不依赖前端和后端，可单独部署
- ✅ **完整功能**: 包含完整的前后端一体化管理功能
- ✅ **数据同步**: 与主系统共享数据库，数据实时同步

### 公网部署优势
- 🌐 **远程管理**: 管理员可在任何地点访问系统
- 🔒 **安全隔离**: 独立部署，不影响主系统运行
- 📱 **多端访问**: 支持PC、平板、手机等多端访问
- ⚡ **高可用**: 支持负载均衡和集群部署

### XShell部署流程
1. **远程连接**: 使用XShell连接云服务器
2. **环境准备**: 安装Docker和相关依赖
3. **镜像部署**: 拉取或构建Docker镜像
4. **服务启动**: 启动容器并配置端口映射
5. **域名绑定**: 配置域名和SSL证书（可选）

### 数据库连接方案
- **本地数据库**: 适合开发测试环境
- **公网数据库**: 适合生产环境，支持多服务器共享
- **云数据库**: 推荐使用阿里云RDS、腾讯云CDB等

---

**注意**: 这是一个疲劳驾驶检测系统，请确保在实际使用中遵守相关法律法规和安全标准。

**安全提醒**:
- 部署到公网时请确保使用强密码
- 建议配置SSL证书启用HTTPS
- 定期更新系统和依赖包
- 配置防火墙和安全组规则
