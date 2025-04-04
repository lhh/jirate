#!/usr/bin/python3
#
# AI-generated (kinda) example unit tests for ComplicatedArgs

# lhh - None of these imports were right
import argparse
import pytest

from jirate.args import ComplicatedArgs


def FunctionMockery(**kwargs):
    if 'return_value' in kwargs:
        def my_func(args):
            return kwargs['return_value']
    else:
        def my_func(args):
            return None
    return my_func


@pytest.fixture
def args():
    return ComplicatedArgs()


def test_initialization(args):
    assert isinstance(args.parser(), argparse.ArgumentParser)
    assert args._commands == {}
    assert args._handlers == {}
    assert args._subparsers is None
    assert args._parsed_ns is None
    assert args._args == {}


def test_add_argument(args):
    args.add_argument('--test', type=int)
    # Needed to add args= for each line
    parsed_args = args.parse_args(args=['--test', '10'])
    assert parsed_args.test == 10


def test_add_arg(args):
    args.add_arg('extra', 'value')
    ns = argparse.Namespace()
    args.finalize(ns)
    assert ns.extra == 'value'


def test_command_and_handler(args):
    mock_handler = FunctionMockery(return_value='test_result')
    args.command('test', help='Test command', handler=mock_handler)
    parsed_args = args.parse_args(args=['test'])
    result = args.finalize(parsed_args)
    assert result == 'test_result'


def test_second_command(args):
    handler_one = FunctionMockery(return_value='test_result')
    handler_two = FunctionMockery()
    args.command('test', help='Test command', handler=handler_one)
    args.command('test-two', help='Test command', handler=handler_two)
    parsed_args = args.parse_args(args=['test-two'])
    result = args.finalize(parsed_args)
    assert result == None


def test_command_duplicate(args):
    args.command('test')
    with pytest.raises(ValueError):
        args.command('test')


def test_register_handler_undefined_command(args):
    with pytest.raises(ValueError):
        args.register_handler('undefined', lambda x: None)


def test_delete_handler(args):
    # This test, which was AI-written, exposed bugs in delete_handler.
    args.command('test', handler=FunctionMockery(return_value=1))
    parsed_args = args.parse_args(args=['test'])
    result = args.finalize(parsed_args)
    assert result == 1
    args.delete_handler('test')
    result = args.finalize(parsed_args)
    assert result is None
    with pytest.raises(ValueError):
        args.delete_handler('HAHAHAHAHAHAH')


def test_parse_args(args):
    args.add_argument('--value', type=int)
    parsed_args = args.parse_args(args=['--value', '5'])
    assert parsed_args.value == 5


def test_finalize_no_command(args):
    ns = argparse.Namespace()
    result = args.finalize(ns, 'default')
    assert result == 'default'


def test_namespace(args):
    args.add_argument('--value', type=int)
    parsed_args = args.parse_args(args=['--value', '5'])
    args.finalize(parsed_args)
    assert args.namespace().value == 5
