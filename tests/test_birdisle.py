import time
import threading
import locale
import socket
import resource

import redis
import birdisle
import pytest


@pytest.fixture
def r():
    return birdisle.StrictRedis(singleton=False)


@pytest.fixture
def limit_fds():
    """Reduce the maximum allowed file descriptors."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    new_soft = min(hard, 128)
    resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
    yield new_soft
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_simple(r):
    r.set('hello', 'world')
    assert r.get('hello') == b'world'


def test_repr(r):
    repr(r)


def test_locale():
    try:
        locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    except locale.Error:
        pytest.skip()
    # Confirm that this is a locale which doesn't use the decimal point
    assert locale.format('%g', 1.5) == '1,5'
    r = birdisle.StrictRedis()
    r.set('foo', b'1.5')
    r.incrbyfloat('foo', b'0.25')
    assert r.get('foo') == b'1.75'
    # Check that birdisle hasn't overridden this thread's locale
    assert locale.format('%g', 1.5) == '1,5'


def test_lua(r):
    r.set('foo', 'bar')
    script = r.register_script("return redis.call('GET', KEYS[1])")
    result = script(['foo'])
    assert result == b'bar'


def test_info(r):
    """Test that the INFO command works"""
    r.info()


def test_blocking(r):
    def worker(r):
        time.sleep(0.1)
        r.rpush('foo', 'bar')

    thread = threading.Thread(target=worker, args=(r,))
    thread.start()
    result = r.blpop('foo')
    assert result == (b'foo', b'bar')
    thread.join()


def test_fd_leak(limit_fds):
    """Servers must not leak file descriptors"""
    for i in range(limit_fds + 1):
        server = birdisle.Server()
        client = server.connect()
        server.close()
        client.close()


def test_singleton():
    a = birdisle.StrictRedis()
    b = birdisle.StrictRedis()
    a.flushall()
    b.flushall()
    a.set('foo', 'bar')
    assert b.get('foo') == b'bar'


def test_non_strict():
    r = birdisle.Redis(singleton=False)
    r.zadd('foo', 'bar', 3)
    assert r.zrange('foo', 0, -1, withscores=True) == [(b'bar', 3)]
