@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

cd /d C:\FTM

echo ======================================== >> C:\FTM\logs\scheduled_system_health_mail_output.txt
echo FTM system health mail started: %date% %time% >> C:\FTM\logs\scheduled_system_health_mail_output.txt

C:\FTM\.venv\Scripts\python.exe -m app.db.send_system_health_mail >> C:\FTM\logs\scheduled_system_health_mail_output.txt 2>&1

echo FTM system health mail finished: %date% %time% >> C:\FTM\logs\scheduled_system_health_mail_output.txt
echo ======================================== >> C:\FTM\logs\scheduled_system_health_mail_output.txt