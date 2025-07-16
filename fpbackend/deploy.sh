#!/bin/bash

# 疲劳检测系统Docker部署脚本

set -e

echo "🚀 开始部署疲劳检测系统..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    print_message "Docker 环境检查通过"
}

# 创建必要的目录
create_directories() {
    print_message "创建必要的目录..."
    
    mkdir -p static/uploads/results
    mkdir -p models/uploads
    mkdir -p logs
    mkdir -p docker/mysql
    mkdir -p docker/nginx/ssl
    
    print_message "目录创建完成"
}

# 检查模型文件
check_model() {
    if [ ! -f "best.pt" ]; then
        print_warning "未找到模型文件 best.pt"
        print_warning "请确保将训练好的模型文件放在项目根目录"
        read -p "是否继续部署？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_message "模型文件检查通过"
    fi
}

# 构建和启动服务
deploy_services() {
    print_message "构建Docker镜像..."
    docker-compose build
    
    print_message "启动服务..."
    docker-compose up -d
    
    print_message "等待服务启动..."
    sleep 10
}

# 检查服务状态
check_services() {
    print_message "检查服务状态..."
    
    # 检查容器状态
    if docker-compose ps | grep -q "Up"; then
        print_message "容器启动成功"
    else
        print_error "容器启动失败"
        docker-compose logs
        exit 1
    fi
    
    # 检查后端健康状态
    for i in {1..30}; do
        if curl -f http://localhost:5001/health &> /dev/null; then
            print_message "后端服务健康检查通过"
            break
        fi
        
        if [ $i -eq 30 ]; then
            print_error "后端服务健康检查失败"
            docker-compose logs fatigue-backend
            exit 1
        fi
        
        sleep 2
    done
}

# 显示部署信息
show_deployment_info() {
    echo
    echo "🎉 部署完成！"
    echo "=================================="
    echo "📋 服务信息:"
    echo "  - 后端API: http://localhost:5001"
    echo "  - 健康检查: http://localhost:5001/health"
    echo "  - Nginx代理: http://localhost:80"
    echo "  - MySQL数据库: localhost:3306"
    echo "  - Redis缓存: localhost:6379"
    echo
    echo "🔑 默认账户:"
    echo "  - 管理员: admin / admin123"
    echo "  - 监控员: monitor / monitor123"
    echo "  - 驾驶员: driver / driver123"
    echo
    echo "📁 数据目录:"
    echo "  - 上传文件: ./static/uploads"
    echo "  - 模型文件: ./models"
    echo "  - 日志文件: ./logs"
    echo
    echo "🛠️  管理命令:"
    echo "  - 查看日志: docker-compose logs -f"
    echo "  - 停止服务: docker-compose down"
    echo "  - 重启服务: docker-compose restart"
    echo "  - 更新服务: docker-compose up -d --build"
    echo "=================================="
}

# 主函数
main() {
    echo "疲劳检测系统 Docker 部署脚本"
    echo "=================================="
    
    check_docker
    create_directories
    check_model
    deploy_services
    check_services
    show_deployment_info
}

# 执行主函数
main "$@"
