@echo off
chcp 65001 >nul
echo 正在开启开机自动连接……
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[Environment]::GetFolderPath('Startup');$ws=New-Object -ComObject WScript.Shell;$l=$ws.CreateShortcut((Join-Path $s '校园网自动连接.lnk'));$l.TargetPath='C:\Users\huanyu\Desktop\校园网自动连接\校园网自动连接.exe';$l.Arguments='--autostart';$l.WorkingDirectory='C:\Users\huanyu\Desktop\校园网自动连接';$l.Description='开机自动连接校园网';$l.Save()"
if %errorlevel%==0 (echo 已开启：开机后将自动连接校园网) else (echo 开启失败)
pause
