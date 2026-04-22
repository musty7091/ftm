@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

cd /d C:\FTM

echo ======================================== >> C:\FTM\logs\scheduled_security_summary_mail_output.txt
echo FTM security summary mail started: %date% %time% >> C:\FTM\logs\scheduled_security_summary_mail_output.txt

C:\FTM\.venv\Scripts\python.exe -m app.db.send_security_summary_mail >> C:\FTM\logs\scheduled_security_summary_mail_output.txt 2>&1

echo FTM security summary mail finished: %date% %time% >> C:\FTM\logs\scheduled_security_summary_mail_output.txt
echo ======================================== >> C:\FTM\logs\scheduled_security_summary_mail_output.txt