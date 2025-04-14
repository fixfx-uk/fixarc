@echo off
REM Command-line wrapper for the Fix Archive tool on Windows.
REM Usage: fixarchive [args]

REM Get the directory where this batch script is located
SET "SCRIPT_DIR=%~dp0"

REM Go up one directory to get the project root
cd /d "%SCRIPT_DIR%.."
SET "PROJECT_ROOT=%cd%"
cd /d "%SCRIPT_DIR%"

REM Set PYTHONPATH to include the project root
SET "ORIGINAL_PYTHONPATH=%PYTHONPATH%"
SET "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

REM Run the Python module using the hyphenated name
python -m fix-archive.cli %*
SET EXIT_CODE=%ERRORLEVEL%

REM Restore original PYTHONPATH (optional, good practice)
SET "PYTHONPATH=%ORIGINAL_PYTHONPATH%"

REM Exit with the same exit code as the Python script
exit /b %EXIT_CODE% 