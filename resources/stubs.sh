#!/bin/bash

ROOT="C:/Users/robin.d/Documents/dev/pipe/fix-archive"

FILES=(
  "__init__.py"
  "cli.py"
  "parser.py"
  "archiver.py"
  "repath.py"
  "gizmobake.py"
  "utils.py"
  "exceptions.py"
  "constants.py"
  "README.md"
  "tests/__init__.py"
  "tests/test_cli.py"
  "tests/test_parser.py"
  "tests/test_archiver.py"
  "tests/test_repath.py"
  "tests/test_gizmobake.py"
  "tests/fixtures/test_basic.nk"
  "tests/fixtures/test_gizmo.nk"
  "tests/fixtures/test_deep.nk"
  "tests/fixtures/plate.1001.exr"
  "tests/fixtures/plate.1002.exr"
  "tests/fixtures/model.abc"
)

echo "Creating fix-archive structure at $ROOT..."

for file in "${FILES[@]}"; do
  FILE_PATH="$ROOT/$file"
  DIR_PATH=$(dirname "$FILE_PATH")
  if [ ! -d "$DIR_PATH" ]; then
    mkdir -p "$DIR_PATH"
    echo "Created directory: $DIR_PATH"
  fi
  if [ ! -f "$FILE_PATH" ]; then
    touch "$FILE_PATH"
    echo "Created file: $FILE_PATH"
  fi
done

echo "✅ fix-archive structure created."
