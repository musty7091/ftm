@echo off
cd /d C:\FTM

echo ======================================== >> C:\FTM\logs\scheduled_backup_output.txt
echo FTM scheduled backup started: %date% %time% >> C:\FTM\logs\scheduled_backup_output.txt

C:\FTM\.venv\Scripts\python.exe -m app.db.backup_database >> C:\FTM\logs\scheduled_backup_output.txt 2>&1

echo FTM scheduled backup finished: %date% %time% >> C:\FTM\logs\scheduled_backup_output.txt
echo ======================================== >> C:\FTM\logs\scheduled_backup_output.txt