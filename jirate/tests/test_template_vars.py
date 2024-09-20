#!/usr/bin/python3

from jirate.template_vars import apply_values

import pytest  # NOQA


def test_apply_var_type1():
    inp = """
{% set var=var or "1.0" %}
fork: {@var@}
"""
    exp = 'fork: 1.0'
    assert apply_values(inp).strip() == exp.strip()


def test_apply_var_type2():
    inp = """
fork: {@var|default('1.0')@}
"""
    exp = 'fork: 1.0'
    assert apply_values(inp).strip() == exp.strip()


def test_missing_var():
    inp = """
fork: {@var|default('1.0')@}
knife: {@butter@}
"""
    with pytest.raises(ValueError):
        apply_values(inp)


def test_provided_var():
    inp = """
fork: {@var|default('1.0')@}
knife: {@butter@}
"""
    exp = """
fork: 2.0
knife: salted
"""
    values = {'var': '2.0',
              'butter': 'salted'}
    assert apply_values(inp, values).strip() == exp.strip()


def test_invalid_var():
    inp = """
fork: {@var|default('1.0')@}
knife: {@butter@}
"""
    values = {'var': '2.0',
              'butter': 'salted',
              'bacon': 'such delishus, very salt, fat, wow'}
    with pytest.raises(ValueError):
        apply_values(inp, values)
