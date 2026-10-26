@echo off
setlocal
cd /d "%~dp0"
set "PHYLLO_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
if not exist "%PHYLLO_NODE%" set "PHYLLO_NODE=node"
echo PHYLLO: http://127.0.0.1:8765/
echo Keep this window open while using the local page. Ctrl+C stops the server.
"%PHYLLO_NODE%" server.mjs
pause
