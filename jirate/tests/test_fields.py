#!/usr/bin/env python

import jirate.jira_fields

import pytest


stringy_value = "haha"

singleton_value = {
    'name': 'TestValue',
    'key': 'thekey',
    'value': 'thevalue',
    'emailAddress': 'robert@thepie.com',
    'displayName': 'Rory Obert'
}

list_value = [
    'val1',
    'val2'
]

listy_field_values = [
    {'emailAddress': 'abc@def',
     'displayName': 'Aloha Brings Customers',
     'value': 'value1',
     'name': 'name1'},
    {'emailAddress': 'def@def',
     'displayName': 'Dark Existential Ferrets',
     'value': 'value2',
     'name': 'name'}
]


fields = {
    'string': stringy_value,
    'singleton': singleton_value,
    'list': list_value,
    'dict_list': listy_field_values
}


def test_parser_string():
    assert jirate.jira_fields.string(stringy_value, fields) == stringy_value


def test_parser_key():
    assert jirate.jira_fields.key(singleton_value, fields) == 'thekey'

    with pytest.raises(KeyError):
        jirate.jira_fields.key({}, fields)


def test_parser_value():
    assert jirate.jira_fields.value(singleton_value, fields) == 'thevalue'

    with pytest.raises(KeyError):
        jirate.jira_fields.value({}, fields)


def test_parser_name():
    assert jirate.jira_fields.name(singleton_value, fields) == 'TestValue'

    with pytest.raises(KeyError):
        jirate.jira_fields.name({}, fields)


def test_parser_user():
    assert jirate.jira_fields.user(singleton_value, fields) == 'Rory Obert - robert@thepie.com'

    with pytest.raises(KeyError):
        jirate.jira_fields.user({}, fields)
