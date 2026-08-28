#!/usr/bin/env python3
"""Восстановление JSON.gz резервной копии PostgreSQL, созданной ботом."""
import gzip
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
url=os.getenv('DATABASE_URL','').strip()
if not url: raise SystemExit('DATABASE_URL не задан')
if len(sys.argv)!=2: raise SystemExit('Использование: python scripts/restore_postgres.py backup.json.gz')

os.environ['DATABASE_URL']=url
from backend import database as db

db.init_db()
with gzip.open(sys.argv[1],'rt',encoding='utf-8') as fh:
    payload=json.load(fh)

import psycopg
with psycopg.connect(url) as con:
    with con.cursor() as cur:
        for table, rows in payload.get('tables',{}).items():
            if not rows: continue
            columns=list(rows[0].keys())
            qtable='"'+table.replace('"','""')+'"'
            qcols=', '.join('"'+c.replace('"','""')+'"' for c in columns)
            placeholders=', '.join(['%s']*len(columns))
            sql=f'INSERT INTO {qtable} ({qcols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            for row in rows: cur.execute(sql,[row.get(c) for c in columns])
    con.commit()
print('Восстановление завершено.')
