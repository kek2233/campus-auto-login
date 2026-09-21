@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[Environment]::GetFolderPath('Startup');$f=Join-Path $s '校园网自动连接.lnk';if(Test-Path $f){Remove-Item $f -Force}"
if %errorlevel%==0 (echo 开机自启已关闭) else (echo 操作失败)
pause
