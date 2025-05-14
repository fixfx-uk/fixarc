@echo off
REM Windows Batch wrapper for the Python-based fixarc-handler.

SET "SCRIPT_DIR=%~dp0"
SET "PYTHON_SCRIPT=%SCRIPT_DIR%fixarc-handler"

REM Execute the Python script, passing all arguments
python "%PYTHON_SCRIPT%" %*

REM Exit with the same exit code as the Python script
exit /b %ERRORLEVEL% 