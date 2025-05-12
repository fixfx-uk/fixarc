# PowerShell wrapper for the Python-based fixarc-handler.

param (
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$PythonScript = Join-Path -Path $PSScriptRoot -ChildPath 'fixarc-handler'

# Execute the Python script, passing all arguments
& python $PythonScript $Arguments

# Exit with the same exit code as the Python script
exit $LASTEXITCODE 