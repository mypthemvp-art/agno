#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Packaging strategyiq-final..."

if [[ ! -d strategyiq-final ]]; then
  echo "Error: strategyiq-final/ not found. Run from repo root."
  exit 1
fi

rm -f strategyiq-final.zip
zip -r strategyiq-final.zip strategyiq-final \
  -x "*.pyc" "*__pycache__*" "*.git*" "*.pytest_cache*" "strategyiq-final/.env"

COUNT=$(find strategyiq-final -type f | wc -l)
echo "Created strategyiq-final.zip with ${COUNT} files"
echo "Next: cd strategyiq-final && vercel --prod --cwd frontend"
