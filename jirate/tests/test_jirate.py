#!/usr/bin/env python

from jirate.jboard import Jirate
from jirate.tests import fake_jira, fake_user

import pytest  # NOQA


fake_jirate = Jirate(fake_jira())


def test_jirate_myself():
    assert not fake_jirate._user
    me = fake_jirate.user
    assert fake_jirate.user
    assert me == fake_user


def test_jirate_issue():
    issue = fake_jirate.issue('TEST-9999')
    assert issue is None
    issue = fake_jirate.issue('TEST-1')
    assert issue


def test_jirate_basicfields():
    # Normal fields should be accessible via the field() function
    issue = fake_jirate.issue('TEST-2')

    val = issue.fields.description

    assert fake_jirate.field(issue, 'description') == val
    assert issue.field('description') == val


def test_jirate_customfields():
    issue = fake_jirate.issue('TEST-2')

    # change if you alter issue or above predefined fake issue
    # data
    expected = 'build-2'

    assert issue.fields.customfield_1234567 == expected
    assert issue.raw['fields']['customfield_1234567'] == expected

    # too bad...
    with pytest.raises(AttributeError):
        issue.fields.fixed_in_build

    # Test one-way
    assert fake_jirate.field('TEST-2', 'fixed_in_build') == expected
    assert fake_jirate.field('TEST-2', 'Fixed in Build') == expected
    assert fake_jirate.field('TEST-2', 'customfield_1234567') == expected

    # Negative test
    with pytest.raises(AttributeError):
        fake_jirate.field('TEST-2', 'arglebargle')

    assert fake_jirate.field(issue, 'fixed_in_build') == expected
    assert fake_jirate.field(issue, 'Fixed in Build') == expected
    assert fake_jirate.field(issue, 'customfield_1234567') == expected

    # Negative test
    with pytest.raises(AttributeError):
        fake_jirate.field(issue, 'arglebargle')

    # Test issue
    assert issue.field('fixed_in_build') == expected
    assert issue.field('Fixed in Build') == expected
    assert issue.field('customfield_1234567') == expected

    # Negative test
    with pytest.raises(AttributeError):
        issue.field('arglebargle')
