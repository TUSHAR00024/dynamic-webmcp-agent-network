#!/usr/bin/env bash
set -euo pipefail

# Project root resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

OUTPUT_ZIP="dynamic-webmcp-agent-network.zip"

echo "============================================================="
echo " Packaging Dynamic WebMCP Agent Network for Submission"
echo "============================================================="

# Ensure no uncommitted secrets or changes if committing
if git status --porcelain | grep -E "^\?\? \.env$"; then
    echo "[!] Notice: Local .env detected in working directory (will be EXCLUDED from zip)."
fi

# Remove previous package if exists
rm -f "${OUTPUT_ZIP}"

# Use git archive to guarantee only tracked repo files are included
# This strictly prevents accidental inclusion of .git, .venv, .env, or __pycache__
echo "[+] Creating archive from HEAD via git archive..."
git archive --format=zip --prefix=dynamic-webmcp-agent-network/ HEAD -o "${OUTPUT_ZIP}"

# Verify exclusion of sensitive files in the generated zip
echo "[+] Verifying exclusions in ${OUTPUT_ZIP}..."
if unzip -l "${OUTPUT_ZIP}" | grep -E "((^|/)\.env$|\.git/|\.venv/|__pycache__/|\.DS_Store)"; then
    echo "[✗] ERROR: Forbidden files detected in zip package!"
    exit 1
else
    echo "[✓] Verified: No .env, .git, .venv, or __pycache__ found in package."
fi

# Print size and SHA256 checksum
echo "============================================================="
echo "[✓] Package created successfully: ${OUTPUT_ZIP}"
if command -v du >/dev/null 2>&1; then
    echo "    Size: $(du -h "${OUTPUT_ZIP}" | cut -f1)"
fi

if command -v shasum >/dev/null 2>&1; then
    SHA=$(shasum -a 256 "${OUTPUT_ZIP}" | awk '{print $1}')
    echo "    SHA256: ${SHA}"
elif command -v sha256sum >/dev/null 2>&1; then
    SHA=$(sha256sum "${OUTPUT_ZIP}" | awk '{print $1}')
    echo "    SHA256: ${SHA}"
fi
echo "============================================================="
