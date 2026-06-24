#!/usr/bin/env bash
# Generate SHA-256 checksums for release artifacts so anyone can verify integrity.
# Usage:  scripts/checksums.sh dist/*.zip > SHA256SUMS
set -euo pipefail
if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi
