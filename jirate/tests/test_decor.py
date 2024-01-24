#!/usr/bin/python3

from jirate.decor import truncate, parse_params, comma_separated


def test_parse_simple():
    assert parse_params('arg') == ['arg']


def test_parse_commas():
    assert parse_params('arg,barg') == ['arg', 'barg']
    assert parse_params('"Comma, Test, ", 2') == ['Comma, Test,', "2"]


def test_parse_spaces():
    assert parse_params('"Space Test"') == ['Space Test']
    assert parse_params('"Space Test",2') == ['Space Test', '2']
    assert parse_params('"Space Test","2"') == ['Space Test', "2"]


def test_parse_quote_eating():
    assert parse_params('"Space Test":10') == ['Space Test:10']


def test_truncate_identity():
    assert truncate('abc', 0) == 'abc'
    assert truncate('abcdef', 10) == 'abcdef'


def test_truncate_exceed():
    assert truncate('abc', 3) == 'abc'
    assert truncate('abcd', 3) == 'ab…'


def test_truncate_negative():
    assert truncate('abc', -3) == 'abc'
    assert truncate('abcd', -3) == '…cd'


def test_comma_separated():
    str_val = 'one, two, "three, and four"'
    list_val = ['one', 'two', 'three, and four']

    assert comma_separated(list_val) == str_val


def test_parse_and_unparse():
    str_val = 'one, two, "three, and four"'
    list_val = ['one', 'two', 'three, and four']

    assert parse_params(comma_separated(list_val)) == list_val
    assert comma_separated(parse_params(str_val)) == str_val
