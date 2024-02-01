#!/usr/bin/python

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


def allowed_value_validate(field_name, values, allowed_values=None):
    if not allowed_values:
        return values

    # Validate that the name or value exists and create our array of IDs
    # corresponding to them.
    if not isinstance(values, list):
        check = [values]
    else:
        check = values

    ret = []
    for val in check:
        found = False
        for av in allowed_values:
            if 'archived' in av and av['archived']:
                continue
            if 'disabled' in av and av['disabled']:
                continue
            for key in ['name', 'value']:
                if key not in av:
                    continue
                if val not in (av[key], nym(av[key]), av[key].lower()):
                    continue
                ret.append(av[key])
                found = True
                break
            if found:
                break
        if not found:
            raise ValueError(f'Value {val} not allowed for {field_name}')

    if not isinstance(values, list):
        return ret[0]
    return ret


def transmogrify_value(value, field_info):
    schema = field_info['schema']
    av = field_info['allowedValues'] if 'allowedValues' in field_info else None

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
    simple_fields = ['project', 'issuetype', 'summary', 'description', 'parent']                # Don't process these fields at all
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
