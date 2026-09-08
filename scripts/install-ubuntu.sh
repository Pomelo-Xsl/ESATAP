#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y python3-venv fio nvme-cli util-linux
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
mkdir -p data results
echo "安装完成。运行 scripts/run.sh 启动平台。"

