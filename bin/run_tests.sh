#! /usr/bin/bash

set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

cd "$SCRIPT_DIR/.."

coverage run \
         --source=fences \
         --omit=fences/regex/grammar.py \
         -m unittest

coverage html
