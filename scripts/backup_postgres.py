#!/usr/bin/env python3
"""Portable logical PostgreSQL backup without requiring pg_dump."""
import gzip
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
url=os.getenv('DATABASE_URL','').strip()
if not url: raise SystemExit('DATABASE_URL не задан')
out_dir=Path(os.getenv('BACKUP_DIR','/app/data/backups')); out_dir.mkdir(parents=True,exist_ok=True)

import psycopg

stamp=datetime.utcnow().strftime('%Y%m%d_%H%M%S')
out=out_dir/f'problem_net_{stamp}.json.gz'
with psycopg.connect(url) as con:
    with con.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables=[r[0] for r in cur.fetchall()]
        payload={'created_at':datetime.utcnow().isoformat(),'tables':{}}
        for table in tables:
            q='"'+table.replace('"','""')+'"'
            cur.execute(f'SELECT * FROM {q}')
            cols=[d.name for d in cur.description]
            payload['tables'][table]=[dict(zip(cols,row)) for row in cur.fetchall()]
with gzip.open(out,'wt',encoding='utf-8') as fh:
    json.dump(payload,fh,ensure_ascii=False,default=str)
print(out)
