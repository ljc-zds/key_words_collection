"""Reclassify existing Feishu rows after the status taxonomy change."""

from product_hunt_daily import failure_status
from write_feishu_batch import SHEET_ID, SPREADSHEET_TOKEN, load_env, request_json, tenant_token


token = tenant_token(load_env())
read = request_json(
    f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}/values/{SHEET_ID}!A2:O51',
    method='GET', payload={}, token=token,
)
rows = read['data']['valueRange']['values']
for row in rows:
    if row[12] == 'failed':
        row[12] = failure_status(row[13])
write = request_json(
    f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}/values',
    method='PUT', payload={'valueRange': {'range': f'{SHEET_ID}!A2:O51', 'values': rows}}, token=token,
)
if write.get('code') != 0:
    raise RuntimeError('Feishu reclassification failed')
print(f'reclassified {len(rows)} rows')
