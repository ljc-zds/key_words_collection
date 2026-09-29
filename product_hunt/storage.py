"""Local, transactional Product Hunt results keyed by launch date and source."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path('runtime/product_hunt.sqlite3')

def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE IF NOT EXISTS products (
        published_date TEXT NOT NULL, product_hunt_url TEXT NOT NULL,
        name TEXT, domain TEXT, status TEXT, reason TEXT, row_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (published_date, product_hunt_url))''')
    return db

def upsert(rows, path=DB_PATH):
    from product_hunt.pipeline import row_key, cell_key
    db = connect(path)
    try:
        with db:
            for row in rows:
                key = row_key(row)
                if key is None or len(row) < 20 or key[0] == '发布日期':
                    continue
                db.execute('''INSERT INTO products
                    (published_date,product_hunt_url,name,domain,status,reason,row_json)
                    VALUES (?,?,?,?,?,?,?) ON CONFLICT(published_date,product_hunt_url)
                    DO UPDATE SET name=excluded.name,domain=excluded.domain,
                    status=excluded.status,reason=excluded.reason,row_json=excluded.row_json,
                    updated_at=CURRENT_TIMESTAMP''',
                    (*key,cell_key(row[0]),cell_key(row[3]),cell_key(row[15]),
                     cell_key(row[16]),json.dumps(row,ensure_ascii=False)))
    finally:
        db.close()

def keys(path=DB_PATH):
    db = connect(path)
    try:
        return set(db.execute('SELECT published_date, product_hunt_url FROM products'))
    finally:
        db.close()

def rows_for_date(day, path=DB_PATH):
    db = connect(path)
    try:
        return [json.loads(r[0]) for r in db.execute(
            'SELECT row_json FROM products WHERE published_date=? ORDER BY rowid', (str(day),))]
    finally:
        db.close()
