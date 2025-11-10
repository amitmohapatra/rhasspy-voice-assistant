@echo off
setlocal enabledelayedexpansion

REM Determine project root (folder containing this script)
set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "VENV_DIR=%ROOT_DIR%venv"
set "BACKEND_PORT=5000"
set "FRONTEND_PORT=8000"

REM Detect Python
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
)
if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python is not installed or not on PATH. Please install Python 3.9+.
    exit /b 1
)

REM Ensure pip exists
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available for %PYTHON_CMD%. Install pip and try again.
    exit /b 1
)

REM Check ffmpeg and start installation in background if needed
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [WARN] ffmpeg not found. Starting installation in background...
    start "ffmpeg Installation" cmd /c "(where choco >nul 2>&1 && choco install ffmpeg -y || (where winget >nul 2>&1 && winget install --id=Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements || echo [WARN] Could not install ffmpeg automatically. Install manually.)) > \"%ROOT_DIR%ffmpeg_install.log\" 2>&1 && echo [INFO] ffmpeg installation completed. Check ffmpeg_install.log || echo [WARN] ffmpeg installation failed. Check ffmpeg_install.log"
    echo [INFO] ffmpeg installation started in background. Servers will start now.
) else (
    echo [INFO] ffmpeg is already installed.
)

REM Set up virtual environment
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
    echo Virtual environment created.
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

REM Install/upgrade dependencies in venv
echo Installing Python dependencies in virtual environment...
python -m pip install --upgrade pip >nul
python -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    exit /b 1
)
echo Dependencies ready.

REM Kill existing servers
for /f "tokens=1" %%p in ('powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*app.py*' } | ForEach-Object { $_.Id }"') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=1" %%p in ('powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*http.server*%FRONTEND_PORT%*' } | ForEach-Object { $_.Id }"') do taskkill /PID %%p /F >nul 2>&1

echo Starting backend server...
start "Rhasspy Backend" cmd /c "call \"%VENV_DIR%\Scripts\activate.bat\" && python \"%BACKEND_DIR%\app.py\" > \"%ROOT_DIR%backend.log\" 2>&1"
powershell -Command "Try { $Retry=30; while ($Retry -gt 0) { Start-Sleep 1; if ((Invoke-WebRequest -UseBasicParsing http://localhost:%BACKEND_PORT%/health).StatusCode -eq 200) { exit 0 } $Retry-- }; exit 1 } Catch { exit 1 }"
if errorlevel 1 (
    echo [WARN] Backend failed to start. Attempting port cleanup...
    powershell -Command "Get-Process -Id (Get-NetTCPConnection -LocalPort %BACKEND_PORT% -State Listen -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"
    start "Rhasspy Backend" cmd /c "call \"%VENV_DIR%\Scripts\activate.bat\" && python \"%BACKEND_DIR%\app.py\" > \"%ROOT_DIR%backend.log\" 2>&1"
    powershell -Command "Try { $Retry=30; while ($Retry -gt 0) { Start-Sleep 1; if ((Invoke-WebRequest -UseBasicParsing http://localhost:%BACKEND_PORT%/health).StatusCode -eq 200) { exit 0 } $Retry-- }; exit 1 } Catch { exit 1 }"
    if errorlevel 1 (
        echo [ERROR] Backend failed to start after retry. See backend.log.
        exit /b 1
    )
)

echo Starting frontend server...
start "Rhasspy Frontend" cmd /c "call \"%VENV_DIR%\Scripts\activate.bat\" && cd /d \"%FRONTEND_DIR%\" && python -m http.server %FRONTEND_PORT% > \"%ROOT_DIR%frontend.log\" 2>&1"
powershell -Command "Try { $Retry=15; while ($Retry -gt 0) { Start-Sleep 1; if ((Invoke-WebRequest -UseBasicParsing http://localhost:%FRONTEND_PORT%).StatusCode -eq 200) { exit 0 } $Retry-- }; exit 1 } Catch { exit 1 }"
if errorlevel 1 (
    echo [ERROR] Frontend failed to start. See frontend.log.
    exit /b 1
)

echo.
echo ================================
echo  Rhasspy servers are running!
echo ================================
echo Backend:  http://localhost:%BACKEND_PORT%
echo Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo Logs located at:
echo   "%ROOT_DIR%backend.log"
echo   "%ROOT_DIR%frontend.log"
if exist "%ROOT_DIR%ffmpeg_install.log" (
    echo   "%ROOT_DIR%ffmpeg_install.log"
)
echo.
echo Use Task Manager or close the console windows to stop the servers.

endlocal
