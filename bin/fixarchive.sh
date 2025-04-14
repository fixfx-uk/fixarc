#!/bin/bash
# Command-line wrapper for the Fix Archive tool on Unix-like systems.
# Usage: fixarchive [args]

# Get the directory where this script is located
SCRIPT_DIR="$( cd "\"$( dirname "\"${BASH_SOURCE[0]}\"" )\"" &> /dev/null && pwd )"

# Get the project root directory (one level up)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Prepend the project root to PYTHONPATH for this command's execution
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Execute the Python module using the hyphenated name, passing all arguments
python -m fix-archive.cli "$@" 