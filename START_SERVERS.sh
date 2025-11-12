#!/bin/bash

# Start script for Rhasspy AI Avatar
# Assumes Python and pip are already installed
# Kills processes on busy ports and installs ffmpeg if needed

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

# Detect Python (assume installed, but find the command)
detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    else
        echo "python3"  # Default fallback
    fi
}

PYTHON_CMD="$(detect_python)"
PIP_CMD="${PYTHON_CMD} -m pip"

echo -e "${BLUE}Using Python: ${PYTHON_CMD}${NC}"

# Install ffmpeg if not available
install_ffmpeg() {
    if command -v ffmpeg >/dev/null 2>&1; then
        echo -e "${GREEN}✅ ffmpeg is already installed${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}⚠️  ffmpeg not found. Installing...${NC}"
    
    if command -v brew >/dev/null 2>&1; then
        echo "Installing ffmpeg via Homebrew..."
        brew install ffmpeg > "${LOG_FFMPEG}" 2>&1
    elif command -v apt-get >/dev/null 2>&1; then
        echo "Installing ffmpeg via apt-get..."
        sudo apt-get update && sudo apt-get install -y ffmpeg > "${LOG_FFMPEG}" 2>&1
    elif command -v dnf >/dev/null 2>&1; then
        echo "Installing ffmpeg via dnf..."
        sudo dnf install -y ffmpeg > "${LOG_FFMPEG}" 2>&1
    elif command -v yum >/dev/null 2>&1; then
        echo "Installing ffmpeg via yum..."
        sudo yum install -y ffmpeg > "${LOG_FFMPEG}" 2>&1
    elif command -v pacman >/dev/null 2>&1; then
        echo "Installing ffmpeg via pacman..."
        sudo pacman -Sy --noconfirm ffmpeg > "${LOG_FFMPEG}" 2>&1
    else
        echo -e "${YELLOW}⚠️  Could not install ffmpeg automatically. Please install it manually:${NC}"
        echo "   macOS: brew install ffmpeg"
        echo "   Ubuntu/Debian: sudo apt-get install ffmpeg"
        echo "   Fedora: sudo dnf install ffmpeg"
        echo "   Arch: sudo pacman -Sy ffmpeg"
        echo "   (Installation log: ${LOG_FFMPEG})"
        return 1
    fi
    
    if command -v ffmpeg >/dev/null 2>&1; then
        echo -e "${GREEN}✅ ffmpeg installed successfully${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  ffmpeg installation may have failed. Check ${LOG_FFMPEG}${NC}"
        return 1
    fi
}

install_ffmpeg

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
echo "📦 Installing Python dependencies..."
python -m pip install --upgrade pip >/dev/null 2>&1
python -m pip install -r "${BACKEND_DIR}/requirements.txt"
echo -e "${GREEN}✅ Python dependencies installed${NC}"

# Kill process on a specific port
kill_on_port() {
    local port="$1"
    local pids
    
    # Try lsof first (works on macOS/Linux)
    pids=$(lsof -ti tcp:"${port}" 2>/dev/null || true)
    
    # If lsof didn't work, try netstat/fuser
    if [[ -z "${pids}" ]]; then
        pids=$(netstat -tlnp 2>/dev/null | grep ":${port} " | awk '{print $7}' | cut -d'/' -f1 | grep -v "^$" || true)
    fi
    
    if [[ -n "${pids}" ]]; then
        echo -e "${YELLOW}⚠️  Port ${port} is busy (PIDs: ${pids}) — killing processes...${NC}"
        for pid in ${pids}; do
            kill "${pid}" 2>/dev/null || true
        done
        sleep 2
        
        # Force kill if still running
        pids=$(lsof -ti tcp:"${port}" 2>/dev/null || true)
        if [[ -n "${pids}" ]]; then
            echo -e "${YELLOW}⚠️  Force killing processes on port ${port}...${NC}"
            for pid in ${pids}; do
                kill -9 "${pid}" 2>/dev/null || true
            done
            sleep 1
        fi
        echo -e "${GREEN}✅ Port ${port} cleared${NC}"
    else
        echo -e "${GREEN}✅ Port ${port} is free${NC}"
    fi
}

# Kill existing Python processes for this project
kill_existing_processes() {
    echo "🔍 Checking for existing server processes..."
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "python.*http.server.*${FRONTEND_PORT}" 2>/dev/null || true
    sleep 1
}

echo ""
echo "🚀 Starting Rhasspy AI Avatar Servers..."
echo ""
echo "🔍 Ensuring ports ${BACKEND_PORT} and ${FRONTEND_PORT} are free..."
kill_existing_processes
kill_on_port "${BACKEND_PORT}"
kill_on_port "${FRONTEND_PORT}"

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
    echo -e "${YELLOW}⚠️  Backend failed to start. Killing processes on port ${BACKEND_PORT} and retrying...${NC}"
    kill_on_port "${BACKEND_PORT}"
    sleep 2
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
echo "   pkill -f 'python.*app.py'"
echo "   pkill -f 'python.*http.server.*${FRONTEND_PORT}'"
echo ""
echo "Press Ctrl+C to stop this script (servers remain running)"
echo ""

wait
