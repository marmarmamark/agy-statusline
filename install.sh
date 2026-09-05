#!/usr/bin/env bash
#
# Antigravity Statusline Installer
# --------------------------------
# Installs and configures the Claude Code-style statusline for Antigravity (agy).
#
set -euo pipefail

AUTO_CONFIRM=false
UNINSTALL=false

for arg in "$@"; do
  case "${arg}" in
    -y|--yes|--non-interactive)
      AUTO_CONFIRM=true
      ;;
    --uninstall)
      UNINSTALL=true
      ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.gemini/config/scripts"
TARGET_FILE="${TARGET_DIR}/statusline.py"
SETTINGS_FILE="${HOME}/.gemini/config/settings.json"

if [ "${UNINSTALL}" = true ]; then
  echo "==> Uninstalling agy-statusline..."
  rm -f "${TARGET_FILE}"
  if [ -f "${SETTINGS_FILE}" ]; then
    SETTINGS_PATH="${SETTINGS_FILE}" python3 -c '
import json, os
path = os.environ["SETTINGS_PATH"]
if os.path.exists(path):
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if "statusLine" in data:
            del data["statusLine"]
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            print("==> Removed statusLine from settings.json")
    except Exception as e:
        print(f"Warning: Could not update settings.json: {e}")
'
  fi
  echo "==> agy-statusline uninstalled successfully."
  exit 0
fi

echo "==> Antigravity Statusline Installer"

# Verify Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found in PATH." >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"
cp "${REPO_DIR}/statusline.py" "${TARGET_FILE}"
chmod +x "${TARGET_FILE}"
echo "==> Installed statusline script to ${TARGET_FILE}"

# Configure Antigravity settings.json
echo "==> Configuring Antigravity settings..."
mkdir -p "$(dirname "${SETTINGS_FILE}")"
SETTINGS_PATH="${SETTINGS_FILE}" SCRIPT_PATH="${TARGET_FILE}" python3 -c '
import json, os

settings_path = os.environ["SETTINGS_PATH"]
script_path = os.environ["SCRIPT_PATH"]

data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path, "r") as f:
            data = json.load(f)
    except Exception:
        data = {}

data["statusLine"] = {
    "type": "command",
    "command": f"python3 {script_path}"
}

with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
'

echo "==> Successfully updated ${SETTINGS_FILE}"

# Self-test
echo "==> Testing statusline execution with sample payload..."
TEST_PAYLOAD='{"context_window":{"used_percentage":28.0},"quota":{"gemini-5h":{"remaining_fraction":0.85,"reset_in_seconds":3600},"gemini-weekly":{"remaining_fraction":0.95}},"terminal_width":80}'
OUTPUT=$(printf '%s' "${TEST_PAYLOAD}" | python3 "${TARGET_FILE}")
echo "==> Preview:"
echo "${OUTPUT}"
echo ""
echo "==> Antigravity Statusline installed successfully!"
echo "    Start or restart 'agy' to see your new statusline."
