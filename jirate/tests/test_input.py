#!/usr/bin/env python

from jirate.tests import fake_metadata, fake_transitions, fake_fields
from jirate.jira_input import transmogrify_input
from jirate.jira_input import check_value, allowed_value_validate

import os
import time

import pytest

os.environ['TZ'] = 'America/New_York'
time.tzset()


def test_trans_string_reflective():
    # identity
    inp = {'description': 'This is a description'}
    out = {'description': 'This is a description'}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_string_nym():
    # We translate to JIRA field IDs
    inp = {'Description': 'This is a description'}
    out = {'description': 'This is a description'}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_priority():
    inp = {'Priority': 'blocker'}
    out = {'priority': {'name': 'Blocker'}}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_custom_basic():
    inp = {'fixed_in_build': 'build123'}
    out = {'customfield_1234567': 'build123'}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_number():
    inp = {'score': '1'}
    out = {'customfield_1234568': 1.0}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_array_options():
    inp = {'array_of_options': 'One,Two'}
    out = {'customfield_1234569': [{'value': 'One'}, {'value': 'Two'}]}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_array_missing_option():
    with pytest.raises(ValueError):
        transmogrify_input(fake_metadata, **{'option_value': 'One,Two,Three'})


def test_trans_array_versions():
    inp = {'array_of_versions': '1.0.1,1.0.2'}
    out = {'customfield_1234570': [{'name': '1.0.1'}, {'name': '1.0.2'}]}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_array_users():
    inp = {'array_of_users': 'user1,user2'}
    out = {'customfield_1234571': [{'name': 'user1'}, {'name': 'user2'}]}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_array_strings():
    inp = {'array_of_strings': '"string one","string 2"'}
    out = {'customfield_1234572': ['string one', 'string 2']}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_array_groups():
    inp = {'array_of_groups': 'group1,group2'}
    out = {'customfield_1234573': [{'name': 'group1'}, {'name': 'group2'}]}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_array_any():
    inp = {'any_value': 'one,2'}
    out = {'customfield_1234574': 'one,2'}

    assert transmogrify_input(fake_metadata, **inp) == out


# TODO: Fixup date and datetime; these should take various input formats
# but are strings


def test_trans_issuelink():
    inp = {'related_issue': 'TEST-2'}
    out = {'customfield_1234577': {'name': 'TEST-2'}}


def test_trans_option():
    inp = {'option_value': 'one'}
    out = {'customfield_1234578': {'value': 'One'}}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_missing_option():
    with pytest.raises(ValueError):
        transmogrify_input(fake_metadata, **{'option_value': 'Four'})


def test_trans_missing_field():
    inp = {'not_a_real_field': 'one'}
    out = {}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_user_value():
    inp = {'User Value': 'user1'}
    out = {'customfield_1234580': {'name': 'user1'}}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_version_value():
    inp = {'version_value': '1.0.1'}
    out = {'customfield_1234581': {'name': '1.0.1'}}

    assert transmogrify_input(fake_metadata, **inp) == out


def test_trans_missing_version():
    with pytest.raises(ValueError):
        transmogrify_input(fake_metadata, **{'version_value': '999'})


def test_trans_metadata():
    transition_fields = fake_transitions


def test_check_value_simple():
    valid = {'1': ['1', ' 1', '1 ', '1-', '-1'],
             'a': ['a', ' a', 'a ', 'a-', '-a'],
             '1.1': [' 1.1', '1.1 '],
             'test': ['test', 'test two']}

    for check in valid:
        for value in valid[check]:
            assert(check_value(check, value))


def test_check_value_exact():
    assert(check_value('1', '1') == 2)


def test_check_value_inexact():
    assert(check_value('1', '1 ') == 1)


def test_check_value_nomatch():
    valid = {'1': ['a1', ' 12', '1.1'],
             'a': ['a1', ' ab', 'a.b'],
             '1.1': ['1.11', '1.1.2']}

    for check in valid:
        for value in valid[check]:
            assert(not check_value(check, value))


def test_fuzzy_values_exact():
    allowed_values = fake_fields[3]['allowedValues']  # components
    # python and 'python 4.0' are available, but because this is exact,
    # we get only one python result
    assert allowed_value_validate('components', 'python', allowed_values) == 'python'


def test_fuzzy_values_fail():
    allowed_values = fake_fields[3]['allowedValues']  # components
    # 2 possible matches for 'test', so ambiguous, raise valueerror
    with pytest.raises(ValueError):
        allowed_value_validate('components', 'test', allowed_values)


def test_fuzzy_values_approx():
    allowed_values = fake_fields[3]['allowedValues']  # components
    # only one match for this
    assert allowed_value_validate('components', 'fuzzy', allowed_values) == 'fuzzy match'


def test_avv_multiple():
    allowed_values = fake_fields[3]['allowedValues']  # components

    assert allowed_value_validate('components', ['fuzzy', 'python'], allowed_values) == ['fuzzy match', 'python']
