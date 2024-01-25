#!/usr/bin/python3

import re  # NOQA
from collections import OrderedDict
from jirate.decor import pretty_date, vsep_print, comma_separated


#
# Field rendering functions. Return a string, or None if you want the field
# suppressed.
#
def _list_of_key(field, key):
    return comma_separated([item[key] for item in field])


def string(field, fields):
    return field


def auto_field(field, fields):
    if isinstance(field, str):
        return field
    if isinstance(field, list):
        return comma_separated([str(item) for item in field])
    if isinstance(field, dict):
        for key in ['name', 'value']:
            if key in field:
                return auto_field(field[key], fields)
    if isinstance(field, float):
        if str(field).endswith('.0'):
            return str(int(field))
    return str(field)


def option_with_child(field, fields):
    if 'child' in field:
        return field['value'] + ' - ' + field['child']['value']
    return field['value']


def key(field, fields):
    return field['key']


def value(field, fields):
    return field['value']


def name(field, fields):
    return field['name']


def user(field, fields):
    return field['displayName'] + ' - ' + field['emailAddress']


def user_list(field, fields):
    # Until we take email addresses as input, we should use
    # user names only when presenting lists of users
    return _list_of_key(field, 'name')


def array(field, fields):
    return comma_separated(field)


def value_list(field, fields):
    return _list_of_key(field, 'value')


def name_list(field, fields):
    return _list_of_key(field, 'name')


def date(field, fields):
    return field


def datetime(field, fields):
    return pretty_date(field)


def _ratio(field, fields):
    if int(field) < 0:
        return None
    return str(field)


def _priority(field, fields):
    if field['name'] not in ('Undefined', 'undefined'):
        return field['name']
    return None


def _reporter(field, fields):
    if field['emailAddress'] != fields['creator']['emailAddress']:
        return user(field, fields)
    return None


def _created_updated(field, fields):
    created = pretty_date(field)
    if field != fields['updated']:
        updated = pretty_date(fields['updated'])
        return f'{created} (Updated {updated})'
    return created


def _votes(field, fields):
    if field['votes'] in (0, '0'):
        return None
    return str(field['votes'])


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
#            verbose mode
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
        'id': 'votes',
        'name': 'Votes',
        'display': _votes
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
    'watches',
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


def apply_schema_renderer(field):
    schema = field['schema']
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
    return eval(str(__code__))


def apply_field_renderers(custom_field_defs=None):
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

    for key in base_fields:
        if key not in custom_fields:
            ret[key] = base_fields[key]

    for key in custom_fields:
        ret[key] = custom_fields[key]

    _fields = ret


def render_field_data(field_key, fields, verbose=False, allow_code=False):
    """Render the field using custom-renderers or user-supplied code
    Note: you must first configure the rendering engine using apply_field_renderers()

    Parameters:
      field_key: Key of field in raw JIRA JSON we're rendering
      fields: The entire raw JIRA JSON we're using
      verbose: Passed to field rendering function
      allow_code: Allow eval() during execution (dangerous whenever source
                  is untrusted)

    Returns:
      field_name: Human-readable field name (string)
      value: Rendered field value (string)
    """
    if field_key not in _fields:
        return field_key, fields[field_key]
    field_name = _fields[field_key]['name']
    if field_key not in fields:
        return field_name, None
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
                return field_name, str(field)
        if isinstance(r_info, str):
            if r_info not in _field_renderers:
                return field_name, f'<invalid renderer: {r_info} for {field_key}>'
            else:
                try:
                    ret = _field_renderers[r_info](field, fields)
                except Exception as exc:
                    ret = '<' + str(exc) + '>'
                return field_name, ret
        else:
            return field_name, r_info(field, fields)
    if 'code' in field_config and allow_code:
        try:
            ret = eval_custom_field(field_config['code'], field, fields)
        except Exception as exc:
            ret = '<' + str(exc) + '>'
        return field_name, ret
    return field_name, str(field)


def field_ordering():
    return [_fields.keys()]


def max_field_width(issue, verbose, allow_code):
    width = 0

    for field_key in _fields:
        if field_key not in issue:
            continue
        field_name, val = render_field_data(field_key, issue, verbose, allow_code)
        if not val:
            continue
        width = max(width, len(field_name))
    return width


def render_issue_fields(issue, verbose=False, allow_code=False, width=None):
    global _fields

    if not width:
        width = max_field_width(issue, verbose, allow_code)

    for field_key in _fields:
        if field_key not in issue:
            continue
        field_name, val = render_field_data(field_key, issue, verbose, allow_code)
        if not val:
            continue
        vsep_print(' ', 0, field_name, width, val)
        # print(field_name.ljust(width), sep, val)
