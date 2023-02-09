#! /usr/bin/bash

set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

OUT_FILE="$SCRIPT_DIR/../fences/regex/grammar.py"

python3 -m lark.tools.standalone \
        --out "$OUT_FILE" \
        "$SCRIPT_DIR/regex.lark"
