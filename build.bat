@echo off
REM ==============================
REM PyInstaller 자동 빌드 스크립트
REM ==============================
chcp 65001 >nul

set SCRIPT_NAME=main.py
set ICON_PATH=assets\app.ico
set DIST_PATH=dist
set BUILD_PATH=build
set DEFAULT_CONFIG_FILE=default_config.ini
set CONFIG_FILE=config.ini
set EXE_NAME=Grafana_Uploader

REM 스크립트 실행 경로로 이동 (어디서 실행해도 안전)
cd /d "%~dp0"

echo [1/4] 이전 빌드 폴더 정리 중...
rmdir /s /q "%DIST_PATH%" 2>nul
rmdir /s /q "%BUILD_PATH%" 2>nul
del /q *.spec 2>nul

echo [2/4] PyInstaller 빌드 중...
pyinstaller ^
 --onefile ^
 --noconsole ^
 --icon=%ICON_PATH% ^
 --add-data "%CONFIG_FILE%;." ^
 --name=%EXE_NAME% ^
 %SCRIPT_NAME%

IF %ERRORLEVEL% NEQ 0 (
    echo [오류] 빌드 실패!
    pause
    exit /b %ERRORLEVEL%
)

echo [3/4] 복사 중...

REM config.ini 복사
IF EXIST "%DEFAULT_CONFIG_FILE%" (
    copy /Y "%DEFAULT_CONFIG_FILE%" "%DIST_PATH%\%CONFIG_FILE%"
) ELSE (
    echo default_config.ini 파일이 없습니다. 복사 생략.
)

REM data 폴더 복사 (하위 폴더 포함)
if exist data (
    xcopy data "%DIST_PATH%\data" /E /I /Y >nul
)

if exist README.md (
    copy /Y README.md "%DIST_PATH%" >nul
)

echo [4/4] 빌드 완료! 결과물은 dist
echo ===============================================
echo dist\%EXE_NAME%.exe
echo ===============================================

pause
