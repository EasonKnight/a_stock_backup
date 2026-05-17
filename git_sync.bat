@echo off
REM Daily git sync for a_stock_trade (bidirectional)
cd /d "C:\Users\Mayn\Desktop\a_stock_trade"

REM 1. Commit local changes
git status --porcelain > "%TEMP%\git_status.tmp"
set /p STATUS=<"%TEMP%\git_status.tmp"
del "%TEMP%\git_status.tmp"

if not "%STATUS%"=="" (
    git add -A
    git commit -m "auto-sync %date%"
)

REM 2. Pull remote changes (rebase)
git pull --rebase origin main 2>nul
if %errorlevel% neq 0 (
    echo PULL FAILED - manual conflict resolution needed
    exit /b 1
)

REM 3. Push back
git push
if %errorlevel% neq 0 (
    echo PUSH FAILED
    exit /b 1
)

echo Sync completed at %date% %time%
