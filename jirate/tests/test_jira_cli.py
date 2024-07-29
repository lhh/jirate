#!/usr/bin/env python

from jirate.tests import fake_jira, fake_user, fake_transitions, fake_metadata, fake_fields
from jirate.args import GenericArgs
from jirate.jira_cli import _parse_creation_args, _create_from_template, _serialize_issue, _generate_template, \
    validate_template
from jirate.jboard import JiraProject
from jirate.jira_fields import apply_field_renderers

import pytest  # NOQA
import types
from jsonschema.exceptions import ValidationError
from pathlib import Path


fake_jirate = JiraProject(fake_jira(), 'TEST', closed_status='Done', allow_code=True)

# These are used in the template tests below
args = GenericArgs()
args.project = fake_jirate
TEMPLATE_DIR = Path('jirate/tests/templates').absolute()


# XXX This metadata shouldn't just be fields? Fix later.
def _fake_metadata(obj, issuetype, **args):
    return {'fields': fake_metadata}


fake_jirate.issue_metadata = types.MethodType(_fake_metadata, fake_jirate)
apply_field_renderers(fake_fields)


def test_creation_args_bare():
    # With no required/reserved/translated fields, input == output
    issue_data = {'subtasks': {'1': 2}, 'issue_type': 'whatever', 'pork': 'bacon'}

    assert _parse_creation_args(issue_data) == issue_data


def test_creation_args_nominal():
    # Ensure having a translated field and one field that is reserved that
    # we strip out the reserved field and translate the other one.
    reserved_fields = ['subtasks']
    translate_fields = {'issue_type': 'issuetype'}

    issue_data = {'subtasks': {'1': 2}, 'issue_type': 'whatever', 'pork': 'bacon'}
    expected = {'issuetype': 'whatever', 'pork': 'bacon'}

    assert _parse_creation_args(issue_data, reserved_fields=reserved_fields, translate_fields=translate_fields) == expected


def test_creation_args_no_trans():
    # Ensure having a translated field but no instance of it, we don't add extra info
    reserved_fields = ['subtasks']
    translate_fields = {'issue_type': 'issuetype'}

    issue_data = {'subtasks': {'1': 2}, 'pork': 'bacon'}
    expected = {'pork': 'bacon'}

    assert _parse_creation_args(issue_data, reserved_fields=reserved_fields, translate_fields=translate_fields) == expected


def test_creation_args_missing():
    # Given a missing required field in our issue_data, ensure that we
    # raise an error.
    reserved_fields = ['subtasks']
    translate_fields = {'issue_type': 'issuetype'}
    required_fields = ['summary']

    issue_data = {'subtasks': {'1': 2}, 'issue_type': 'whatever', 'pork': 'bacon'}

    with pytest.raises(ValueError):
        assert _parse_creation_args(issue_data, required_fields=required_fields, reserved_fields=reserved_fields, translate_fields=translate_fields)


def test_creation_args_required_trans():
    # Given an untranslated field name in our issue_data, ensure that it is
    # translated.
    reserved_fields = ['subtasks']
    translate_fields = {'issue_type': 'issuetype'}
    required_fields = ['summary', 'issuetype']

    issue_data = {'subtasks': {'1': 2}, 'issue_type': 'whatever', 'pork': 'bacon', 'summary': 'Summary'}
    expected = {'issuetype': 'whatever', 'pork': 'bacon', 'summary': 'Summary'}

    assert _parse_creation_args(issue_data, required_fields=required_fields, reserved_fields=reserved_fields, translate_fields=translate_fields) == expected


def test_creation_args_required_no_trans():
    # Given an input with a required field that is translatable but
    # already in the right format, we don't alter the output.
    reserved_fields = ['subtasks']
    translate_fields = {'issue_type': 'issuetype'}
    required_fields = ['summary', 'issuetype']

    issue_data = {'subtasks': {'1': 2}, 'issuetype': 'whatever', 'pork': 'bacon', 'summary': 'Summary'}
    expected = {'issuetype': 'whatever', 'pork': 'bacon', 'summary': 'Summary'}

    assert _parse_creation_args(issue_data, required_fields=required_fields, reserved_fields=reserved_fields, translate_fields=translate_fields) == expected


def test_creation_args_defaults():
    # Ensure that when we are provided default inputs, that those are copied
    # to our output.  Anything in start_vals should not be removed or ignored
    # if they are in reserved_fields, since start_vals is expected to be
    # code and issue_data is user input.
    reserved_fields = ['subtasks']
    required_fields = ['summary', 'issuetype']
    start_vals = {'issuetype': 'whatever', 'other': 'value'}

    issue_data = {'subtasks': {'1': 2}, 'pork': 'bacon', 'summary': 'Summary'}
    expected = {'pork': 'bacon', 'summary': 'Summary', 'issuetype': 'whatever', 'other': 'value'}

    assert _parse_creation_args(issue_data, required_fields=required_fields, reserved_fields=reserved_fields, start_vals=start_vals) == expected


def test_creation_args_defaults_no_override():
    # Ensure that when we are provided default inputs, that those are copied
    # to our output.  Additionally, when we have a reserved field that is
    # already provided in the start_vals but then again in issue_data, if
    # it is a reserved field, it should not be overridden.
    reserved_fields = ['subtasks', 'issuetype']
    required_fields = ['summary', 'issuetype']
    start_vals = {'issuetype': 'whatever', 'other': 'value'}

    issue_data = {'subtasks': {'1': 2}, 'pork': 'bacon', 'summary': 'Summary', 'issuetype': 'other_issuetype'}
    expected = {'pork': 'bacon', 'summary': 'Summary', 'issuetype': 'whatever', 'other': 'value'}

    assert _parse_creation_args(issue_data, required_fields=required_fields, reserved_fields=reserved_fields, start_vals=start_vals) == expected


def test_creation_args_defaults_override():
    # Ensure that when we are provided default inputs, that those are copied
    # to our output.  Additionally, when we have a field in our start_vals
    # that is not reserved and also provided in issue_data, we should
    # overwrite it.
    reserved_fields = ['subtasks']
    required_fields = ['summary', 'issuetype']
    start_vals = {'issuetype': 'whatever', 'other': 'value'}

    issue_data = {'subtasks': {'1': 2}, 'pork': 'bacon', 'summary': 'Summary', 'issuetype': 'other_issuetype'}
    expected = {'pork': 'bacon', 'summary': 'Summary', 'issuetype': 'other_issuetype', 'other': 'value'}

    assert _parse_creation_args(issue_data, required_fields=required_fields, reserved_fields=reserved_fields, start_vals=start_vals) == expected


def test_create_from_template_simple():
    template = {'issues': [
                {'summary': 'whatever',
                 'issuetype': 'Task',
                 'description': 'Description'}
                ]}

    issue = _create_from_template(args, template)
    assert issue == [{'parent': 'TEST-1'}]
    issue = fake_jirate.issue('TEST-1')
    assert issue == {'key': 'TEST-1', 'raw': {'fields': {'description': 'Description', 'issuetype': 'Task', 'project': {'key': 'TEST'}, 'summary': 'whatever'}}}


def test_create_from_template_customfield():
    # TEST-2 pops out because we are reusing the above fake_jirate
    template = {'issues': [
                {'summary': 'custom field test',
                 'issuetype': 'Task',
                 'fixed_in_build': 'abc123',
                 'description': 'Test of custom field transmogrify'}
                ]}

    issue = _create_from_template(args, template)
    assert issue == [{'parent': 'TEST-2'}]
    issue = fake_jirate.issue('TEST-2')
    assert issue == {'key': 'TEST-2', 'raw': {'fields': {'description': 'Test of custom field transmogrify', 'issuetype': 'Task', 'customfield_1234567': 'abc123', 'project': {'key': 'TEST'}, 'summary': 'custom field test'}}}


def test_create_from_template_subtasks():
    # TEST-3/4 pop out because we are reusing the above fake_jirate
    template = {'issues': [
                {'summary': 'Sub Tasks Check',
                 'issuetype': 'Task',
                 'subtasks': [
                     {'summary': 'Child Task'}
                 ]}]}

    _create_from_template(args, template)
    # Creates TEST-3 and TEST-4
    assert fake_jirate.issue('TEST-3') == {'key': 'TEST-3', 'raw': {'fields': {'issuetype': 'Task', 'project': {'key': 'TEST'}, 'summary': 'Sub Tasks Check'}}}
    assert fake_jirate.issue('TEST-4') == {'key': 'TEST-4', 'raw': {'fields': {'issuetype': 'Sub-task', 'parent': {'key': 'TEST-3'}, 'project': {'key': 'TEST'}, 'summary': 'Child Task'}}}


def test_create_from_template_multiple_types():
    # TEST-5/6 pop out because we are reusing the above fake_jirate
    template = {'issues': [
                {'summary': 'Multitype1',
                 'issuetype': 'Task'
                 },
                {'summary': 'Multitype2',
                 'issuetype': 'Bug',
                 'subtasks': [
                     {'summary': 'Bug Subtask'}
                 ]}]}

    _create_from_template(args, template)
    # Creates TEST-5 and TEST-6
    assert fake_jirate.issue('TEST-5') == {'key': 'TEST-5', 'raw': {'fields': {'issuetype': 'Task', 'project': {'key': 'TEST'}, 'summary': 'Multitype1'}}}
    assert fake_jirate.issue('TEST-6') == {'key': 'TEST-6', 'raw': {'fields': {'issuetype': 'Bug', 'project': {'key': 'TEST'}, 'summary': 'Multitype2'}}}
    assert fake_jirate.issue('TEST-7') == {'key': 'TEST-7', 'raw': {'fields': {'issuetype': 'Sub-task', 'project': {'key': 'TEST'}, 'parent': {'key': 'TEST-6'}, 'summary': 'Bug Subtask'}}}


def test_generate_template_simple():
    # Note this uses the fake_issues found in __init__.py, not from the create_from_template tests
    actual = {'issues': [
                {'summary': 'Test 1',
                 'issue_type': 'Bug',
                 'description': 'Test Description 1'}
                ]}
    allow_fields = list(actual['issues'][0].keys())
    generated = _generate_template(fake_jira().issue('TEST-1').raw['fields'],
                                   fake_jirate.field_to_alias,
                                   allow_fields=allow_fields)
    generated = {'issues': [generated]}

    assert actual == generated


def test_generate_template_customfield():
    # Note this uses the fake_issues found in __init__.py, not from the create_from_template tests
    actual = {'issues': [
                {'summary': 'Test 1',
                 'issue_type': 'Bug',
                 'description': 'Test Description 1',
                 'fixed_in_build': 'test-build-1'}
                ]}
    allow_fields = list(actual['issues'][0].keys())

    generated = _generate_template(fake_jira().issue('TEST-1').raw['fields'],
                                   fake_jirate.field_to_alias,
                                   allow_fields=allow_fields)
    generated = {'issues': [generated]}
    assert actual == generated


def test_generate_template_subtasks():
    # Note this uses the fake_issues found in __init__.py, not from the create_from_template tests
    actual = {'issues': [
                {'summary': 'Test 3 (parent task)',
                 'issue_type': 'Bug',
                 'sub_tasks': [
                     {'summary': 'Test 4 (subtask of Test 3)',
                      'issue_type': 'Sub-task'}
                 ]}]}
    allow_fields = list(actual['issues'][0].keys())

    generated = _generate_template(fake_jira().issue('TEST-3').raw['fields'],
                                   fake_jirate.field_to_alias,
                                   allow_fields=allow_fields,
                                   fetch_issue=fake_jira().issue)
    generated = {'issues': [generated]}

    assert actual == generated


def test_validate_templates_good():
    # Validating a known-good template should succeed
    args.template_file = f"{TEMPLATE_DIR / 'good-template.yaml'}"
    validate_template(args)


def test_validate_templates_bad():
    # Validating a known-bad template should fail
    args.template_file = f"{TEMPLATE_DIR / 'bad-template.yaml'}"
    with pytest.raises(ValidationError):
        validate_template(args)
