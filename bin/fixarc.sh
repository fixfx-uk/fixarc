#!/bin/bash
# Command-line wrapper for the Fix Archive tool on Unix-like systems.
# Usage: fixarc [args]

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Path to the main Python executable script
PYTHON_EXECUTABLE_SCRIPT="${SCRIPT_DIR}/fixarc"

# Execute the main Python executable script, passing all arguments
# This script is responsible for setting up its own environment, including fixenv.
"$PYTHON_EXECUTABLE_SCRIPT" "$@" 