import functools
import logging
import os

from web3.middleware.cache import generate_cache_key
import diskcache

logger = logging.getLogger(__name__)


VERSION = 1
VERSION_CACHE_KEY = 'VERSION'

_cache = None

def check_version():
    version = _cache.get(VERSION_CACHE_KEY, 0)
    if version != VERSION:
        _cache.clear()
        _cache[VERSION_CACHE_KEY] = VERSION
        logger.info(f"Old cache version! Creating new cache with version: {VERSION}")

if not os.environ.get("DEFI_PROTO_CACHE_DISABLE"):
    cache_dir = os.environ.get("DEFI_PROTO_CACHE_DIR", "/tmp/defi_protocols/")
    logger.debug(f"Cache enabled. Storage is at '{cache_dir}'.")
    _cache = diskcache.Cache(directory=cache_dir)
    check_version()
    if os.environ.get("DEFI_PROTO_CLEAN_CACHE"):
        _cache.clear()
else:
    logger.debug(f'Cache is disabled')

def is_enabled():
    return _cache is not None

def clear():
    if is_enabled():
        _cache.clear()

class TemporaryCache:
    """Provides a context with a temporary cache.

    Useful for tests. Not thread safe!
    """
    def __init__(self):
        self.original_cache = _cache

    def __enter__(self):
        global _cache
        _cache = diskcache.Cache()
        return _cache

    def __exit__(self, *args, **kwargs):
        global _cache
        _cache = self.original_cache


def disk_cache_middleware(make_request, web3):
    """
    Cache middleware that supports multiple blockchains.
    It also do not caches if block='latest'.
    """

    RPC_WHITELIST = {'eth_chainId', 'eth_call'}

    def middleware(method, params):
        do_cache = False
        if method in RPC_WHITELIST and 'latest' not in params:
            do_cache = True
        if method == 'eth_chainId':
            do_cache = True

        if do_cache:
            params_hash = generate_cache_key(params)
            cache_key = f"{web3._network_name}.{method}.{params_hash}"
            if cache_key not in _cache:
                response = make_request(method, params)
                if not 'error' in response and 'result' in response and response['result'] is not None:
                    _cache[cache_key] = ('result', response['result'])
                elif 'error' in response:
                    if response['error']['code'] in [-32000, -32015]:
                        _cache[cache_key] = ('error', response['error'])
                return response
            else:
                key, data = _cache[cache_key]
                return {'jsonrpc': '2.0', 'id': 11, key: data}
        else:
            logger.debug(f"Not caching '{method}' with params: '{params}'")
            return make_request(method, params)
    return middleware

def cache_call(exclude_args=None):
    """Decorator to cache the result of a function.

    It has the ability to exclude arguments that the result
    of the call is not dependant.

    In the following example, the function does not depend on the http_client:

    @cache_call(exclude_args=['http_client'])
    def get_pi_digits(http_client, count):
        response = http_client.get(f"https://api.pi.delivery/v1/pi?start=0&numberOfDigits={count}")
        return response["content"]
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            from inspect import getcallargs
            cache_args = getcallargs(f, *args, **kwargs)
            if exclude_args:
                for arg in exclude_args:
                    cache_args.pop(arg)
            cache_key = generate_cache_key((f.__qualname__, cache_args))
            if cache_key not in _cache:
                result = f(*args, **kwargs)
                _cache[cache_key] = result
            else:
                result = _cache[cache_key]
            return result
        return wrapper
    return decorator

def const_call(f):
    """Utility to do .call() on web3 contracts that are known to be cacheable"""
    cache_key = generate_cache_key((f.w3._network_name, f.address, f.function_identifier, f.args, f.kwargs))
    if not is_enabled() or cache_key not in _cache:
        result = f.call()
        if is_enabled():
            _cache[cache_key] = result
    else:
        result = _cache[cache_key]
    return result
