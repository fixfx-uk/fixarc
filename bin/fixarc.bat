@echo off
REM Command-line wrapper for the Fix Archive tool on Windows.
REM This script executes the main Python entry point 'fixarc' (the Python script).
REM Logging and output capture should be handled by the calling process or
REM configured within the Python application itself.

SET "SCRIPT_DIR=%~dp0"
REM PYTHON_EXECUTABLE_SCRIPT should point to the 'fixarc' Python script in the same directory
SET "PYTHON_EXECUTABLE_SCRIPT=%SCRIPT_DIR%fixarc"

REM Execute the Python script, passing all arguments.
REM Stdout and stderr will be inherited or captured by the caller.
REM Ensuring python is called explicitly if 'fixarc' is not directly executable
REM or to be certain. If 'fixarc' is a .py file and associated, this works.
REM If 'fixarc' is a script that needs 'python' to run it, this is also fine.
python "%PYTHON_EXECUTABLE_SCRIPT%" %*

REM Exit with the same exit code as the Python script
exit /b %ERRORLEVEL% 