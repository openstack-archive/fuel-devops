import functools
from time import sleep

def retry(count=10, delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            i = 0
            while True:
                #noinspection PyBroadException
                try:
                    return func(*args, **kwargs)
                except:
                    if i >= count:
                        raise
                    i += 1
                    sleep(delay)
        return wrapper
    return decorator
