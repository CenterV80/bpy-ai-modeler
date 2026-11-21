@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  bpy モデラーの起動バッチ（Windows）
rem  ・初回は .venv を作って必要なものを入れる
rem  ・requirements.txt が変わったら入れ直す
rem  ・サーバーが立ち上がったらブラウザでビューアーを開く
rem  引数はそのまま server.py に渡す（例: start.bat --port 8001）
rem ============================================================
cd /d "%~dp0"

if not defined PORT set PORT=8000
call :find_port %*

rem ---- 1. 仮想環境（.venv）がなければ作る
if exist ".venv\Scripts\python.exe" goto :install
echo [1/3] 仮想環境（.venv）を Python 3.13 で作っています...
where uv >nul 2>nul
if not errorlevel 1 (
  uv venv --python 3.13 .venv || goto :fail
  goto :install
)
py -3.13 -c "pass" >nul 2>nul
if not errorlevel 1 (
  py -3.13 -m venv .venv || goto :fail
  goto :install
)
echo.
echo uv も Python 3.13 も見つかりません。どちらかを入れてから、もう一度実行してください。
echo   uv:     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo   Python: winget install -e --id Python.Python.3.13
goto :fail

rem ---- 2. 必要なものを入れる（requirements.txt が前回と同じなら飛ばす）
:install
fc /b "requirements.txt" ".venv\requirements.installed" >nul 2>nul
if not errorlevel 1 goto :run
echo [2/3] 必要なもの（bpy など）を入れています。初回は数分かかります...
where uv >nul 2>nul
if not errorlevel 1 (
  uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt || goto :fail
) else (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)
copy /y "requirements.txt" ".venv\requirements.installed" >nul

rem ---- 3. 起動して、立ち上がったらブラウザを開く
:run
echo [3/3] 起動しています（止めるときは Ctrl+C）...
start "" /b powershell -NoProfile -Command "for($i=0;$i -lt 90;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%PORT%/api/runs -TimeoutSec 1 | Out-Null; Start-Process http://127.0.0.1:%PORT%; break}catch{Start-Sleep 1}}"
".venv\Scripts\python.exe" server.py %*
echo.
echo サーバーが止まりました。
pause
exit /b 0

:fail
echo.
echo うまくいきませんでした。上のメッセージを確認してください。
pause
exit /b 1

rem ---- 引数から --port の値を取り出す
:find_port
if "%~1"=="" exit /b 0
if "%~1"=="--port" (
  set PORT=%~2
  exit /b 0
)
shift
goto :find_port
