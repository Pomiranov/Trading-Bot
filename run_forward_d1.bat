@echo off
rem QuantFlow: daily forward run osc_range D1 (Task Scheduler, 00:15)
cd /d D:\Trading-Bot-Nik
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
C:\Python314\python.exe run_forward_d1.py >> logs\forward_d1.log 2>&1
