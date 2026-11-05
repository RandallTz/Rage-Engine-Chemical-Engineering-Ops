"""Request-local optimization policy, independent of physics and numerical models."""
from contextlib import contextmanager
from contextvars import ContextVar

_enabled = ContextVar('preparation_cache_enabled', default=True)


def enabled():
    return _enabled.get()


@contextmanager
def preparation_policy(*, cached):
    token = _enabled.set(bool(cached))
    try:
        yield
    finally:
        _enabled.reset(token)
