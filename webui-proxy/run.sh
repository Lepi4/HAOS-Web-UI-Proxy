#!/usr/bin/with-contenv bash
set -euo pipefail

python3 /app/generate.py

exec nginx -g 'daemon off;'
