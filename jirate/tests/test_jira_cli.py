#!/usr/bin/env python

from jirate.jira_cli import _parse_creation_args

import pytest  # NOQA


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
