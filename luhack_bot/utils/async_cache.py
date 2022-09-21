from __future__ import annotations
import functools

from typing import Awaitable, Callable, ParamSpec, Protocol, TypeVar

import cachetools
from cachetools import keys

_Cache = TypeVar("_Cache", bound=cachetools.Cache)
_R = TypeVar("_R", covariant=True)
_P = ParamSpec("_P")


class CachedCallable(Protocol[_P, _R, _Cache]):
    def __call__(self, *args: _P.args, **kwds: _P.kwargs) -> _R:
        ...

    cache: _Cache
    clear: Callable[[], None]


def async_cached(
    cache: _Cache, key=keys.hashkey
) -> Callable[[Callable[_P, Awaitable[_R]]], CachedCallable[_P, Awaitable[_R], _Cache]]:
    def decorator(func: Callable[_P, Awaitable[_R]]):
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            k = key(*args, **kwargs)

            try:
                return cache[k]
            except KeyError:
                pass

            val = await func(*args, **kwargs)

            try:
                cache[k] = val
            except ValueError:
                pass

            return val

        def clear():
            cache.clear()

        wrapper.cache = cache
        wrapper.clear = clear

        wrapper_: CachedCallable[_P, Awaitable[_R], _Cache] = wrapper  # type: ignore

        return functools.update_wrapper(wrapper_, func)

    return decorator
