#!/usr/bin/env bash
set -Eeuo pipefail

# Enable tracing if DEBUG=1 is set:
#   DEBUG=1 ./wrapper.sh arg1 arg2
[[ "${DEBUG:-0}" == "1" ]] && set -x

# Print a useful error if something fails
trap 'rc=$?; echo "ERROR: ${BASH_SOURCE[0]} failed at line ${LINENO} with exit code ${rc}" >&2; exit "$rc"' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON_SCRIPT="${SCRIPT_DIR}/fixarc-handler"

# Optional: allow overriding python binary
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Debug info
echo "Wrapper starting..." >&2
echo "SCRIPT_DIR:    $SCRIPT_DIR" >&2
echo "PYTHON_SCRIPT: $PYTHON_SCRIPT" >&2
echo "PYTHON_BIN:    $PYTHON_BIN" >&2
echo "ARGS ($#):     $*" >&2

# Sanity checks
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: Python interpreter not found: $PYTHON_BIN" >&2
    exit 127
fi

if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    echo "ERROR: Python script not found: $PYTHON_SCRIPT" >&2
    exit 1
fi

if [[ ! -r "$PYTHON_SCRIPT" ]]; then
    echo "ERROR: Python script is not readable: $PYTHON_SCRIPT" >&2
    exit 1
fi

# Run the Python script
# exec replaces the shell process with Python, which is usually cleaner
exec "$PYTHON_BIN" "$PYTHON_SCRIPT" "$@"