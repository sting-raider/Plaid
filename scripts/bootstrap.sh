#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "$0")/fetch_refs.py"
echo "Reference lab ready under .refs/"
echo "Next: install stable Rust, then run: cargo test --workspace"
