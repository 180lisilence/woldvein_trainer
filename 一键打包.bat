@echo off
chcp 936 >nul
cd /d "%~dp0"
title 一键打包 - 平野孤鸿修改器 v0.5.0（主线）
echo ============================================================
echo   平野孤鸿修改器 v0.5.0（主线）
echo   spec : woldvein_trainer.spec
echo   模式 : onefile
echo   产物 : dist\woldvein_trainer.exe
echo ============================================================
echo.

set "TOOLS=%~dp0..\..\tools"
set "SELFTEST=%TOOLS%\post_build.py"

set "PY=E:\pythonpath\python.exe"

if not exist "%PY%" (
  echo [错误] 未找到 Python: %PY%
  echo        请修改本 bat 里的 PY 变量，指向你的 Python
  echo        注意: GUI 项目必须用带 tkinter 的 Python
  echo        ^(托管 Python 通常没有 tkinter^)
  pause
  exit /b 1
)

echo [1/3] 环境检查
"%PY%" -c "import sys;print('       Python', sys.version.split()[0])"
"%PY%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo       PyInstaller 未安装，正在安装...
  "%PY%" -m pip install pyinstaller
  if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    echo        请手动执行: "%PY%" -m pip install pyinstaller
    pause
    exit /b 1
  )
)
"%PY%" -c "import PyInstaller;print('       PyInstaller', PyInstaller.__version__)"

echo.
echo [2/3] 清理旧构建
if exist build rmdir /s /q build
if exist "dist\woldvein_trainer.exe" del /q "dist\woldvein_trainer.exe"

echo.
echo [3/4] 打包中，请稍候 ^(约 10-60 秒^)...
rem 上面已自行 rmdir build，这里不再加 --clean：--clean 会触发一次
rem 几十到上百个文件的批量删除，在受管控环境里可能被拦截导致构建中断
"%PY%" -m PyInstaller --noconfirm woldvein_trainer.spec
if errorlevel 1 (
  echo.
  echo [失败] 打包出错，请看上方错误信息
  pause
  exit /b 1
)

echo.
echo [4/4] 产物自检 ^(资源是否真的打进去 / 注入器是否随行^)
if not exist "%SELFTEST%" (
  echo       ^(未找到 %SELFTEST%，跳过自检^)
) else (
  "%PY%" "%SELFTEST%" "%~dp0" "dist\woldvein_trainer.exe"
  if errorlevel 1 (
    echo.
    echo [失败] 产物自检未通过，请看上方 [*] 条目
    pause
    exit /b 1
  )
)

echo.
echo ============================================================
if exist "dist\woldvein_trainer.exe" (
  echo   打包完成
  echo   产物: %CD%\dist\woldvein_trainer.exe
  for %%F in ("dist\woldvein_trainer.exe") do echo   大小: %%~zF 字节
) else (
  echo   未找到 dist\woldvein_trainer.exe，请检查上方输出
)
echo ============================================================
if /i not "%1"=="/nopause" pause
