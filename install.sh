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

# agy reads its settings from ~/.gemini/antigravity-cli/settings.json. Writing to
# ~/.gemini/config/settings.json created a file agy never loads, so the statusline
# was installed but never appeared. Prefer the real location, and only fall back to
# the legacy path if the antigravity-cli directory is genuinely absent.
if [ -f "${HOME}/.gemini/antigravity-cli/settings.json" ] || [ -d "${HOME}/.gemini/antigravity-cli" ]; then
  SETTINGS_FILE="${HOME}/.gemini/antigravity-cli/settings.json"
elif [ -f "${HOME}/.gemini/config/settings.json" ]; then
  SETTINGS_FILE="${HOME}/.gemini/config/settings.json"
else
  SETTINGS_FILE="${HOME}/.gemini/antigravity-cli/settings.json"
fi
echo "==> Using agy settings file: ${SETTINGS_FILE}"

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

# The statusline is rendered by agy itself, and its quota segments are read from
# `agy -p /usage`. Without agy nothing ever invokes this script.
ANTIGRAVITY_URL="https://antigravity.google/"
AUTO_MODE_URL="https://github.com/marmarmamark/agy-auto-mode"

agy_installed() {
  command -v agy >/dev/null 2>&1 && return 0
  for c in "${HOME}/.local/bin/agy" \
           "${HOME}/.antigravity-ide/antigravity-ide/bin/agy" \
           "/usr/local/bin/agy" \
           "/opt/homebrew/bin/agy"; do
    [ -x "${c}" ] && return 0
  done
  return 1
}

if agy_installed; then
  echo "==> Detected Antigravity CLI (agy)"
else
  echo ""
  echo "------------------------------------------------------------------"
  echo " Missing dependency: Google Antigravity (agy)"
  echo ""
  echo " agy renders this statusline and supplies the quota data it shows."
  echo " Without it the script is installed but never runs."
  echo ""
  echo " Download Antigravity: ${ANTIGRAVITY_URL}"
  echo "------------------------------------------------------------------"
  if [ -t 0 ] && [ "${AUTO_CONFIRM}" = false ]; then
    read -r -p " Install anyway (ready for when agy is installed)? [y/N]: " CONTINUE_NO_AGY
    case "${CONTINUE_NO_AGY}" in
      [Yy]*) echo "==> Continuing without agy." ;;
      *)
        echo "==> Aborted. Install Antigravity first, then re-run this installer."
        exit 1
        ;;
    esac
  else
    echo "==> Continuing without agy (non-interactive). Install Antigravity to activate the statusline."
  fi
  echo ""
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

# Merge, do not replace: users set extra statusLine keys (e.g. stack_with_default)
# and a wholesale assignment silently drops them.
status_line = data.get("statusLine")
if not isinstance(status_line, dict):
    status_line = {}
status_line["type"] = "command"
status_line["command"] = f"python3 {script_path}"
data["statusLine"] = status_line

# Atomic write: settings.json also carries permissions, so a partial write on
# interruption would be worse than no write at all.
tmp = settings_path + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
os.replace(tmp, settings_path)
'

echo "==> Successfully updated ${SETTINGS_FILE}"

# Self-test. The cache path is redirected: the statusline persists whatever payload
# it is handed, and writing these sample numbers to the real cache would leave
# agy-auto-resume and gemini-worker reading a fabricated 85% quota.
echo "==> Testing statusline execution with sample payload..."
SELFTEST_CACHE="$(mktemp "${TMPDIR:-/tmp}/agy_statusline_selftest.XXXXXX")"
TEST_PAYLOAD='{"context_window":{"used_percentage":28.0},"quota":{"gemini-5h":{"remaining_fraction":0.85,"reset_in_seconds":3600},"gemini-weekly":{"remaining_fraction":0.95}},"terminal_width":80}'
OUTPUT=$(printf '%s' "${TEST_PAYLOAD}" | STATUSLINE_CACHE_PATH="${SELFTEST_CACHE}" python3 "${TARGET_FILE}")
rm -f "${SELFTEST_CACHE}" "${SELFTEST_CACHE}.tmp"
echo "==> Preview:"
echo "${OUTPUT}"
# The "Auto: N left" segment reads the classifier's usage ledger. It is optional,
# but silently omitting the segment reads as a bug, so say why it is not there.
if [ ! -f "${HOME}/.gemini/config/classifier_usage.json" ] \
   && [ ! -d "${HOME}/.gemini/config/plugins/agy-auto-mode" ]; then
  echo ""
  echo "------------------------------------------------------------------"
  echo " Optional: agy-auto-mode is not installed."
  echo ""
  echo " The statusline works without it, but the 'Auto: N left' segment"
  echo " (remaining daily auto-mode classifier requests) will be hidden,"
  echo " because there is no classifier usage ledger to read."
  echo ""
  echo " Get it here: ${AUTO_MODE_URL}"
  echo "------------------------------------------------------------------"
fi

echo ""
echo "==> Antigravity Statusline installed successfully!"
echo "    Start or restart 'agy' to see your new statusline."
