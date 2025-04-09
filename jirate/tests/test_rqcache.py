#!/usr/bin/python3
import copy
import os
import time

import pytest  # NOQA

from jirate.rqcache import RequestCache
import jirate.rqcache


class TestSession(object):
    def request(self, method, url, **kwargs):
        return {'value': os.urandom(16), 'resp': 200}

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def put(self, url, **kwargs):
        return self.request('PUT', url, **kwargs)
    """ Uncomment when needed; disabled for coverage
    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)
    """


# Overwrite ResilientSession import
jirate.rqcache.ResilientSession = TestSession


def test_rqcache_nomatch():
    session = TestSession()
    cache = RequestCache(session, filename=None, expire=10)  # NOQA
    # url1 is not matched by our paths so it should always
    # be a cache miss
    ret1 = session.get('url1')
    ret2 = session.get('url1')
    assert ret1 != ret2

    session.put('url2')


def test_rqcache_match():
    session = TestSession()
    cache = RequestCache(session, filename=None, expire=10)  # NOQA
    # /field is a match, so we should get the cached data on
    # the second pull
    ret1 = session.get('https://whatever/rest/api/2/field', params={'data': '1'})
    ret2 = session.get('https://whatever/rest/api/2/field', params={'data': '2'})
    ret3 = session.get('https://whatever/rest/api/2/field', params={'data': '1'})
    ret4 = session.get('https://whatever/rest/api/2/field', params={'data': '2'})
    ret5 = session.get('https://whatever/rest/api/2/field', params={'data': '3'})

    assert ret1 != ret2
    assert ret1 == ret3
    assert ret2 == ret4
    assert ret1 != ret5
    assert ret2 != ret5

    cache.debug_dump()


def test_rqcache_match_expire():
    session = TestSession()
    cache = RequestCache(session, filename=None, expire=1)  # NOQA
    # We expire in 1 second, so second pull should have new
    # data
    ret1 = session.get('https://whatever/rest/api/2/field')
    time.sleep(1.1)
    ret2 = session.get('https://whatever/rest/api/2/field')

    assert ret1 != ret2


def test_rqcache_purge_expired():
    session = TestSession()
    cache = RequestCache(session, filename=None, expire=1)
    # Here, our baseline has no requests
    baseline = copy.deepcopy(cache.cached_reqs)
    session.get('https://whatever/rest/api/2/field')
    # Now our cache has one request, which expires in 1 second
    # Flushing the cache should not matter
    cache.flush()
    assert cache.cached_reqs != baseline

    # Wait for our req to expire
    time.sleep(1.1)
    cache.flush()
    # Now, we should be back to baseline
    assert cache.cached_reqs == baseline


def test_rqcache_load_none(tmp_path):
    session = TestSession()
    cache = RequestCache(session, filename=None, expire=1)
    assert not cache.load(os.path.join(tmp_path, 'cache_test'))
    assert not cache.load()


def test_rqcache_load_bad(tmp_path):
    session = TestSession()
    filename = os.path.join(tmp_path, 'cache_test')
    with open(filename, 'w') as fp:
        fp.write('hello, world!')
    cache = RequestCache(session, filename, expire=1)
    # Tests using our initial filename
    assert not cache.load()

    # Bad magic # Note: doing this to your cache then
    # reading it, your object's behavior is undefined
    del cache.cached_reqs['magic']
    assert cache.save() == None  # pickle.dump returns None
    # This will wipe the file
    cache.load()

    # We unlink the file if it's bad data
    with pytest.raises(FileNotFoundError):
        os.unlink(filename)

    # No save
    cache._cache_file = None
    assert cache.save() == None


def test_rqcache_persist(tmp_path):
    session = TestSession()
    filename = os.path.join(tmp_path, 'cache_test')
    cache = RequestCache(session, filename=filename)  # use default
    ret1 = session.get('https://whatever/rest/api/2/field')
    cache.save()

    # Load our cache from disk
    session2 = TestSession()  # NOQA
    cache2 = RequestCache(session, filename=filename, expire=1)  # NOQA
    ret2 = session.get('https://whatever/rest/api/2/field')

    # Request should match
    assert ret1 == ret2


def test_rqcache_persist_expire(tmp_path):
    session = TestSession()
    filename = os.path.join(tmp_path, 'cache_test')
    cache = RequestCache(session, filename=filename, expire=1)
    ret1 = session.get('https://whatever/rest/api/2/field')
    cache.save()
    time.sleep(1.1)

    # Load our cache from disk
    session2 = TestSession()  # NOQA
    cache2 = RequestCache(session, filename=filename, expire=1)  # NOQA
    ret2 = session.get('https://whatever/rest/api/2/field')

    # Request should not match
    assert ret1 != ret2


def test_user_break(tmp_path):
    session = TestSession()
    filename = os.path.join(tmp_path, 'cache_test')
    cache = RequestCache(session, filename=filename, expire=1)
    url = 'https://whatever/rest/api/2/field'
    cache.user_breaks = {'GET': [url]}
    with pytest.raises(Exception):
        session.get(url)

