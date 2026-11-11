#!/usr/bin/env bash
# AI原生CRM - Linux/macOS 启动脚本
# 用法: chmod +x start.sh && ./start.sh
set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "           AI原生CRM - 一键启动"
echo "=================================================="

# ---------- 1. 定位 Python 3.10+ ----------
PY=""
for cmd in python3 python; do
    if command -v $cmd >/dev/null 2>&1; then
        if $cmd -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null; then
            PY=$cmd; break
        fi
    fi
done
if [ -z "$PY" ]; then
    echo "[X] 未找到 Python 3.10+，请先安装"
    exit 1
fi
echo "[√] Python: $($PY --version)"

# ---------- 2. 依赖检查（缺失自动安装）----------
if ! $PY -c "import tornado, numpy, httpx, aiosqlite, dotenv" >/dev/null 2>&1; then
    echo "[!] 核心依赖缺失，正在自动安装..."
    $PY -m pip install -r requirements.txt -q
fi
echo "[√] 依赖就绪"

# ---------- 3. 首次运行初始化 .env ----------
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[√] 已生成 .env（默认离线演示模式；填入 LLM_API_KEY 即启用真实大模型）"
fi

# ---------- 4. 启动服务 ----------
echo "[√] 启动服务: http://127.0.0.1:8888"
exec $PY main.py
