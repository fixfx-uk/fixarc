@echo off
REM Command-line wrapper for the Fix Archive tool on Windows.
REM Usage: fixarchive [args]

REM Get the directory where this batch script is located
SET "SCRIPT_DIR=%~dp0"

REM Path to the main Python executable script
SET "PYTHON_EXECUTABLE_SCRIPT=%SCRIPT_DIR%fixarc"

REM Execute the main Python executable script, passing all arguments
REM This script is responsible for setting up its own environment, including fixenv.
"%PYTHON_EXECUTABLE_SCRIPT%" %*

REM Exit with the same exit code as the Python script
exit /b %ERRORLEVEL% 