#!/bin/bash
# Bash wrapper for the Python-based fixarc-handler.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_SCRIPT="${SCRIPT_DIR}/fixarc-handler"

# Execute the Python script, passing all arguments
python "$PYTHON_SCRIPT" "$@"