@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PYTHON_VERSION=3.13.14"
set "RUNTIME_DIR=%~dp0.runtime\python"
set "PYTHON_EXE=%RUNTIME_DIR%\python.exe"

if not exist "%PYTHON_EXE%" call :bootstrap_python
if not exist "%PYTHON_EXE%" goto :failed

echo Generating content.json...
"%PYTHON_EXE%" generate.py
if errorlevel 1 goto :failed

echo.
echo Local preview: http://localhost:8000
echo Close this window or press Ctrl+C to stop.
echo.

if not defined BLOG_NO_BROWSER start "" /b cmd /d /c "ping -n 3 127.0.0.1 >nul & start http://localhost:8000"
"%PYTHON_EXE%" -m http.server 8000
exit /b %errorlevel%

:bootstrap_python
echo Python runtime not found. Downloading a project-local copy...

where curl.exe >nul 2>&1 || goto :bootstrap_missing_tools
where tar.exe >nul 2>&1 || goto :bootstrap_missing_tools

set "PYTHON_ARCH=amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PYTHON_ARCH=arm64"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" set "PYTHON_ARCH=win32"

set "RUNTIME_ZIP=%TEMP%\blog-python-%PYTHON_VERSION%-%PYTHON_ARCH%.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-%PYTHON_ARCH%.zip"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>&1
curl.exe -fL --retry 3 --connect-timeout 15 -o "%RUNTIME_ZIP%" "%PYTHON_URL%"
if errorlevel 1 goto :bootstrap_failed

tar.exe -xf "%RUNTIME_ZIP%" -C "%RUNTIME_DIR%"
if errorlevel 1 goto :bootstrap_failed
del /q "%RUNTIME_ZIP%" >nul 2>&1
exit /b 0

:bootstrap_missing_tools
echo [ERROR] curl.exe or tar.exe is unavailable on this Windows installation.
exit /b 1

:bootstrap_failed
echo [ERROR] Failed to download or extract the Python runtime.
exit /b 1

:failed
echo.
echo [ERROR] Local preview failed to start.
pause
exit /b 1
