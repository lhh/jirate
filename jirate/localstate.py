#!/usr/bin/python3
#
# Locked read/write ops for binary state files
#
import os
import struct
import fcntl
import pickle
import time


def lock(fd, block=True):
    lck = struct.pack('hhllhh', fcntl.F_WRLCK, 0, 0, 0, 0, 0)
    op = fcntl.F_SETLKW
    if block:
        op = fcntl.F_SETLK
    fcntl.fcntl(fd, op, lck)


def pickle_read(fn, **kwargs):
    ret = None
    exp = 0

    block = True
    if 'block' in kwargs and kwargs['block'] is False:
        block = False

    if 'expire' in kwargs:
        ex = kwargs['expire']
        if ex is None:
            exp = 0
        elif isinstance(ex, bool) and ex is False:
            exp = 0
        elif isinstance(ex, str) and ex == '0':
            exp = 0
        elif isinstance(ex, int) is int and ex <= 0:
            exp = 0
        elif isinstance(ex, float) and ex <= 0:
            exp = 0
        else:
            exp = ex

    inp = os.path.expanduser(fn)
    if not inp:
        return None

    try:
        st = os.stat(inp)
    except OSError:
        return None

    # Expired cache
    if exp and time.gmtime(st.st_mtime + float(exp)) <= time.gmtime():
        return None

    try:
        fd = os.open(inp, os.O_RDWR)
        lock(fd, block)
    except Exception as ex:  # NOQA - ditto
        if fd != -1:
            os.close(fd)
        return None

    fp = open(fd, 'rb')
    ret = pickle.load(fp)
    fp.close()
    return ret


def pickle_write(fn, obj):
    # TODO: mkstemp() and os.rename() for atomicity
    inp = os.path.expanduser(fn)
    if not inp:
        return None

    fd = -1
    try:
        fd = os.open(inp, os.O_WRONLY | os.O_SYNC | os.O_CREAT, mode=0o600)
        # lock before writing
        lock(fd)
    except:  # NOQA - Lots of reasons this could fail.
        if fd != -1:
            os.close(fd)
        return None

    os.lseek(fd, 0, 0)
    os.truncate(fd, 0)
    fp = open(fd, 'wb')
    ret = pickle.dump(obj, fp)
    fp.close()
    return ret
