#!/usr/bin/python3

from jirate.template_vars import apply_values, _populate_defaults

import pytest  # NOQA
import types


def test_populate_defaults_simple():
    inp = '@@a:b@@'
    values = {}

    _populate_defaults(inp, values)
    assert values == {'a': 'b'}


def test_ok_variable_no_default():
    inp = '@@a@@'
    values = {'a': 'b'}

    ret = apply_values(inp, values)
    assert ret == 'b'


def test_populate_defaults_no_overwrite():
    inp = '@@a:b@@'
    values = {'a': 'c'}

    ret = apply_values(inp, values)
    assert ret == 'c'


def test_populate_defaults_first_value():
    inp = '@@a:b@@ @@a:c@@'
    values = {}

    ret = apply_values(inp, values)
    assert ret == 'b b'


def test_populate_defaults_no_overwrite2():
    inp = '@@a:b@@ @@a:c@@'
    values = {'a': 'd'}

    ret = apply_values(inp, values)
    assert ret == 'd d'


def test_populate_defaults_second_def():
    inp = '@@a@@ @@a:c@@'
    values = {}

    ret = apply_values(inp, values)
    assert ret == 'c c'


def test_multi_str1():
    inp = 'abc@@a@@def@@b@@ghi@@a@@jkl@@c@@'
    values = {'a': '1', 'b': '2', 'c': '3'}

    ret = apply_values(inp, values)
    assert ret == 'abc1def2ghi1jkl3'


def test_list1():
    inp = ['one', '@@ver@@', 'two']
    values = {'ver': '1.0'}

    ret = apply_values(inp, values)
    assert ret == ['one', '1.0', 'two']


def test_dict1():
    inp = {'top': '@@ver@@', 'bottom': '@@old:0.1@@'}
    values = {'ver': '1.0'}

    ret = apply_values(inp, values)
    assert ret == {'top': '1.0', 'bottom': '0.1'}


def test_complex1():
    inp = {'top': '@@ver@@', 'bottom': ['@@old:0.1@@', '@@date@@', {'pork': '@@bacon@@'}]}
    values = {'ver': '1.0', 'date': '2024-07-25', 'bacon': 'yum'}

    ret = apply_values(inp, values)
    assert ret == {'top': '1.0', 'bottom': ['0.1', '2024-07-25', {'pork': 'yum'}]}


def test_invalid_var():
    inp = {'fun': '@@bar@@'}
    values = {'baz': '123'}

    with pytest.raises(ValueError):
        ret = apply_values(inp, values)
