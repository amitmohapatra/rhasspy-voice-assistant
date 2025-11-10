#!/bin/bash

# Start script for Rhasspy AI Avatar
# Sets up virtual environment, installs dependencies,
# then launches backend (Flask) and frontend (static server).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
VENV_DIR="${ROOT_DIR}/venv"
BACKEND_PORT=${BACKEND_PORT:-5000}
FRONTEND_PORT=${FRONTEND_PORT:-8000}

LOG_BACKEND="${ROOT_DIR}/backend.log"
LOG_FRONTEND="${ROOT_DIR}/frontend.log"
LOG_FFMPEG="${ROOT_DIR}/ffmpeg_install.log"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    else
        echo ""
    fi
}

PYTHON_CMD="$(detect_python)"
if [[ -z "${PYTHON_CMD}" ]]; then
    echo -e "${RED}❌ Python is not installed. Please install Python 3.9+ and re-run this script.${NC}"
    exit 1
fi

if ! "${PYTHON_CMD}" -m pip --version >/dev/null 2>&1; then
    echo -e "${RED}❌ pip is not available for ${PYTHON_CMD}. Install pip and try again.${NC}"
    exit 1
fi

# Check ffmpeg and start installation in background if needed
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ ffmpeg not found. Starting installation in background...${NC}"
    (
        if command -v brew >/dev/null 2>&1; then
            brew install ffmpeg > "${LOG_FFMPEG}" 2>&1 && echo -e "${GREEN}✅ ffmpeg installed successfully${NC}" || echo -e "${YELLOW}⚠️ ffmpeg installation failed. Check ${LOG_FFMPEG}${NC}"
        elif command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update && sudo apt-get install -y ffmpeg > "${LOG_FFMPEG}" 2>&1 && echo -e "${GREEN}✅ ffmpeg installed successfully${NC}" || echo -e "${YELLOW}⚠️ ffmpeg installation failed. Check ${LOG_FFMPEG}${NC}"
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y ffmpeg > "${LOG_FFMPEG}" 2>&1 && echo -e "${GREEN}✅ ffmpeg installed successfully${NC}" || echo -e "${YELLOW}⚠️ ffmpeg installation failed. Check ${LOG_FFMPEG}${NC}"
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y ffmpeg > "${LOG_FFMPEG}" 2>&1 && echo -e "${GREEN}✅ ffmpeg installed successfully${NC}" || echo -e "${YELLOW}⚠️ ffmpeg installation failed. Check ${LOG_FFMPEG}${NC}"
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -Sy --noconfirm ffmpeg > "${LOG_FFMPEG}" 2>&1 && echo -e "${GREEN}✅ ffmpeg installed successfully${NC}" || echo -e "${YELLOW}⚠️ ffmpeg installation failed. Check ${LOG_FFMPEG}${NC}"
        else
            echo -e "${YELLOW}⚠️ Could not install ffmpeg automatically. Please install it manually:"
            echo "   macOS: brew install ffmpeg"
            echo "   Ubuntu/Debian: sudo apt-get install ffmpeg"
            echo "   Fedora: sudo dnf install ffmpeg"
            echo "   Arch: sudo pacman -Sy ffmpeg"
            echo "   Windows: choco install ffmpeg  (or https://ffmpeg.org/download.html)"
            echo "   (Installation log: ${LOG_FFMPEG})"
        fi
    ) &
    echo -e "${BLUE}ℹ️  ffmpeg installation started in background. Servers will start now.${NC}"
else
    echo -e "${GREEN}✅ ffmpeg is already installed${NC}"
fi

# Set up virtual environment
if [[ ! -d "${VENV_DIR}" ]]; then
    echo "📦 Creating virtual environment..."
    "${PYTHON_CMD}" -m venv "${VENV_DIR}"
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

# Install/upgrade dependencies in venv
echo "📦 Installing Python dependencies in virtual environment..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "${BACKEND_DIR}/requirements.txt"
echo -e "${GREEN}✅ Python dependencies installed${NC}"

kill_on_port() {
    local port="$1"
    local pids
    pids=$(lsof -ti tcp:"${port}" 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
        echo -e "${YELLOW}⚠️  Port ${port} busy (PIDs: ${pids}) — terminating...${NC}"
        kill ${pids} 2>/dev/null || true
        sleep 1
        if lsof -ti tcp:"${port}" >/dev/null 2>&1; then
            kill -9 ${pids} 2>/dev/null || true
            sleep 1
        fi
    fi
}

kill_existing_processes() {
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "python.*http.server ${FRONTEND_PORT}" 2>/dev/null || true
}

echo ""
echo "🚀 Starting Rhasspy AI Avatar Servers..."
echo ""
echo "🔍 Ensuring ports ${BACKEND_PORT} and ${FRONTEND_PORT} are free..."
kill_existing_processes
kill_on_port "${BACKEND_PORT}"
kill_on_port "${FRONTEND_PORT}"
echo "✅ Ports cleared"

attempt_backend_start() {
    echo -e "${BLUE}Starting backend server on http://localhost:${BACKEND_PORT}${NC}"
    cd "${BACKEND_DIR}"
    python app.py > "${LOG_BACKEND}" 2>&1 &
    BACKEND_PID=$!
    echo "Backend PID: ${BACKEND_PID}"

    echo "⏳ Waiting for backend health check..."
    local retries=30
    until curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; do
        sleep 1
        retries=$((retries - 1))
        if [[ ${retries} -le 0 ]]; then
            return 1
        fi
    done
    echo -e "${GREEN}✅ Backend server running${NC}"
    return 0
}

if ! attempt_backend_start; then
    echo -e "${YELLOW}⚠️ Backend failed to start on first attempt. Trying to free port ${BACKEND_PORT}...${NC}"
    kill_on_port "${BACKEND_PORT}"
    if ! attempt_backend_start; then
        echo -e "${RED}❌ Backend failed to start after retry. Check ${LOG_BACKEND}.${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}Starting frontend server on http://localhost:${FRONTEND_PORT}${NC}"
cd "${FRONTEND_DIR}"
python -m http.server "${FRONTEND_PORT}" > "${LOG_FRONTEND}" 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: ${FRONTEND_PID}"

echo "⏳ Waiting for frontend..."
RETRIES=15
until curl -sf "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; do
    sleep 1
    RETRIES=$((RETRIES - 1))
    if [[ ${RETRIES} -le 0 ]]; then
        echo -e "${RED}❌ Frontend failed to start. Check ${LOG_FRONTEND}.${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✅ Frontend server running${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}🎉 All servers are running!${NC}"
echo "=========================================="
echo ""
echo "📱 Access the application at:"
echo -e "   ${BLUE}http://localhost:${FRONTEND_PORT}${NC}"
echo ""
echo "🔧 Services:"
echo "   Backend API: http://localhost:${BACKEND_PORT}"
echo "   Frontend:    http://localhost:${FRONTEND_PORT}"
echo ""
echo "📝 Logs:"
echo "   Backend:  ${LOG_BACKEND}"
echo "   Frontend: ${LOG_FRONTEND}"
if [[ -f "${LOG_FFMPEG}" ]]; then
    echo "   ffmpeg:   ${LOG_FFMPEG}"
fi
echo ""
echo "🛑 To stop servers, run:"
echo "   pkill -f 'python app.py'"
echo "   pkill -f 'python -m http.server ${FRONTEND_PORT}'"
echo ""
echo "Press Ctrl+C to stop this script (servers remain running)"
echo ""

wait
