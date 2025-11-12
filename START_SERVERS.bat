@echo off
setlocal enabledelayedexpansion

REM Start script for Rhasspy AI Avatar
REM Assumes Python and pip are already installed
REM Kills processes on busy ports and installs ffmpeg if needed

REM Determine project root (folder containing this script)
set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "VENV_DIR=%ROOT_DIR%venv"
set "BACKEND_PORT=5000"
set "FRONTEND_PORT=8000"

set "LOG_BACKEND=%ROOT_DIR%backend.log"
set "LOG_FRONTEND=%ROOT_DIR%frontend.log"
set "LOG_FFMPEG=%ROOT_DIR%ffmpeg_install.log"

REM Detect Python (assume installed, but find the command)
set "PYTHON_CMD=python"
where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
if "%PYTHON_CMD%"=="" set "PYTHON_CMD=python"

echo [INFO] Using Python: %PYTHON_CMD%

REM Install ffmpeg if not available
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [WARN] ffmpeg not found. Installing...
    
    REM Try Chocolatey first
    where choco >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] Installing ffmpeg via Chocolatey...
        choco install ffmpeg -y > "%LOG_FFMPEG%" 2>&1
    ) else (
        REM Try winget
        where winget >nul 2>&1
        if not errorlevel 1 (
            echo [INFO] Installing ffmpeg via winget...
            winget install --id=Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements > "%LOG_FFMPEG%" 2>&1
        ) else (
            echo [WARN] Could not install ffmpeg automatically. Please install manually:
            echo    Chocolatey: choco install ffmpeg
            echo    winget: winget install Gyan.FFmpeg
            echo    Or download from: https://ffmpeg.org/download.html
            echo    Installation log: %LOG_FFMPEG%
        )
    )
    
    REM Verify installation
    where ffmpeg >nul 2>&1
    if errorlevel 1 (
        echo [WARN] ffmpeg installation may have failed. Check %LOG_FFMPEG%
    ) else (
        echo [INFO] ffmpeg installed successfully
    )
) else (
    echo [INFO] ffmpeg is already installed
)

REM Set up virtual environment
if not exist "%VENV_DIR%" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
    echo [INFO] Virtual environment created
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

REM Install/upgrade dependencies in venv
echo [INFO] Installing Python dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    exit /b 1
)
echo [INFO] Python dependencies installed

REM Function to kill process on a port
echo.
echo [INFO] Ensuring ports %BACKEND_PORT% and %FRONTEND_PORT% are free...

REM Kill processes on backend port
powershell -Command "$ErrorActionPreference='SilentlyContinue'; $conn = Get-NetTCPConnection -LocalPort %BACKEND_PORT% -State Listen -ErrorAction SilentlyContinue; if ($conn) { $pid = $conn.OwningProcess; Write-Host '[WARN] Port %BACKEND_PORT% is busy (PID: '$pid') - killing...'; Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2; $conn2 = Get-NetTCPConnection -LocalPort %BACKEND_PORT% -State Listen -ErrorAction SilentlyContinue; if ($conn2) { Stop-Process -Id $conn2.OwningProcess -Force -ErrorAction SilentlyContinue } } else { Write-Host '[INFO] Port %BACKEND_PORT% is free' }"

REM Kill processes on frontend port
powershell -Command "$ErrorActionPreference='SilentlyContinue'; $conn = Get-NetTCPConnection -LocalPort %FRONTEND_PORT% -State Listen -ErrorAction SilentlyContinue; if ($conn) { $pid = $conn.OwningProcess; Write-Host '[WARN] Port %FRONTEND_PORT% is busy (PID: '$pid') - killing...'; Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2; $conn2 = Get-NetTCPConnection -LocalPort %FRONTEND_PORT% -State Listen -ErrorAction SilentlyContinue; if ($conn2) { Stop-Process -Id $conn2.OwningProcess -Force -ErrorAction SilentlyContinue } } else { Write-Host '[INFO] Port %FRONTEND_PORT% is free' }"

REM Kill existing Python processes for this project
echo [INFO] Checking for existing server processes...
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*app.py*' -or $_.CommandLine -like '*http.server*%FRONTEND_PORT%*' } | Stop-Process -Force -ErrorAction SilentlyContinue"
timeout /t 1 /nobreak >nul

echo.
echo [INFO] Starting Rhasspy AI Avatar Servers...
echo.

REM Start backend server
echo [INFO] Starting backend server on http://localhost:%BACKEND_PORT%
start "Rhasspy Backend" cmd /c "call \"%VENV_DIR%\Scripts\activate.bat\" && cd /d \"%BACKEND_DIR%\" && python app.py > \"%LOG_BACKEND%\" 2>&1"

REM Wait for backend to be ready
echo [INFO] Waiting for backend health check...
powershell -Command "$ErrorActionPreference='SilentlyContinue'; $retries=30; while ($retries -gt 0) { Start-Sleep 1; try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:%BACKEND_PORT%/health' -TimeoutSec 1; if ($response.StatusCode -eq 200) { Write-Host '[INFO] Backend server running'; exit 0 } } catch { } $retries-- }; Write-Host '[WARN] Backend failed to start. Attempting port cleanup...'; $conn = Get-NetTCPConnection -LocalPort %BACKEND_PORT% -State Listen -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 }; start 'Rhasspy Backend' cmd /c \"call \\\"%VENV_DIR%\\Scripts\\activate.bat\\\" && cd /d \\\"%BACKEND_DIR%\\\" && python app.py > \\\"%LOG_BACKEND%\\\" 2>&1\"; $retries=30; while ($retries -gt 0) { Start-Sleep 1; try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:%BACKEND_PORT%/health' -TimeoutSec 1; if ($response.StatusCode -eq 200) { Write-Host '[INFO] Backend server running'; exit 0 } } catch { } $retries-- }; Write-Host '[ERROR] Backend failed to start after retry'; exit 1"

if errorlevel 1 (
    echo [ERROR] Backend failed to start. Check %LOG_BACKEND%
    exit /b 1
)

REM Start frontend server
echo [INFO] Starting frontend server on http://localhost:%FRONTEND_PORT%
start "Rhasspy Frontend" cmd /c "call \"%VENV_DIR%\Scripts\activate.bat\" && cd /d \"%FRONTEND_DIR%\" && python -m http.server %FRONTEND_PORT% > \"%LOG_FRONTEND%\" 2>&1"

REM Wait for frontend to be ready
echo [INFO] Waiting for frontend...
powershell -Command "$ErrorActionPreference='SilentlyContinue'; $retries=15; while ($retries -gt 0) { Start-Sleep 1; try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:%FRONTEND_PORT%' -TimeoutSec 1; if ($response.StatusCode -eq 200) { Write-Host '[INFO] Frontend server running'; exit 0 } } catch { } $retries-- }; Write-Host '[ERROR] Frontend failed to start'; exit 1"

if errorlevel 1 (
    echo [ERROR] Frontend failed to start. Check %LOG_FRONTEND%
    exit /b 1
)

echo.
echo ================================
echo  Rhasspy servers are running!
echo ================================
echo.
echo Access the application at:
echo   http://localhost:%FRONTEND_PORT%
echo.
echo Services:
echo   Backend API: http://localhost:%BACKEND_PORT%
echo   Frontend:    http://localhost:%FRONTEND_PORT%
echo.
echo Logs located at:
echo   %LOG_BACKEND%
echo   %LOG_FRONTEND%
if exist "%LOG_FFMPEG%" (
    echo   %LOG_FFMPEG%
)
echo.
echo Use Task Manager or close the console windows to stop the servers.
echo.

endlocal
