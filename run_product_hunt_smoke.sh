#!/bin/zsh
set -eu

cd '/Users/am/Documents/代码/key_words_collection'
test -f .env
test -x .venv/bin/python
exec .venv/bin/python -m py_compile product_hunt_daily.py aitdk_enrichment/tabapi.py
