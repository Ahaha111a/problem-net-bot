import os
import time
from collections import defaultdict

try:
    from redis.asyncio import Redis
except Exception:
    Redis = None

LIMIT = int(os.getenv('RATE_LIMIT_PER_MINUTE', '120'))
WINDOW = 60
_local = defaultdict(list)


def _redis():
    url = os.getenv('REDIS_URL', '').strip()
    return Redis.from_url(url, decode_responses=True) if Redis and url else None


async def allowed(key: str) -> bool:
    r = _redis()
    now = int(time.time())
    bucket = f'problem-net:rate:{key}:{now // WINDOW}'
    if r:
        try:
            value = await r.incr(bucket)
            if value == 1:
                await r.expire(bucket, WINDOW + 2)
            await r.aclose()
            return value <= LIMIT
        except Exception:
            try:
                await r.aclose()
            except Exception:
                pass
    items = _local[key]
    cutoff = time.time() - WINDOW
    _local[key] = [x for x in items if x > cutoff]
    if len(_local[key]) >= LIMIT:
        return False
    _local[key].append(time.time())
    return True
