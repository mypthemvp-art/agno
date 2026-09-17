#!/usr/bin/env bash
#
# Idempotent Cloud Agent bootstrap for the Agno repo.
#
# Creates the two project virtualenvs described in AGENTS.md:
#   .venv        -> development: pytest, ./scripts/format.sh, ./scripts/validate.sh
#   .venvs/demo  -> cookbooks/examples (agno[demo]) + agno[evm] for the
#                   startup_stock blockchain MVP CLI and examples.
#
# Safe to re-run: the setup scripts recreate each venv and uv resolves from cache.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# Ensure uv (used by the dev/demo setup scripts) is installed and on PATH.
export PATH="${HOME}/.local/bin:${PATH}"
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
fi
uv --version

# Development venv (.venv): tests, formatting, validation.
echo "Setting up .venv (dev)..."
./scripts/dev_setup.sh

# Demo venv (.venvs/demo): cookbooks + examples.
echo "Setting up .venvs/demo (demo)..."
./scripts/demo_setup.sh

# The startup_stock blockchain MVP needs web3 (the agno[evm] extra).
echo "Installing agno[evm] into the demo venv..."
VIRTUAL_ENV="${REPO_ROOT}/.venvs/demo" uv pip install -e "libs/agno[evm]"

echo "Environment setup complete."
