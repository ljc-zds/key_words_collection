#!/bin/zsh
cd '/Users/am/Documents/代码/key_words_collection' || exit 1
export PYTHONPATH=.
.venv/bin/python browser_sessions.py google-trends || exit 1
exec '/Users/am/Documents/代码/key_words_collection/.venv/bin/python' -m trend_radar.cli \
  --roots-feishu-url 'https://my.feishu.cn/wiki/Vwo7wNFp3ivv5okIQVKciPgGnCd?from=from_copylink' \
  --limit 20 \
  --cdp-url http://127.0.0.1:9229 \
  --output '/Users/am/Documents/代码/key_words_collection/output/trend-radar-dfs-20-unbounded-v6.json'
