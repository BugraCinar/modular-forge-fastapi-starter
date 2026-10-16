import threading
import time

from redis import Redis
from redis.exceptions import RedisError

from modular_forge.shared.errors import DomainError, unavailable

SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {n, redis.call('TTL', KEYS[1])}
"""


class RedisStore:
    def __init__(self, url):
        self.client = Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        self.script = self.client.register_script(SCRIPT)

    def hit(self, key, window):
        count, ttl = self.script(keys=[key], args=[window])
        return int(count), max(int(ttl), 1)

    def healthy(self):
        try:
            return bool(self.client.ping())
        except RedisError:
            return False

    def close(self):
        self.client.close()


class MemoryStore:
    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()

    def hit(self, key, window):
        now = time.monotonic()
        with self.lock:
            if len(self.values) > 10000:
                self.values = {k: v for k, v in self.values.items() if v[1] > now}
                if len(self.values) > 10000:
                    raise unavailable()
            count, expiry = self.values.get(key, (0, now + window))
            if expiry <= now:
                count, expiry = 0, now + window
            self.values[key] = (count + 1, expiry)
            return count + 1, max(int(expiry - now), 1)

    def healthy(self):
        return True

    def close(self):
        pass


class RateLimiter:
    def __init__(self, settings, security, store=None):
        self.settings, self.security = settings, security
        self.store = store or (
            MemoryStore()
            if settings.rate_limit_backend == "memory"
            else RedisStore(settings.redis_url)
        )

    def check(self, category: str, identity: str, limit: int, window: int):
        key = "modular-forge:limit:" + self.security.token_hash(
            category + ":" + identity, purpose="rate-limit"
        )
        try:
            count, retry = self.store.hit(key, window)
        except RedisError:
            if self.settings.rate_limit_fail_open and self.settings.environment != "production":
                return
            raise unavailable() from None
        if count > limit:
            error = DomainError(429, "rate_limited", "Too many requests. Try again later.")
            error.retry_after = retry
            raise error
