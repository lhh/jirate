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


def test_ignore_underscore():
    # Variables that start with underscore are
    # ignored and thus are not required to be set
    # during template rendering.
    inp = """
{% set _varone=_varone or "1.0" %}
fork: {@_vartwo|default('1.0')@}
knife: {@_varthree@}
spoon: {@varfour@}
"""

    apply_values(inp, {'varfour': 'meh'})


def test_underscore_invalid():
    # It's a user error to try to set a variable that
    # starts with an underscore
    inp = """
{% set _varone=_varone or "1.0" %}
fork: {@_vartwo|default('1.0')@}
knife: {@_varthree@}
spoon: {@varfour@}
"""

    with pytest.raises(ValueError):
        apply_values(inp, {'_varthree': 'abc', 'varfour': 'meh'})


def test_datetime_strftime():
    inp = """
{% set year = datetime(2025, 5, 7, 10, 32, 27, 87081).strftime('%Y') %}
year: {@year@}
"""
    exp = 'year: 2025'

    assert apply_values(inp).strip() == exp.strip()


def test_datetime_override():
    inp = """
{% set year = year or datetime(2025, 5, 7, 10, 32, 27, 87081).strftime('%Y') %}
year: {@year@}
"""
    exp = 'year: 2033'

    values = {'year': '2033'}

    assert apply_values(inp, values).strip() == exp.strip()
