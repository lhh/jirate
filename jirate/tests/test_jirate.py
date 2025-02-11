#!/usr/bin/env python

from jirate.jboard import Jirate
from jirate.tests import fake_jira, fake_user, fake_transitions

import pytest  # NOQA
import types


fake_jirate = Jirate(fake_jira())


def transitions_override(obj, issue):
    return fake_transitions['transitions']


# XXX we don't have subs in at the level we need, so fake transitions this way
fake_jirate.transitions = types.MethodType(transitions_override, fake_jirate)


def test_jirate_myself():
    # assert not fake_jirate._user
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
    issue = fake_jirate.issue('TEST-1')

    # change if you alter issue or above predefined fake issue
    # data
    expected = 'test-build-1'

    assert issue.fields.customfield_1234567 == expected
    assert issue.raw['fields']['customfield_1234567'] == expected

    # too bad...
    with pytest.raises(AttributeError):
        issue.fields.fixed_in_build

    # Test one-way
    assert fake_jirate.field('TEST-1', 'fixed_in_build') == expected
    assert fake_jirate.field('TEST-1', 'Fixed in Build') == expected
    assert fake_jirate.field('TEST-1', 'customfield_1234567') == expected

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


def test_transition_resolutions():
    issue = fake_jirate.issue('TEST-1')
    assert fake_jirate.transitions(issue) == fake_transitions['transitions']

    fake_jirate.jira._session.reset()
    assert fake_jirate.move('TEST-1', 'done') == [issue]
    assert fake_jirate.jira._session.post_urls == {'https://domain.com/rest/api/2/issue/1000001/transitions': {'transition': {'id': '13'}}}

    fake_jirate.jira._session.reset()
    assert fake_jirate.move('TEST-1', 'done', resolution='won\'t do') == [issue]
    assert fake_jirate.jira._session.post_urls == {'https://domain.com/rest/api/2/issue/1000001/transitions': {'fields': {'resolution': {'name': 'Won\'t Do'}}, 'transition': {'id': '13'}}}

    fake_jirate.jira._session.reset()
    assert fake_jirate.move('TEST-1', 'done', resolution='done') == [issue]
    assert fake_jirate.jira._session.post_urls == {'https://domain.com/rest/api/2/issue/1000001/transitions': {'fields': {'resolution': {'name': 'Done'}}, 'transition': {'id': '13'}}}


def test_transition_bad_field():
    issue = fake_jirate.issue('TEST-1')
    assert fake_jirate.transitions(issue) == fake_transitions['transitions']

    fake_jirate.jira._session.reset()
    with pytest.raises(ValueError):
        assert fake_jirate.move('TEST-1', 'done', beastly_fido='odif_yltsaeb') == [issue]


@pytest.mark.parametrize("param,expected", [
    ('Fixed in Build', 'customfield_1234567'),
    ('fixed_in_build', 'customfield_1234567'),
    ('customfield_1234567', 'customfield_1234567')])
def test_field_to_id(param, expected):
    assert fake_jirate.field_to_id(param) == expected


@pytest.mark.parametrize("param,expected", [
    ('Fixed in Build', 'fixed_in_build'),
    ('fixed_in_build', 'fixed_in_build'),
    ('customfield_1234567', 'fixed_in_build')])
def test_field_to_alias(param, expected):
    assert fake_jirate.field_to_alias(param) == expected


@pytest.mark.parametrize("param,expected", [
    ('Fixed in Build', 'Fixed in Build'),
    ('fixed_in_build', 'Fixed in Build'),
    ('customfield_1234567', 'Fixed in Build')])
def test_field_to_human(param, expected):
    assert fake_jirate.field_to_human(param) == expected
