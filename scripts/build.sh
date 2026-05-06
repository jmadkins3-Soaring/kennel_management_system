#!/usr/bin/env bash
# Alias entry point — delegates to the root build.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/../build.sh" "$@"
