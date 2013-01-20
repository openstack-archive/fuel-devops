import functools
from time import sleep

def retry(count=1, delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            i = 0
            while True:
                #noinspection PyBroadException
                try:
                    return func(*args, **kwargs)
                except:
                    i += 1
                    if i >= count:
                        raise
                    sleep(delay)
        return wrapper
    return decorator
