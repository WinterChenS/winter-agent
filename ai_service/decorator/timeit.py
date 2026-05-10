import inspect
import time
from functools import wraps


def timeit(func):
    if inspect.isasyncgenfunction(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            print(f'started {func.__name__}, start_at: {start}')
            result = func(*args, **kwargs)
            end = time.time()
            print(f'finished {func.__name__}, end_at: {end}')
            return result
        return wrapper
    elif inspect.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            print(f'started {func.__name__}, start_at: {start}')
            result = await func(*args, **kwargs)
            end = time.time()
            print(f'finished {func.__name__}, end_at: {end}')
            return result
        return wrapper
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            print(f'started {func.__name__}, start_at: {start}')
            result = func(*args, **kwargs)
            end = time.time()
            print(f'finished {func.__name__}, end_at: {end}')
            return result
        return wrapper