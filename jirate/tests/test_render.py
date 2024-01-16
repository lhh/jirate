#!/usr/bin/env python

from jirate.jboard import Jirate
from jirate.tests import fake_jira, fake_user
from jirate.jira_fields import apply_field_renderers, render_issue_fields, max_field_width, render_field_data

import pytest

fake_jirate = Jirate(fake_jira())
test_fielddefs = fake_jirate.jira.fields()


def test_rendering_basic():
    issue = fake_jirate.issue('TEST-1')
    apply_field_renderers()

    assert render_field_data('assignee', issue.raw['fields'], False, False) == ('Assignee', 'Rory Obert - robert@pie.com')


def test_rendering_display():
    # Override assignee to show user name in JIRA
    # Calls predefined function
    fielddefs = [{'id': 'assignee', 'name': 'Assignee', 'display': 'name'}]

    issue = fake_jirate.issue('TEST-1')
    apply_field_renderers(fielddefs)

    assert render_field_data('assignee', issue.raw['fields'], False, False) == ('Assignee', 'rory')


def test_render_nocode_oops():
    # Override assignee to show user name in JIRA
    # Ignores code _and_ display when overriding a base thing, resulting in the dict being produced
    fielddefs = [{'id': 'assignee', 'name': 'Assignee', 'code': 'field[\'emailAddress\']'}]

    issue = fake_jirate.issue('TEST-1')
    apply_field_renderers(fielddefs)

    ret = render_field_data('assignee', issue.raw['fields'], False, False)
    assert ret[0] == 'Assignee'
    assert ret[1] == str(issue.field('assignee'))


def test_render_code():
    # Test code callback
    fielddefs = [{'id': 'assignee', 'name': 'Assignee', 'code': 'field[\'emailAddress\']'}]

    issue = fake_jirate.issue('TEST-1')
    apply_field_renderers(fielddefs)

    assert render_field_data('assignee', issue.raw['fields'], False, True) == ('Assignee', 'robert@pie.com')


def test_render_code_override():
    # Display overrides code when both are present even when saying to allow code
    fielddefs = [{'id': 'assignee', 'name': 'Assignee', 'display': 'name', 'code': 'field[\'emailAddress\']'}]

    issue = fake_jirate.issue('TEST-1')
    apply_field_renderers(fielddefs)

    assert render_field_data('assignee', issue.raw['fields'], False, True) == ('Assignee', 'rory')


def test_render_auto_defs():
    apply_field_renderers(test_fielddefs)
    issue = fake_jirate.issue('TEST-1')
    fields = issue.raw['fields']

    # Fixed in build
    assert render_field_data('customfield_1234567', fields, False, True) == ('Fixed in Build', 'test-build-1')

    # Score
    assert render_field_data('customfield_1234568', fields, False, True) == ('Score', '22')

    # Array of Options (value) - includes checkboxes
    assert render_field_data('customfield_1234569', fields, False, True) == ('Array of Options', 'option_one, option_two')

    # Array of Versions (names)
    assert render_field_data('customfield_1234570', fields, False, True) == ('Array of Versions', 'Version1, Version2')

    # Array of Users (email addresses)
    assert render_field_data('customfield_1234571', fields, False, True) == ('Array of Users', 'one@two.com, two@two.com')

    # Array of strings
    assert render_field_data('customfield_1234572', fields, False, True) == ('Array of Strings', 'one, two, three')

    # Array of groups (name?)
    assert render_field_data('customfield_1234573', fields, False, True) == ('Array of Groups', 'group1, group2')

    # Array of Any values
    assert render_field_data('customfield_1234574', fields, False, True) == ('Any Value', 'one, 2.0')

    # Date value
    assert render_field_data('customfield_1234575', fields, False, True) == ('Date Value', '2022-08-01')

    # Datetime value
    assert render_field_data('customfield_1234576', fields, False, True) == ('Datetime Value', '2019-12-24 21:10:00 EST')

    # Related Issue (issue key) - TODO
    # assert render_field_data('customfield_1234577', fields, False, True) == ('TEST-2', ???)

    # Option (value)
    assert render_field_data('customfield_1234578', fields, False, True) == ('Option Value', 'option_one')

    # Option with child
    assert render_field_data('customfield_1234579', fields, False, True) == ('Option and Child', 'option_one - child_value')

    # User value (Name - email address)
    assert render_field_data('customfield_1234580', fields, False, True) == ('User Value', 'Rory Obert - robert@pie.com')

    # Version value (name)
    assert render_field_data('customfield_1234581', fields, False, True) == ('Version Value', 'Version1')


def test_render_null_auto_defs():
    issue = fake_jirate.issue('TEST-2')
    fields = issue.raw['fields']

    # Fixed in build
    assert render_field_data('customfield_1234567', fields, False, True) == ('Fixed in Build', 'build-2')

    # Score
    assert render_field_data('customfield_1234568', fields, False, True) == ('Score', None)

    # Array of Options (value) - includes checkboxes
    assert render_field_data('customfield_1234569', fields, False, True) == ('Array of Options', None)

    # Array of Versions (names)
    assert render_field_data('customfield_1234570', fields, False, True) == ('Array of Versions', None)

    # Array of Users (email addresses)
    assert render_field_data('customfield_1234571', fields, False, True) == ('Array of Users', None)

    # Array of strings
    assert render_field_data('customfield_1234572', fields, False, True) == ('Array of Strings', None)

    # Array of groups (name?)
    assert render_field_data('customfield_1234573', fields, False, True) == ('Array of Groups', None)

    # Array of Any values
    assert render_field_data('customfield_1234574', fields, False, True) == ('Any Value', None)

    # Date value
    assert render_field_data('customfield_1234575', fields, False, True) == ('Date Value', None)

    # Datetime value
    assert render_field_data('customfield_1234576', fields, False, True) == ('Datetime Value', None)

    # Option (value)
    assert render_field_data('customfield_1234578', fields, False, True) == ('Option Value', None)

    # Option with child
    assert render_field_data('customfield_1234579', fields, False, True) == ('Option and Child', None)

    # User value (Name - email address)
    assert render_field_data('customfield_1234580', fields, False, True) == ('User Value', None)

    # Version value (name)
    assert render_field_data('customfield_1234581', fields, False, True) == ('Version Value', None)
