# 多阶段构建 - 针对独立管理员系统优化
FROM python:3.12-slim AS builder

# 设置构建时环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 复制并安装Python依赖
COPY requirements.txt .
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ --timeout 3000 && \
    pip install --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ --timeout 3000 --retries 3

# 生产阶段
FROM python:3.11-slim AS production

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    PATH=/home/appuser/.local/bin:$PATH \
    TZ=Asia/Shanghai

# 安装运行时依赖和时区数据
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置工作目录

WORKDIR /app

# 从构建阶段复制Python包
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码和静态资源
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser requirements.txt .

# 复制静态资源目录 - 确保所有CSS、JS、字体、图片都被包含
COPY --chown=appuser:appuser static/ ./static/
# 确保LayUI的所有模块都被正确复制
COPY --chown=appuser:appuser static/css/ ./static/css/
COPY --chown=appuser:appuser static/font/ ./static/font/
COPY --chown=appuser:appuser static/images/ ./static/images/
COPY --chown=appuser:appuser static/layui.js ./static/

# 复制模板目录
COPY --chown=appuser:appuser templates/ ./templates/

# 复制数据库初始化文件（如果需要）
COPY --chown=appuser:appuser demo01.sql .

# 创建必要的目录并设置权限
RUN mkdir -p /app/logs /app/uploads /app/temp && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/static && \
    chmod -R 755 /app/templates

# 验证关键静态资源文件存在
RUN ls -la /app/static/ && \
    ls -la /app/static/css/ && \
    ls -la /app/static/font/ && \
    test -f /app/static/layui.js && \
    test -f /app/static/css/layui.css && \
    echo "✅ 所有静态资源验证通过"

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 启动命令 - 使用Flask内置服务器（适合开发和小规模部署）
CMD ["python", "app.py"]
