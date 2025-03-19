#!/usr/bin/python3
# Wrapper to add handlers to subparsers

import argparse


class ComplicatedArgs(object):
    def __init__(self):
        self._parser = argparse.ArgumentParser()
        self._commands = {}
        self._handlers = {}
        self._subparsers = None
        self._parsed_ns = None
        self._args = {}     # Pasted in to namespaces before calling handlers

    def parser(self):
        return self._parser

    def add_arg(self, key, value):
        self._args[key] = value

    def add_argument(self, *args, **kwargs):
        self._parser.add_argument(*args, **kwargs)

    def command(self, cmd, help=None, handler=None):
        if cmd in self._commands:
            raise ValueError('Command already specified:' + str(cmd))

        if self._subparsers is None:
            self._subparsers = self._parser.add_subparsers(help='Commands (add -h for help)', dest='command')
        subparser = self._subparsers.add_parser(cmd, help=help)
        self._commands[cmd] = subparser
        if handler is not None:
            self.register_handler(cmd, handler)
        return subparser

    def register_handler(self, cmd, handler):
        if cmd not in self._commands:
            raise ValueError('Undefined command:', str(cmd))
        self._handlers[cmd] = handler

    def delete_handler(self, cmd):
        if cmd not in self._commands:
            raise ValueError('Undefined command:', str(cmd))
        if cmd in self._handlers:
            del self._handlers[cmd]

    def parse_args(self, **kwargs):
        return self._parser.parse_args(**kwargs)

    # Call our callouts with the namespace mapping we built
    def finalize(self, ns, ret=None):
        cmd = None
        try:
            if ns.command:
                cmd = ns.command
        except AttributeError:
            pass
        for key in self._args:
            setattr(ns, key, self._args[key])
        self._parsed_ns = ns
        if cmd and cmd in self._handlers:
            return self._handlers[cmd](ns)
        # Command not found
        return ret

    # Store this so we can return our handlers' return values instead of
    # our own.
    def namespace(self):
        return self._parsed_ns


# For calling cmdline functions w/o using
# argparse
class GenericArgs(dict):
    def __getattr__(self, name):
        if (name in self):
            return dict.__getitem__(self, name)
        return None
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
