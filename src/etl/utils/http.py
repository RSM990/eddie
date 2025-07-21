# src/etl/utils/http.py

import time
from functools import wraps
import requests

def rate_limited(max_calls: int, period: float = 60.0):
    """
    Decorator to ensure the wrapped function is called at most `max_calls`
    times per `period` seconds. Sleeps as needed to enforce the rate.
    """
    min_interval = period / float(max_calls)
    def decorator(func):
        last_time = [0.0]  # mutable closure

        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_time[0]
            wait = min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            result = func(*args, **kwargs)
            last_time[0] = time.time()
            return result

        return wrapper
    return decorator


def get_session(user_agent: str) -> requests.Session:
    """
    Create a requests.Session with common headers, retries, etc.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    # you can also configure retries here if you like
    return session
