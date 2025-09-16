from redis import Redis, from_url
import os

def _create_redis_client() -> Redis:
    url = os.getenv("REDIS_URL")
    if url:
        return from_url(url, decode_responses=True)
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return Redis(host=host, port=port, decode_responses=True)


redis_client = _create_redis_client()
