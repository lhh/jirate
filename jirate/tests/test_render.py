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


field_test_params = 'field_id,field_name,value'
field_test_info = [
        # Fixed in build (string)
        pytest.param('customfield_1234567', 'Fixed in Build', 'test-build-1'),

        # Score
        pytest.param('customfield_1234568', 'Score', '22'),

        # Array of Options (value) - includes checkboxes
        pytest.param('customfield_1234569', 'Array of Options', 'option_one, option_two'),

        # Array of Versions (names),
        pytest.param('customfield_1234570', 'Array of Versions', 'Version1, Version2'),

        # Array of Users (email addresses),
        pytest.param('customfield_1234571', 'Array of Users', 'one@two.com, two@two.com'),

        # Array of strings
        pytest.param('customfield_1234572', 'Array of Strings', 'one, two, three'),

        # Array of groups (name?),
        pytest.param('customfield_1234573', 'Array of Groups', 'group1, group2'),

        # Array of Any values
        pytest.param('customfield_1234574', 'Any Value', 'one, 2.0'),

        # Date value
        pytest.param('customfield_1234575', 'Date Value', '2022-08-01'),

        # Datetime value
        pytest.param('customfield_1234576', 'Datetime Value', '2019-12-24 21:10:00 EST'),

        # Related Issue (issue key) - TODO
        # assert render_field_data('customfield_1234577','TEST-2', ???),

        # Option (value),
        pytest.param('customfield_1234578', 'Option Value', 'option_one'),

        # Option with child
        pytest.param('customfield_1234579', 'Option and Child', 'option_one - child_value'),

        # User value (Name - email address),
        pytest.param('customfield_1234580', 'User Value', 'Rory Obert - robert@pie.com'),

        # Version value (name),
        pytest.param('customfield_1234581', 'Version Value', 'Version1'),
    ]


@pytest.mark.parametrize(field_test_params, field_test_info)
def test_render_auto_defs(field_id, field_name, value):
    apply_field_renderers(test_fielddefs)
    issue = fake_jirate.issue('TEST-1')
    fields = issue.raw['fields']

    # Fixed in build
    assert render_field_data(field_id, fields, False, True) == (field_name, value)


@pytest.mark.parametrize(field_test_params, field_test_info)
def test_render_null_auto_defs(field_id, field_name, value):
    apply_field_renderers(test_fielddefs)
    issue = fake_jirate.issue('TEST-2')
    fields = issue.raw['fields']

    assert render_field_data(field_id, fields, False, True) == (field_name, None)


def test_render_no_field():
    # Not all fields are in the schema
    apply_field_renderers(test_fielddefs)
    issue = fake_jirate.issue('TEST-2')
    fields = issue.raw['fields']

    assert render_field_data('summary', fields, False, True) == ('summary', 'Test 1')
