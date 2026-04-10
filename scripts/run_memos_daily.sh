#!/usr/bin/env bash
set -euo pipefail

# English: Bootstrap a Linux-side Python environment for OpenClaw and then
# execute the requested memos_daily_report command.
# 中文：给 Linux / Docker 里的 OpenClaw 自举一套 Python 环境，然后执行
# memos_daily_report 对应命令。

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${VENV_DIR:-${REPO_ROOT}/.venv-linux}"
STAMP_FILE="${VENV_DIR}/.install-stamp"
PYPROJECT_FILE="${REPO_ROOT}/pyproject.toml"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed inside the current environment." >&2
  echo "ERROR: Please extend your OpenClaw Docker image with python3 and python3-venv first." >&2
  exit 127
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  echo "[bootstrap] creating Linux virtualenv at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

# English: Reinstall dependencies whenever the environment is missing or the
# project metadata changed after the last install.
# 中文：如果虚拟环境还没装依赖，或者 pyproject 在上次安装后有变化，就重新安装。
if [ ! -f "${STAMP_FILE}" ] || [ "${PYPROJECT_FILE}" -nt "${STAMP_FILE}" ]; then
  echo "[bootstrap] syncing Python dependencies"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install -e "${REPO_ROOT}"
  touch "${STAMP_FILE}"
fi

export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

exec "${VENV_DIR}/bin/python" -m memos_daily_report "$@"
