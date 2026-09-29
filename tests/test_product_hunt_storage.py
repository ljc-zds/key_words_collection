from product_hunt import storage
from product_hunt.pipeline import filter_unseen_products
from product_hunt.aitdk.product.product_hunt import ProductCandidate

def test_date_source_dedup_and_retry_update(tmp_path):
    path = tmp_path / 'results.sqlite3'
    row = [''] * 20
    row[0], row[6], row[15], row[17] = 'Test', '2026-09-09', 'error', 'https://ph/test'
    storage.upsert([row], path)
    row[15] = 'Success'
    storage.upsert([row], path)
    assert len(storage.keys(path)) == 1
    assert storage.rows_for_date('2026-09-09', path)[0][15] == 'Success'
    candidates = [ProductCandidate('1','Test','',row[17],'https://test.com','test.com',day,0)
                  for day in ('2026-09-09', '2026-09-10')]
    assert filter_unseen_products(candidates, storage.keys(path)) == candidates[1:]
    row[6] = '2026-09-10'
    storage.upsert([row], path)
    assert len(storage.keys(path)) == 2
