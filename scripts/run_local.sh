#!/usr/bin/env bash
set -euo pipefail

# Best-effort local runner that prefers Python 3.11 via pyenv.
# If pyenv is available it will install/use Python 3.11.16. If not,
# and Homebrew is available, the script will attempt to install pyenv.
# Otherwise the script falls back to the system python and prints guidance.

PY_VER=3.11.16

command_exists() { command -v "$1" >/dev/null 2>&1; }

echo "Checking Python version..."
if command_exists python3; then
  SYS_PY=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  echo "System python: $SYS_PY"
else
  echo "python3 not found on PATH. Please install Python or use Docker." >&2
  exit 1
fi

PYTHON_BIN=""
if [ "$SYS_PY" = "3.11" ]; then
  PYTHON_BIN=$(command -v python3)
  echo "Using system Python 3.11"
else
  if command_exists pyenv; then
    echo "pyenv found — ensuring Python $PY_VER is installed"
    if pyenv versions --bare | grep -q "^${PY_VER}$"; then
      PYTHON_BIN="$(pyenv root)/versions/${PY_VER}/bin/python3"
      echo "Using pyenv Python at $PYTHON_BIN"
    else
      echo "Installing Python $PY_VER with pyenv (may take a few minutes)..."
      if pyenv install -s ${PY_VER}; then
        PYTHON_BIN="$(pyenv root)/versions/${PY_VER}/bin/python3"
      else
        echo "pyenv install failed — ensure build deps are present (openssl, readline, zlib)." >&2
      fi
    fi
  else
    if command_exists brew; then
      echo "Homebrew found — installing pyenv"
      brew update || true
      brew install pyenv
      echo "Restarting shell may be required; continuing with this shell's pyenv"
      if pyenv install -s ${PY_VER}; then
        PYTHON_BIN="$(pyenv root)/versions/${PY_VER}/bin/python3"
      else
        echo "pyenv install failed — please install build dependencies and re-run the script." >&2
      fi
    else
      echo "pyenv and Homebrew not found. Falling back to system python (may be incompatible)." >&2
    fi
  fi
fi

if [ -z "${PYTHON_BIN}" ]; then
  echo "Using system python3 at $(command -v python3)"
  PYTHON_BIN=$(command -v python3)
fi

echo "Creating virtualenv with: $PYTHON_BIN"
# If the chosen python lives inside an existing .venv, reuse it instead of deleting it.
if [[ "${PYTHON_BIN}" == *".venv"* ]]; then
  echo "Detected active .venv; reusing existing virtualenv"
  # activate the existing venv
  # shellcheck disable=SC1090
  source ".venv/bin/activate"
else
  rm -rf .venv
  "${PYTHON_BIN}" -m venv .venv
  # shellcheck disable=SC1090
  source ".venv/bin/activate"
fi
pip install --upgrade pip
pip install -r requirements.txt

# Start uvicorn to serve API + static frontend (frontend served at /)
uvicorn src.api_placeholder:app --host 0.0.0.0 --port 8000
