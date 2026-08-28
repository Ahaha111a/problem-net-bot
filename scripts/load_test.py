#!/usr/bin/env python3
"""Простое нагрузочное тестирование liveness endpoint.

Пример:
  python scripts/load_test.py https://example.up.railway.app 1000 50
"""
import asyncio
import sys
import time
import aiohttp

async def main():
    if len(sys.argv) < 2:
        raise SystemExit('Использование: python scripts/load_test.py URL [requests=1000] [concurrency=50]')
    url=sys.argv[1].rstrip('/')+'/health'
    total=int(sys.argv[2]) if len(sys.argv)>2 else 1000
    concurrency=int(sys.argv[3]) if len(sys.argv)>3 else 50
    sem=asyncio.Semaphore(concurrency)
    ok=0; failed=0; started=time.perf_counter()
    async with aiohttp.ClientSession() as session:
        async def one():
            nonlocal ok, failed
            async with sem:
                try:
                    async with session.get(url,timeout=10) as r:
                        if r.status==200: ok+=1
                        else: failed+=1
                except Exception: failed+=1
        await asyncio.gather(*(one() for _ in range(total)))
    elapsed=time.perf_counter()-started
    print(f'requests={total} ok={ok} failed={failed} seconds={elapsed:.2f} rps={total/elapsed:.1f}')
    if failed: raise SystemExit(1)

if __name__=='__main__': asyncio.run(main())
