#!/usr/bin/env python

import types

from .decor import hbar_over, hbar_under
from jira.client import ResilientSession

debug_reqs = {}
user_breaks = {}
# user_breaks = {'GET': ['https://my-jira.com/rest/api/2/field']}

def dbg_request(self, method, url, **kwargs):
    if method in user_breaks and url in user_breaks[method]:
        raise Exception(f'User break @ {method} {url}')
    if method not in debug_reqs:
        debug_reqs[method] = {}
    if url not in debug_reqs[method]:
        debug_reqs[method][url] = {'count': 1}
    else:
        debug_reqs[method][url]['count'] += 1
    return super(ResilientSession, self).request(method, url, **kwargs)


def debug_setup(jira):
    jira._session.request = types.MethodType(dbg_request, jira._session)


def debug_dump():
    if not debug_reqs:
        return
    total = 0
    hbar_under('API profiling starts')
    for key in debug_reqs:
        print(key)
        for url in debug_reqs[key]:
            count = debug_reqs[key][url]['count']
            total = total + count
            print(f'    {count} {url}')
    hbar_over(f'Total: {total}')
