#!/usr/bin/python3

import re  # NOQA
from collections import OrderedDict
from jirate.decor import pretty_date, vsep_print, comma_separated
from jirate.jira_custom import custom_field_renderers


#
# Field rendering functions. Return a string, or None if you want the field
# suppressed.
#
def _list_of_key(field, key, as_object=False):
    if as_object:
        return list([item[key] for item in field])
    return comma_separated([item[key] for item in field])


def string(field, fields, as_object=False):
    return field


def floating(field, fields, as_object=False):
    if str(field).endswith('.0'):
        field = int(field)
    if not as_object:
        field = str(field)
    return field


def auto_field(field, fields, as_object=False):
    if isinstance(field, str):
        return field
    elif isinstance(field, list):
        return array(field, fields, as_object)
    elif isinstance(field, dict):
        for key in ['name', 'value']:
            if key in field:
                if 'id' in field and not as_object:
                    return f"{field[key]} (ID: {field['id']})"
                return auto_field(field[key], fields, as_object)
    elif isinstance(field, float):
        return floating(field, fields, as_object)

    if as_object:
        return field
    else:
        return str(field)


def option_with_child(field, fields, as_object=False):
    if 'child' in field:
        return field['value'] + ' - ' + field['child']['value']
    return field['value']


def key(field, fields, as_object=False):
    return field['key']


def value(field, fields, as_object=False):
    return field['value']


def name(field, fields, as_object=False):
    return field['name']


def user(field, fields, as_object=False):
    return field['displayName'] + ' - ' + field['emailAddress']


def user_list(field, fields, as_object=False):
    # Until we take email addresses as input, we should use
    # user names only when presenting lists of users
    return _list_of_key(field, 'name', as_object)


def array(field, fields, as_object=False):
    if as_object:
        return list(field)
    return comma_separated([str(item) for item in field])


def value_list(field, fields, as_object=False):
    return _list_of_key(field, 'value', as_object)


def name_list(field, fields, as_object=False):
    return _list_of_key(field, 'name', as_object)


def date(field, fields, as_object=False):
    return pretty_date(field)


def datetime(field, fields, as_object=False):
    return pretty_date(field)


def _ratio(field, fields, as_object=False):
    if int(field) < 0:
        return None
    if as_object:
        return field
    return str(field)


def _priority(field, fields, as_object=False):
    if field['name'] not in ('Undefined', 'undefined'):
        return field['name']
    return None


def _reporter(field, fields, as_object=False):
    if field['emailAddress'] != fields['creator']['emailAddress']:
        return user(field, fields)
    return None


def _created_updated(field, fields, as_object=False):
    created = pretty_date(field)
    if field != fields['updated']:
        updated = pretty_date(fields['updated'])
        return f'{created} (Updated {updated})'
    return created


def _human_list(basic_value, item_list, field, fields, as_object=False):
    if field[basic_value] in (0, '0'):
        return None
    if item_list not in field or as_object:
        return auto_field(field[basic_value], fields, as_object)
    else:
        # Special: votes is a count + list_of_key as displayName
        return str(field[basic_value]) + ': ' + _list_of_key(field[item_list], 'displayName', False)


def _votes(field, fields, as_object=False):
    return _human_list('votes', 'voters', field, fields, as_object)


def _watchers(field, fields, as_object=False):
    return _human_list('watchCount', 'watchers', field, fields, as_object)


# these can functions can be referenced in custom user
# config files.  These should be generic and should not
# utilize custom fields.
_field_renderers = {
    'string': string,
    'any': auto_field,
    'number': auto_field,
    'option': value,
    'option-with-child': option_with_child,
    'key': key,
    'issuelinks': key,
    'value': value,
    'name': name,
    'version': name,
    'user': user,
    'user_list': user_list,
    'array': array,
    'email_list': user_list,  # Is this duplicate needed?
    'value_list': value_list,
    'name_list': name_list,
    'datetime': datetime,
    'date': date
}


# Rule of thumb: if it's using an above generic
# renderer, use the key above.  If it's custom
# for that field, use the function. The goal is to
# provide as many generic items as possible to reduce
# the need for config-side rendering via code snippets.
#
# That said, in the config, one can call the functions:
#
#    "code": "name(field, fields)"
#
#     ===
#
#    "display": "name"
#
# 'id': matches your JIRA instance
# 'name': What to display as output when printing
# 'immutable': If True, user configurations cannot
#              overwrite/register handler for this
#              field
# 'display': Omitted: Display the field rendered as a
#                     string
#            False: Do not display this field at all
#            String: Predefined key from above field
#                    renderer table.
# 'code': Should really only be used by custom user
#         configs when here_there_be_dragons is True
#         Note: 'display' supersedes 'code' if both
#         are present.
# 'verbose': if True, Only show this field in
#            verbose mode when rendering all fields
#
_base_fields = [
    {
        'id': 'issuetype',
        'name': 'Issue Type',
        'immutable': True,
        'display': 'name'
    },
    {
        'id': 'parent',
        'name': 'Parent',
        'immutable': True,
        'display': 'key'
    },
    {
        'id': 'priority',
        'name': 'Priority',
        'display': _priority
    },
    {
        'id': 'created',
        'name': 'Created',
        'immutable': True,
        'verbose': True,
        'display': _created_updated
    },
    {
        'id': 'duedate',
        'name': 'Due Date',
        'display': 'date'
    },
    {
        # This is part of above.
        'id': 'updated',
        'name': 'Updated',
        'immutable': True,
        'display': False
    },
    {
        'id': 'assignee',
        'name': 'Assignee',
        'display': 'user'
    },
    {
        'id': 'status',
        'name': 'Status',
        'display': 'name'
    },
    {
        'id': 'resolution',
        'name': 'Resolution',
        'display': 'name'
    },
    {
        'id': 'resolutiondate',
        'name': 'Resolved',
        'display': 'date'
    },
    {
        'id': 'security',
        'name': 'Security Level',
        'display': 'name'
    },
    {
        'id': 'workratio',
        'name': 'Work Ratio',
        'display': _ratio
    },
    {
        'id': 'creator',
        'name': 'Creator',
        'display': 'user',
        'verbose': True,
    },
    {
        'id': 'reporter',
        'name': 'Reporter',
        'verbose': True,
        'display': _reporter
    },
    {
        'id': 'archivedby',
        'name': 'Archiver',
        'verbose': True,
        'display': 'user'
    },
    {
        'id': 'archiveddate',
        'name': 'Archived',
        'verbose': True,
        'display': 'date'
    },
    {
        'id': 'labels',
        'name': 'Labels',
        'display': 'array',
    },
    {
        'id': 'components',
        'name': 'Component(s)',
        'display': 'name_list'
    },
    {
        'id': 'versions',
        'name': 'Affects Version(s)',
        'display': 'name_list'
    },
    {
        'id': 'fixVersions',
        'name': 'Fix Version(s)',
        'display': 'name_list'
    },
    {
        'id': 'votes',
        'name': 'Votes',
        'display': _votes
    },
    {
        'id': 'watches',
        'name': 'Watchers',
        'display': _watchers
    },
]


# Shortcut to avoid making above list enormous
# These are all standard fields we don't presently
# have rendering for, but might in the future.
# Remember ordering matters in above list.  Since
# it "shouldn't" for things we're not printing out,
# alphabetic is fine.
_quiet_fields = [
    'aggregateprogress',
    'aggregatetimeestimate',
    'aggregatetimeoriginalestimate',
    'aggregatetimespent',
    'archivedby',
    'archiveddate',
    'environment',
    'lastViewed',
    'progress',
    'project',
    'reporter',
    'timeestimate',
    'timeoriginalestimate',
    'timespent',
    'timetracking',
    'worklog',
    'workratio'
]

_quiet_fields_applied = False


if not _quiet_fields_applied:
    _quiet_fields_applied = True
    for field in _quiet_fields:
        val = {'id': field, 'name': field, 'display': False}
        _base_fields.append(val)


# These are fields we should never provide
# custom rendering for; they are inherently
# complicated or positional.
_ignore_fields = [
    'attachment',
    'comment',
    'description',
    'issuekey',
    'issuelinks',
    'subtasks',
    'summary',
    'thumbnail'
]


_fields = None


_array_renderers = {
    'user': 'user_list',
    'option': 'value_list',
    'version': 'name_list',
    'group': 'name_list'
}


_jirate_fields = {}

# Store modules here so we don't keep loading from disk
_loaded_mods = {}


def apply_schema_renderer(field):
    schema = field['schema']
    if 'custom' in schema and schema['custom'] in custom_field_renderers:
        field['display'] = custom_field_renderers[schema['custom']]
        return
    if schema['type'] == 'array':
        try:
            field['display'] = _array_renderers[schema['items']]
        except KeyError:
            field['display'] = array
    else:
        try:
            field['display'] = _field_renderers[schema['type']]
        except KeyError:
            field['display'] = string


def func_from_path(filename, function, field, fields):
    # Load a function from a file and run that
    import importlib.util
    import os

    full_fn = os.path.expanduser(filename)
    mod_fn = os.path.basename(full_fn)
    if mod_fn not in _loaded_mods:
        spec = importlib.util.spec_from_file_location(f'{mod_fn}', full_fn)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded_mods[mod_fn] = module
    else:
        module = _loaded_mods[mod_fn]

    ret = eval(f'module.{function}(field, fields)')
    return ret


def eval_custom_field(__code__, field, fields):
    """Proof of concept: Execute inline code to render a field

    Only used if 'here_there_be_dragons' is set to true.  Represents
    an obvious security issue if you are not in control of your
    jirate configuration file:
        "code": "os.system('rm -rf ~/*')"

    Parameters:
      field:    is your variable name for your dict
      fields:   dict of fields indexed by id
      __code__: is inline in your config and can reference field

    Returns:
      rendered field value (string)
    """
    if field is None or not field:
        return None
    if '__code__' in __code__:
        raise ValueError('Reserved keyword in code snippet')
    if __code__.startswith('#'):
        filename, func = __code__[1:].split(':')
        return func_from_path(filename, func, field, fields)
    return eval(str(__code__))


def apply_field_renderers(custom_field_defs=None, reorder_custom=True):
    """Custom field rendering setup function

    Parameters:
      custom_field_defs: Dictionary (typically retrieved from
        /rest/api/latest/field) with custom code snippets or
        field rendering definitions

    Returns:
      nothing in particular
    """
    global _fields
    base_fields = OrderedDict()
    custom_fields = OrderedDict()
    ret = OrderedDict()

    # NOTE: Don't feed in field definitions acquired from getting
    # createmeta or editmeta; the resulting dictionary is subtly
    # different in an important way: field['id'] is field['fieldId']
    if not custom_field_defs:
        for field in _base_fields:
            if field['id'] in _ignore_fields:
                continue
            ret[field['id']] = field
        _fields = ret
        return

    # First go through base fields
    for field in _base_fields:
        base_fields[field['id']] = field

    # reorder
    for field in custom_field_defs:
        if 'id' not in field:
            continue
        if field['id'] in _ignore_fields:
            continue
        if field['id'] in base_fields:
            bf = base_fields[field['id']]
            if 'immutable' in bf and bf['immutable']:
                custom_fields[field['id']] = bf
                continue
            custom_fields[field['id']] = field
            if 'display' in bf and 'display' not in field and 'code' not in field:
                custom_fields[field['id']]['display'] = bf['display']
                continue
        custom_fields[field['id']] = field
        if 'display' not in field and 'code' not in field and 'schema' in field:
            apply_schema_renderer(field)
        if '_jirate_reference' in field:
            # Just keep track of reference
            _jirate_fields[field['id']] = field['_jirate_reference']

    if reorder_custom:
        for key in base_fields:
            if key not in custom_fields:
                ret[key] = base_fields[key]
        for key in custom_fields:
            ret[key] = custom_fields[key]
    else:
        for key in base_fields:
            ret[key] = base_fields[key]
        for key in custom_fields:
            ret[key] = custom_fields[key]

    if _fields:
        # If we were called twice, tack on the things we'd already set up
        for key in _fields:
            if key not in ret:
                ret[key] = _fields[key]

    _fields = ret


def jirate_field(field_key):
    if field_key in _jirate_fields:
        return _jirate_fields[field_key]
    return None


def render_field_data(field_key, fields, verbose=False, allow_code=False, as_object=False):
    """Render the field using custom-renderers or user-supplied code
    Note: you must first configure the rendering engine using apply_field_renderers()

    Parameters:
      field_key: Key of field in raw JIRA JSON we're rendering
      fields: The entire raw JIRA JSON we're using
      verbose: Passed to field rendering function
      allow_code: Allow eval() during execution (dangerous whenever source
                  is untrusted)
      as_object: Return a Python object instead of a string representation

    Returns:
      field_name: Human-readable field name (string)
      value: Rendered field value (string)
    """
    if field_key not in _fields:
        return field_key, fields[field_key]
    field_name = _fields[field_key]['name']
    if field_key not in fields and field_key not in _jirate_fields:
        return field_name, None
    if field_key in _jirate_fields:
        real_key = _jirate_fields[field_key]
        if real_key not in fields:
            return field_name, None
        field = fields[_jirate_fields[field_key]]
    else:
        field = fields[field_key]
    if not field:
        return field_name, None
    field_config = _fields[field_key]

    if 'verbose' in field_config:
        if field_config['verbose'] is True and not verbose:
            return field_name, None
    if 'disabled' in field_config and field_config['disabled'] is True:
        return field_name, None
    # display supersedes code
    if 'display' in field_config:
        r_info = field_config['display']
        if isinstance(r_info, bool):
            if not r_info:
                return field_name, None
            else:
                if as_object:
                    return field_name, field
                return field_name, str(field)
        if isinstance(r_info, str):
            if r_info not in _field_renderers:
                return field_name, f'<invalid renderer: {r_info} for {field_key}>'
            else:
                try:
                    ret = _field_renderers[r_info](field, fields, as_object)
                except Exception as exc:
                    ret = '<' + str(exc) + '>'
                return field_name, ret
        else:
            return field_name, r_info(field, fields, as_object)
    if 'code' in field_config and allow_code:
        try:
            ret = eval_custom_field(field_config['code'], field, fields)
        except Exception as exc:
            ret = '<' + str(exc) + '>'
        return field_name, ret
    if as_object:
        return field_name, field
    return field_name, str(field)


def field_ordering():
    return [_fields.keys()]


def max_field_width(issue, verbose, allow_code):
    width = 0

    for field_key in _fields:
        field_name, val = render_field_data(field_key, issue, verbose, allow_code)
        if not val:
            continue
        width = max(width, len(field_name))
    return width


def render_issue_fields(issue, verbose=False, allow_code=False, width=None):
    if not width:
        width = max_field_width(issue, verbose, allow_code)

    for field_key in _fields:
        field_name, val = render_field_data(field_key, issue, verbose, allow_code)
        if not val:
            continue
        vsep_print(' ', 0, field_name, width, val)
        # print(field_name.ljust(width), sep, val)
