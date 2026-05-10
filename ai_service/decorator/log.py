from functools import wraps
import inspect

def log(func):
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            print(f'log before: {func.__name__}, method: {func.__qualname__}, args: {args}, kwargs: {kwargs}')
            result = await func(*args, **kwargs)
            print(f'log after: {func.__name__}, method: {func.__qualname__}, result: {result}')
            return result
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            print("log before")
            result = func(*args, **kwargs)
            print("log after")
            return result
        return sync_wrapper