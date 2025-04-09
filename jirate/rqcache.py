#!/usr/bin/python3
#
# A lot of JIRA data is static - or close enough. So, we can
# greatly improve performance by caching a lot of commonly-retrieved
# fields.
#
# Previously, Jirate would simply cache individual items.
# This implementation uses patterns to cache specific API endpoints,
# including pagination, for things that don't change terribly often.
#
# We cache individual API calls with their parameters and the results,
# then return the results if the result is within _expire_time of the
# original request.  By recording the states locally, user-facing performance
# is dramatically improved.
#
# Future improvements:
# - A future improvement might be to allow individual expire times for
#   various patterns that change more frequently.  For example, fetching
#   an issue might have a 1 minute, while fetching /field might be 30 days.
# - Allow a user to purge cache from CLI (besides removing the file)
#
import os
import re
import time
import types

from jira.client import ResilientSession

from .decor import hbar_over, hbar_under
from .localstate import pickle_write, pickle_read

default_cache_expire = 43200

default_cache_patterns = {
    'GET': [r'/rest/api/[0-9]+/myself$',
            r'/rest/api/[0-9]+/field$',
            r'/rest/api/[0-9]+/user/search',
            r'/rest/agile/[0-9]+(\.[0-9]+)?/board$',
            r'/rest/agile/[0-9]+(\.[0-9]+)?/board/[0-9]+/sprint$',
            r'/rest/api/[0-9]+/project/[A-Z]+/statuses$',
            r'/rest/api/[0-9]+/project/[A-Z]+$',
            r'/rest/api/[0-9]+/issue/[0-9]+/transitions',
            r'/rest/api/[0-9]+/issue/createmeta/[A-Z]+/issuetypes',
            r'/rest/api/[0-9]+/issue/[0-9]+/editmeta',
            r'/rest/api/[0-9]+/user\?(username|key)=']
}


def _cached_request(cache, method, url, **kwargs):
    # Check cache first
    ret = cache._cache_read(method, url, kwargs)
    if ret:
        return ret

    # Record cache miss for API profiling/debugging
    cache._dbg_request(method, url, **kwargs)
    ret = ResilientSession.request(cache.session, method, url, **kwargs)
    cache._record_info(method, url, kwargs, ret)
    return ret


class RequestCache(object):
    __req_magic__ = '__req_magic__'

    def __init__(self, session, filename=None, expire=None, **kwargs):
        if expire is None:
            expire = default_cache_expire
        self._expire_time = expire
        self._cache_hits = 0
        self._cache_file = filename
        self.cached_reqs = {'magic': self.__req_magic__, 'GET': {}}
        self.cache_patterns = default_cache_patterns
        self.debug_reqs = {}
        self.user_breaks = {}

        self.session = session
        session.request = types.MethodType(_cached_request, self)
        if not filename:
            return
        self.load(filename)

    def _cache_read(self, method, url, args_dict=None):
        if method not in self.cached_reqs:
            return None
        if url not in self.cached_reqs[method]:
            return None

        for item in self.cached_reqs[method][url]:
            if time.gmtime(item['expire']) <= time.gmtime():
                # Expired
                self.cached_reqs[method][url].remove(item)
                return None
            if args_dict != item['args']:
                continue
            self._cache_hits = self._cache_hits + 1
            return item['value']
        return None

    def _dbg_request(self, method, url, **kwargs):
        if method in self.user_breaks and url in self.user_breaks[method]:
            raise Exception(f'User break @ {method} {url}')
        if method not in self.debug_reqs:
            self.debug_reqs[method] = {}
        if url not in self.debug_reqs[method]:
            self.debug_reqs[method][url] = {'count': 1}
        else:
            self.debug_reqs[method][url]['count'] += 1

    def debug_dump(self):
        total = 0
        print()
        if self.debug_reqs:
            hbar_under('API profiling starts')
            for key in self.debug_reqs:
                print(key)
                for url in self.debug_reqs[key]:
                    count = self.debug_reqs[key][url]['count']
                    total = total + count
                    print(f'    {count} {url}')
        hbar_over(f'Total reqs: {total} Cache hits: {self._cache_hits}')

    def _record_info(self, method, url, args_dict, value):
        if method not in self.cache_patterns:
            return
        urlmatch = False
        for line in self.cache_patterns[method]:
            if re.search(line, url):
                urlmatch = True
                break
        if not urlmatch:
            return
        expire = time.time() + float(self._expire_time)
        if url not in self.cached_reqs[method]:
            self.cached_reqs[method][url] = []
        self.cached_reqs[method][url].append({'args': args_dict,
                                              'expire': expire,
                                              'value': value})

    def load(self, filename=None):
        if filename is None:
            filename = self._cache_file
        if filename is None:
            return None
        # We expire per-req, not per file
        try:
            ret = pickle_read(filename)
        except:  # NOQA
            # Unpickling error, read error, whatever;
            # result is same for our purposes
            ret = False
            pass

        if ret:
            # Verify structure
            if 'magic' not in ret or ret['magic'] != self.__req_magic__:
                ret = None

        if ret:
            self.cached_reqs = ret
            return True
        try:
            os.unlink(filename)
        except FileNotFoundError:
            pass
        return False

    def flush(self):
        for method in self.cached_reqs:
            if method == 'magic':
                continue
            url_nuke = []
            for url in self.cached_reqs[method]:
                nuke = []
                for item in self.cached_reqs[method][url]:
                    if time.gmtime(item['expire']) <= time.gmtime():
                        # Expired
                        nuke.append(item)
                for item in nuke:
                    self.cached_reqs[method][url].remove(item)
                if not self.cached_reqs[method][url]:
                    url_nuke.append(url)
            for url in url_nuke:
                del self.cached_reqs[method][url]

    def save(self, filename=None):
        if filename is None:
            filename = self._cache_file
        if not filename:
            return None
        self.flush()
        return pickle_write(filename, self.cached_reqs)
