#!/usr/bin/env bash
# Install Strata + IQ2_XS into /srv/share/Strata (root of the 2TB drive).
# Other sizes can be added later with:  ./setup.sh --setup --family qwen --model <SIZE>
#   e.g. ./setup.sh --setup --yes --family qwen --model IQ3_S \
#        --vision gpu --gpus 0,1 --host 0.0.0.0 --api-key "$(cat /srv/share/strata-ops/strata-api-key.txt)" \
#        --data-dir /srv/share/Strata-data --no-start
set -u
cd /srv/share/Strata
DIR="$(cd "$(dirname "$0")" && pwd)"
KEY="$(cat "$DIR/strata-api-key.txt")"
echo "### $(date '+%F %T') installing IQ2_XS"
./setup.sh --yes --family qwen --model IQ2_XS --vision gpu --gpus 0,1 \
  --host 0.0.0.0 --api-key "$KEY" --data-dir /srv/share/Strata-data --no-start
echo "### $(date '+%F %T') DONE (rc=$?)"
