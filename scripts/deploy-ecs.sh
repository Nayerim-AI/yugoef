#!/usr/bin/env bash
# Yugoef — Deploy to Alibaba Cloud ECS (Ubuntu 22.04+)
# Run this on a fresh ECS instance.
set -euo pipefail

echo "=== Yugoef — Alibaba Cloud ECS Deployment ==="
echo ""

# ── System deps ──────────────────────────────────────────
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git curl

# ── Clone / deploy ───────────────────────────────────────
echo "[2/5] Deploying Yugoef..."
cd /opt
sudo mkdir -p yugoef
sudo chown ubuntu:ubuntu yugoef 2>/dev/null || true

# If you have the code locally, use your preferred method:
# scp -r ./yugoef ubuntu@<ECS_IP>:/opt/
# Or clone from GitHub once pushed:
# git clone https://github.com/Nayerim-AI/yugoef.git /opt/yugoef

# For now, assume code is at /opt/yugoef/
cd /opt/yugoef

# ── Python venv ──────────────────────────────────────────
echo "[3/5] Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

# ── Qwen Cloud API key ───────────────────────────────────
echo "[4/5] Configuring environment..."
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# Yugoef on Alibaba Cloud
# !! IMPORTANT: Replace with your actual Qwen Cloud API key !!
QWEN_API_KEY=your_qwen_cloud_api_key_here
QWEN_BASE_URL=https://portal.qwen.ai/v1
QWEN_MODEL=qwen3.7-plus

# Disable simulated mode — RuView sends real events
RUVIEW_SIMULATED=true

# Server
YUGOEF_HOST=0.0.0.0
YUGOEF_PORT=8000
YUGOEF_DEBUG=false
ENVEOF
    echo "  .env file created — EDIT IT with your QWEN_API_KEY"
fi

# ── Systemd service ──────────────────────────────────────
echo "[5/5] Installing systemd service..."
sudo tee /etc/systemd/system/yugoef.service > /dev/null << 'SERVICEOF'
[Unit]
Description=Yugoef — Room Intelligence Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/yugoef
EnvironmentFile=/opt/yugoef/.env
ExecStart=/opt/yugoef/.venv/bin/uvicorn yugoef.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICEOF

sudo systemctl daemon-reload
sudo systemctl enable yugoef
sudo systemctl start yugoef

echo ""
echo "=== Deployment complete ==="
echo ""
echo "  Service:  yugoef.service"
echo "  Status:   sudo systemctl status yugoef"
echo "  Logs:     sudo journalctl -u yugoef -f"
echo "  API:      http://$(curl -s http://checkip.amazonaws.com):8000"
echo "  Health:   curl http://localhost:8000/health"
echo ""
echo "  Next:"
echo "  1. Edit /opt/yugoef/.env — set QWEN_API_KEY"
echo "  2. Restart: sudo systemctl restart yugoef"
echo "  3. Security group: open port 8000 (TCP)"
echo "  4. Test: curl http://localhost:8000/health"
echo ""
