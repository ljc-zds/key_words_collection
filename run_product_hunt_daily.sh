#!/bin/zsh
set -eu

cd '/Users/am/Documents/代码/key_words_collection'
mkdir -p runtime
export AITDK_CDP_URL=http://127.0.0.1:9230
.venv/bin/python browser_sessions.py product-hunt
exec .venv/bin/python product_hunt_daily.py >> runtime/product_hunt_daily.log 2>&1
