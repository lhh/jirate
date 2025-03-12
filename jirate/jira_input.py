#!/usr/bin/python

import re

from jirate.decor import parse_params
from jirate.decor import nym


def in_string(value):
    return str(value)


def in_number(value):
    return float(value)


def in_key(value):
    return {'key': value}


def in_name(value):
    return {'name': value}


def in_value(value):
    return {'value': value}


def in_owc(value):
    if ':' not in value:
        raise ValueError('Option-with-child is of form "option:child"')
    vals = value.split(':')
    if len(vals) != 2:
        raise ValueError('Option-with-child is of form "option:child"')

    return {'value': vals[0], 'child': {'value': vals[1]}}


# these can functions can be referenced in custom user
# config files.  These should be generic and should not
# utilize custom fields.
_input_renderers = {
    'number': in_number,
    'option': in_value,
    'priority': in_name,
    'version': in_name,
    'securitylevel': in_name,
    'option-with-child': in_owc,
    'issuelink': in_key,
    'resolution': in_name,
    'user': in_name
}


def _input_list(vals, attrib):
    return [{attrib: val} for val in vals]


def in_user_list(vals):
    # Could be key, which is why it's separate
    return _input_list(vals, 'name')


def in_value_list(vals):
    return _input_list(vals, 'value')


def in_name_list(vals):
    return _input_list(vals, 'name')


def in_string_list(vals):
    return vals


_input_array_renderers = {
    'user': in_user_list,
    'option': in_value_list,
    'version': in_name_list,
    'group': in_name_list,
    'component': in_name_list
}


# Custom field inputs for a few things
def in_sprint_field(value):
    if isinstance(value, list):
        value = value[0]
    return in_number(value)


def in_issue_key(value):
    if isinstance(value, list):
        value = value[0]
    return str(value).upper()


_custom_field_input = {
    'com.pyxis.greenhopper.jira:gh-sprint': in_sprint_field,
    'com.atlassian.jpo:jpo-custom-field-parent': in_issue_key,
    'com.pyxis.greenhopper.jira:gh-epic-link': in_issue_key
}


# Because allowed Values can be very long and complicated, we
# want users to be able to provide, essentially, the minimum
# unique value to save keystrokes (and frustration).
def check_value(check, value):
    for possible_value in (value, nym(value), value.lower()):
        if possible_value == check:
            return 2
        if check not in possible_value:
            continue
        # begnning of string, end of string.
        # Values should be divided by a space or dash
        # This is just a guess; we may want this configurable
        #
        rx = f'(^|[\\s\\-]){check}($|[\\s\\-])'
        if re.search(rx, possible_value):
            return 1
    return 0


def allowed_value_validate(field_name, values, allowed_values=None):
    if not allowed_values:
        return values

    # Validate that the name or value exists and create our array of IDs
    # corresponding to them.
    if not isinstance(values, list):
        check = [values]
    else:
        check = values

    info = {}
    for val in check:
        for av in allowed_values:
            # Ignore archived or disabled allowed values
            if 'archived' in av and av['archived']:
                continue
            if 'disabled' in av and av['disabled']:
                continue

            # Not sure why we care about name vs. value; value only is fine
            for key in ['name', 'value']:
                if key not in av:
                    continue
                cv = check_value(val, av[key])
                if cv == 2:
                    info[val] = {'values': [av[key]], 'exact': True}
                    continue
                if cv == 1:
                    if val in info:
                        if not info[val]['exact']:
                            info[val]['values'].append(av[key])
                    else:
                        info[val] = {'values': [av[key]], 'exact': False}

        # If we didn't find a match, raise an error
        if val not in info:
            raise ValueError(f'Value {val} not allowed for {field_name}')

    # We should only have one match per value
    for key in info:
        if len(info[key]['values']) > 1:
            raise ValueError(f'{key}: More than one match for {key}')

    ret = []
    # Output order MUST match input order
    for val in check:
        ret.append(info[val]['values'][0])

    if not isinstance(values, list):
        return ret[0]

    return ret


def transmogrify_value(value, field_info):
    schema = field_info['schema']
    av = field_info['allowedValues'] if 'allowedValues' in field_info else None

    if 'custom' in schema and schema['custom'] in _custom_field_input:
        return _custom_field_input[schema['custom']](value)

    if schema['type'] == 'array':
        vals = allowed_value_validate(field_info['name'], parse_params(value), av)
        try:
            ret = _input_array_renderers[schema['items']](vals)
        except KeyError:
            ret = in_string_list(vals)
    else:
        try:
            out_val = allowed_value_validate(field_info['name'], value, av)
            ret = _input_renderers[schema['type']](out_val)
        except KeyError:
            ret = in_string(value)

    return ret


# Channelling ... Calvin
def transmogrify_input(field_definitions, **args):
    """ Translate text input into something Jira understands natively when
    pasting to the API.

    Parameters:
        field_definitions: Create/Update metadata or /field dictionary
        args: User-provided key,value pairs (strings)

    Returns:
        Updated dictionary with JIRA field IDs and values corresponding to
        metadata in field_definitions
    """
    drop_fields = ['attachment', 'reporter', 'issuelinks']  # These are not set during create/update
    simple_fields = ['project', 'issuetype', 'summary', 'description']                # Don't process these fields at all
    output = {}
    def_map = {}

    for field in field_definitions:
        def_map[field] = field
        def_map[nym(field)] = field
        def_map[field_definitions[field]['name']] = field
        def_map[nym(field_definitions[field]['name'])] = field

    for field in args:
        value = args[field]
        if field in simple_fields:
            output[field] = value
            continue
        if field not in def_map:
            continue
        field_id = def_map[field]
        if field_id in drop_fields:
            continue
        output[field_id] = transmogrify_value(value, field_definitions[field_id])
    return output
