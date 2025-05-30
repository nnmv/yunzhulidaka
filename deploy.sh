#!/bin/bash

# 自动打卡系统部署脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# 输出欢迎信息
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}       自动打卡系统部署脚本${NC}"
echo -e "${GREEN}=========================================${NC}"
echo

# 检查是否为root用户
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}错误: 请使用root用户运行此脚本${NC}"
    exit 1
fi

# 定义变量
APP_DIR="/www/wwwroot/auto_clock_in"
LOG_DIR="/www/wwwlogs/auto_clock_in"
USER="www"
GROUP="www"
PYTHON_VERSION="3.9"
VENV_DIR="${APP_DIR}/venv"

# 创建应用目录
echo -e "${YELLOW}正在创建应用目录...${NC}"
mkdir -p ${APP_DIR}
mkdir -p ${LOG_DIR}
chown -R ${USER}:${GROUP} ${APP_DIR}
chown -R ${USER}:${GROUP} ${LOG_DIR}
echo -e "${GREEN}应用目录创建完成${NC}"

# 安装依赖
echo -e "${YELLOW}正在安装依赖...${NC}"
yum install -y epel-release
yum install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-devel python${PYTHON_VERSION}-pip gcc git
echo -e "${GREEN}依赖安装完成${NC}"

# 创建虚拟环境
echo -e "${YELLOW}正在创建Python虚拟环境...${NC}"
su - ${USER} -c "python${PYTHON_VERSION} -m venv ${VENV_DIR}"
echo -e "${GREEN}虚拟环境创建完成${NC}"

# 激活虚拟环境并安装Python包
echo -e "${YELLOW}正在安装Python包...${NC}"
su - ${USER} -c "source ${VENV_DIR}/bin/activate && pip install --upgrade pip && pip install flask flask-sqlalchemy apscheduler requests gunicorn"
echo -e "${GREEN}Python包安装完成${NC}"

# 复制应用文件
echo -e "${YELLOW}正在复制应用文件...${NC}"
cp -r ./* ${APP_DIR}/
chown -R ${USER}:${GROUP} ${APP_DIR}
echo -e "${GREEN}应用文件复制完成${NC}"

# 创建systemd服务
echo -e "${YELLOW}正在创建systemd服务...${NC}"
cat > /etc/systemd/system/auto_clock_in.service << EOF
[Unit]
Description=自动打卡系统
After=network.target

[Service]
User=${USER}
Group=${GROUP}
WorkingDirectory=${APP_DIR}
Environment="PATH=${VENV_DIR}/bin"
ExecStart=${VENV_DIR}/bin/gunicorn -w 4 -b 0.0.0.0:5000 main:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl enable auto_clock_in
systemctl start auto_clock_in
echo -e "${GREEN}服务已启动${NC}"

# 配置防火墙
echo -e "${YELLOW}正在配置防火墙...${NC}"
firewall-cmd --zone=public --add-port=5000/tcp --permanent
firewall-cmd --reload
echo -e "${GREEN}防火墙配置完成${NC}"

# 输出完成信息
echo
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}       自动打卡系统部署完成!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${YELLOW}访问地址: http://服务器IP:5000${NC}"
echo -e "${YELLOW}管理后台: http://服务器IP:5000/admin${NC}"
echo -e "${YELLOW}默认管理员密码: your_admin_password (请在代码中修改)${NC}"
echo
echo -e "${YELLOW}服务管理命令:${NC}"
echo -e "${YELLOW}  启动: systemctl start auto_clock_in${NC}"
echo -e "${YELLOW}  停止: systemctl stop auto_clock_in${NC}"
echo -e "${YELLOW}  重启: systemctl restart auto_clock_in${NC}"
echo -e "${YELLOW}  状态: systemctl status auto_clock_in${NC}"
echo