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
  echo "ERROR: Please extend your OpenClaw Docker image with python3 first." >&2
  exit 127
fi

create_linux_venv() {
  # English: Prefer the stdlib venv module, but fall back to virtualenv for
  # Alpine-style images where `python3 -m venv` may be unavailable.
  # 中文：优先使用标准库 venv；如果是 Alpine 这类环境不带 venv，就退回到 virtualenv。
  if python3 -m venv "${VENV_DIR}" >/dev/null 2>&1; then
    return 0
  fi

  if python3 -m virtualenv "${VENV_DIR}" >/dev/null 2>&1; then
    return 0
  fi

  echo "ERROR: failed to create a virtual environment." >&2
  echo "ERROR: install either Python venv support or the virtualenv package in your image." >&2
  exit 1
}

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  echo "[bootstrap] creating Linux virtualenv at ${VENV_DIR}"
  create_linux_venv
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
