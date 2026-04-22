@echo off
cd /d C:\FTM

echo ======================================== >> C:\FTM\logs\scheduled_restore_test_output.txt
echo FTM scheduled restore test started: %date% %time% >> C:\FTM\logs\scheduled_restore_test_output.txt

C:\FTM\.venv\Scripts\python.exe -m app.db.test_backup_restore >> C:\FTM\logs\scheduled_restore_test_output.txt 2>&1

echo FTM scheduled restore test finished: %date% %time% >> C:\FTM\logs\scheduled_restore_test_output.txt
echo ======================================== >> C:\FTM\logs\scheduled_restore_test_output.txt