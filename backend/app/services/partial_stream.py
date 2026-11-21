"""Bounded Redis transport. A session has exactly one ordered consumer."""

import hashlib
import time
from collections.abc import Iterator

from redis import Redis

from app.core.config import settings

TTL = 4 * 3600
MAX_CHUNK = 1024 * 1024
MAX_QUEUED = 8 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_SECONDS = 2 * 3600


def client() -> Redis:
    return Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=5)


def keys(session_id: str) -> tuple[str, str, str, str]:
    base = f"partial:{{{session_id}}}"
    return base + ":meta", base + ":queue", base + ":hashes", base + ":lock"


def initialize(session_id: str) -> None:
    meta, _, _, _ = keys(session_id)
    with client() as redis:
        redis.hset(meta, mapping={
            "state": "open", "next": 0, "queued": 0, "total": 0,
            "client": time.time(), "heartbeat": time.time(),
        })
        redis.expire(meta, TTL)


# SHA comparison distinguishes retries from conflicting reuse of a sequence.
_APPEND = """
if redis.call('EXISTS', KEYS[1]) == 0 then return -410 end
local n = tonumber(redis.call('HGET', KEYS[1], 'next'))
local seq = tonumber(ARGV[1])
if seq < n then
  if redis.call('HGET', KEYS[3], ARGV[1]) == ARGV[2] then return n end
  return -409
end
if redis.call('HGET', KEYS[1], 'state') ~= 'open' then return -410 end
if seq ~= n then return -409 end
local size = string.len(ARGV[3])
if tonumber(redis.call('HGET', KEYS[1], 'queued')) + size > tonumber(ARGV[4]) then return -429 end
if tonumber(redis.call('HGET', KEYS[1], 'total')) + size > tonumber(ARGV[5]) or n >= 7200 then return -413 end
redis.call('RPUSH', KEYS[2], ARGV[3])
redis.call('HSET', KEYS[3], ARGV[1], ARGV[2])
redis.call('HSET', KEYS[1], 'next', n + 1, 'client', ARGV[7])
redis.call('HINCRBY', KEYS[1], 'queued', size)
redis.call('HINCRBY', KEYS[1], 'total', size)
for i = 1, 3 do redis.call('EXPIRE', KEYS[i], ARGV[6]) end
return n + 1
"""


def append(session_id: str, sequence: int, data: bytes) -> int:
    with client() as redis:
        return int(redis.eval(
            _APPEND, 3, *keys(session_id)[:3], sequence,
            hashlib.sha256(data).hexdigest(), data, MAX_QUEUED, MAX_TOTAL, TTL,
            time.time(),
        ))


def finish(session_id: str, count: int) -> int:
    with client() as redis:
        return int(redis.eval("""
if redis.call('EXISTS', KEYS[1]) == 0 then return -410 end
if tonumber(redis.call('HGET', KEYS[1], 'next')) ~= tonumber(ARGV[1]) then return -409 end
redis.call('HSET', KEYS[1], 'state', 'closing', 'client', ARGV[2])
return 0
""", 1, keys(session_id)[0], count, time.time()))


def purge(session_id: str) -> None:
    # Keep the consumer lease until that task exits, preventing a second reader.
    with client() as redis:
        redis.delete(*keys(session_id)[:3])


def touch_client(session_id: str) -> None:
    """Atualiza o timestamp de atividade do cliente e renova o TTL da sessão."""
    meta = keys(session_id)[0]
    with client() as redis:
        redis.eval(
            """
if redis.call('EXISTS', KEYS[1]) == 1 and redis.call('HGET', KEYS[1], 'state') == 'open' then
  redis.call('HSET', KEYS[1], 'client', ARGV[1])
  redis.call('EXPIRE', KEYS[1], ARGV[2])
end
""",
            1,
            meta,
            time.time(),
            TTL,
        )


class StreamClosed(Exception):
    pass


def chunks(session_id: str, redis: Redis) -> Iterator[bytes]:
    meta, queue, _, _ = keys(session_id)
    started = time.monotonic()
    # Bounded drain after stop; closing no longer depends on client heartbeat.
    while time.monotonic() - started < MAX_SECONDS + 1800:
        info = redis.hgetall(meta)
        if not info:
            raise StreamClosed("Sessão cancelada ou expirada")
        if info.get(b"state") == b"open":
            if time.monotonic() - started >= MAX_SECONDS:
                raise TimeoutError("Limite de duas horas para captura parcial")
            if time.time() - float(info.get(b"client", 0)) > 120:
                raise TimeoutError("Cliente desconectado por mais de 120s")
        if not redis.eval('''
if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
redis.call('HSET', KEYS[1], 'heartbeat', ARGV[1])
return 1
''', 1, meta, time.time()):
            raise StreamClosed("Sessão cancelada")
        data = redis.eval("""
local data = redis.call('LPOP', KEYS[2])
if data and redis.call('EXISTS', KEYS[1]) == 1 then
  redis.call('HINCRBY', KEYS[1], 'queued', -string.len(data))
end
return data
""", 2, meta, queue)
        if data is not None:
            yield data
        elif info.get(b"state") == b"closing":
            return
        else:
            time.sleep(0.2)
    raise TimeoutError("Limite de duas horas para parciais atingido")
