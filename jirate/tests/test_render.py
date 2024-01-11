#!/usr/bin/env python

from jirate.jboard import Jirate
from jirate.tests import fake_jira, fake_user
from jirate.jira_fields import apply_field_renderers, render_issue_fields, max_field_width, render_field_data

import pytest

fake_jirate = Jirate(fake_jira())


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
