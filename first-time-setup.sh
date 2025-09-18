#!/usr/bin/env bash
set -euo pipefail

# --- Config -------------------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
REQ_FILE="${PROJECT_DIR}/requirements.txt"
USER_NAME="$(whoami)"
CURRENT_DIR="$(pwd)"

echo "==> Updating apt package lists…"
sudo apt-get update -y

echo "==> Installing system packages…"
# Notes:
# - python3-venv / python3-pip: create & use venv
# - build-essential / python3-dev / libffi-dev: compile wheels when needed
# - ffmpeg: for pydub / whisper audio I/O
# - portaudio19-dev: for PyAudio (if you use it)
# - vlc + python3-vlc: libVLC + Python bindings (yes, python3-vlc is a real apt pkg)
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  libffi-dev \
  ffmpeg \
  portaudio19-dev \
  vlc \
  python3-vlc

echo "==> Python: creating venv at ${VENV_DIR} (if missing)…"
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

echo "==> Activating venv…"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "==> Upgrading pip/setuptools/wheel…"
python -m pip install --upgrade pip setuptools wheel

if [[ -f "${REQ_FILE}" ]]; then
  echo "==> Installing Python dependencies from ${REQ_FILE}…"
  python -m pip install -r "${REQ_FILE}"
else
  echo "!! ${REQ_FILE} not found. Skipping pip install."
  echo "   Create it or run:  python -m pip freeze > requirements.txt"
fi

echo "==> Quick import sanity checks (non-fatal)…"
python - <<'PY' || true
mods = ["fastapi","uvicorn","pydub","dotenv","whisper","vlc","socketio","PIL","gtts"]
import importlib
missing = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        missing.append((m, str(e)))
if missing:
    print("Missing/errored modules:")
    for m, err in missing:
        print(f" - {m}: {err}")
else:
    print("All sanity-check imports loaded.")
PY

echo ""
echo -e "\033[32m==> Done.\033[0m"
echo "Tips:"
echo "  - Activate your venv next time with:  source venv/bin/activate"
echo "  - If you rely on a .env file, copy it now:"
echo "      scp .env ${USER_NAME}@<PI_IP>:${CURRENT_DIR}/.env"
