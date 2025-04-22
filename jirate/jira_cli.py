#!/usr/bin/python3

import copy
import json
import os
import re
import sys
import yaml
from importlib.resources import files

import editor

from collections import OrderedDict
from jira.exceptions import JIRAError
from referencing import Registry
import jsonschema

from jirate.args import ComplicatedArgs, GenericArgs
from jirate.jboard import JiraProject, get_jira
from jirate.decor import md_print, pretty_date, hbar_under, hbar, hbar_over, nym, vsep_print, parse_params, truncate, render_matrix, comma_separated
from jirate.decor import issue_link_string, link_string
from jirate.decor import pretty_print  # NOQA
from jirate.decor import EscapedString
from jirate.config import get_config, yaml_dump
from jirate.jira_fields import apply_field_renderers, render_issue_fields, max_field_width, render_field_data, jirate_field
from jirate.template_vars import apply_values
from jirate.rqcache import RequestCache


# Prevent case/typos/etc.
_subtask = 'Sub-task'


def move(args):
    if args.user:
        args.project.assign(args.src, args.user)
    if args.mine:
        args.project.assign(args.src, 'me')
    ret = args.project.move(args.src, args.target)
    if ret:
        print('Moved', [issue.key for issue in ret], 'to', args.target)
        return (0, False)
    print('No issue(s) moved')
    return (1, False)


def close_issues(args):
    ret = 0
    close_args = {}
    if args.resolution:
        close_args['resolution'] = args.resolution

    close_issues = []
    if args.subtasks:
        for issue_key in args.target:
            # Close subtasks first, then main issue
            issue = args.project.issue(issue_key)
            if issue.key in close_issues:
                continue
            issue_subtasks = [subtask['key'] for subtask in issue.raw['fields']['subtasks']]
            close_issues.extend(issue_subtasks)
            close_issues.append(issue.key)
    else:
        close_issues = args.target

    for issue in close_issues:
        if not args.project.close(issue, **close_args):
            ret = 1
    return (ret, False)


def parse_field_widths(field_string, allowed_fields=None, ignore_fields=None, starting_fields=None):
    if not starting_fields:
        fields = OrderedDict()
    else:
        fields = starting_fields

    raw_fields = parse_params(field_string)
    for field in raw_fields:
        if ':' in field:
            val = field.split(':')
            field = val[0]
            maxlen = int(val[1])
        else:
            maxlen = 0
        if ignore_fields and field in ignore_fields:
            continue
        if allowed_fields and field not in allowed_fields:
            continue
        fields[field] = maxlen
    return fields


def _reorder_issues(issue_list):
    ret = []
    issues_by_key = OrderedDict()

    # 1. Scrape all issues by key
    for issue in issue_list:
        issues_by_key[str(issue.key)] = issue

    # 2. Reorder
    #    a. group subtasks under parent task
    #    b. orphan subtasks are left in rank order
    for issue in issue_list:
        if str(issue.fields.issuetype) == _subtask:
            # For subtasks, if their parent is not in the list,
            # append now to preserve rank order
            if str(issue.fields.parent) not in issues_by_key:
                ret.append(issue)
            continue
        ret.append(issue)

        # There's a bug in JIRA API. If you get:
        #    issue/ISSUE-123
        # ... the subtasks in the JSON data are in order according to the
        # JIRA web UI.  If, however, you have ISSUE-123 as part of the
        # result of a search, the subtasks' ordering according to the UI
        # is not preserved
        issue_subtasks = [subtask['key'] for subtask in issue.raw['fields']['subtasks']]
        for subtask in issue_subtasks:
            if subtask in issues_by_key:
                ret.append(issues_by_key[subtask])

    return ret


def print_issues_by_field(issue_list, args=None, exclude_fields=[]):
    # TODO: sort by column
    fields = OrderedDict({'key': 0})
    ignore_fields = ['key']
    ignore_fields.extend(exclude_fields)
    fields = parse_field_widths(args.fields, ignore_fields=ignore_fields, starting_fields=fields)
    if args.format != 'csv':
        subtask_prefix = EscapedString('↳ ')
        subtask_error = EscapedString('‼ ')
    else:
        subtask_prefix = EscapedString('')
        subtask_error = EscapedString('')

    if not args.compact:
        args.compact = args.project.get_user_data('compact_output')

    output = []
    raw_fields = list(fields.keys())
    output.append(list(truncate(key, fields[key]) for key in fields))
    del fields['key']

    found_fields = []
    issue_list = _reorder_issues(issue_list)

    # To show subtasks under parents, we need to know all the issues we
    # have so we can see if the parent task is in the list
    issue_keys = [str(issue.key) for issue in issue_list]

    for issue in issue_list:
        if args and hasattr(args, 'status') and args.status:
            if nym(issue.field('status')['name']) != nym(args.status):
                continue
        row = []
        key_string = issue_link_string(issue.key, args.project.jira.server_url)
        # Above, we reordered a subtask to be under its parent task in subtask
        # order according to the parent issue. Here, we want to show a visual break
        # to show this is associated with the above non-Subtask
        if str(issue.fields.issuetype) == _subtask and str(issue.fields.parent) in issue_keys:
            # No f-magic for EscapedString, so we must concatenate
            if issue.raw['fields']['status']['statusCategory']['name'] != 'Done' and issue.raw['fields']['parent']['fields']['status']['statusCategory']['name'] == 'Done':
                key_string = subtask_error + key_string
            else:
                key_string = subtask_prefix + key_string
        row.append(key_string)
        for field in fields:
            # See if it's a user-defined one first, as optimization
            real_key = jirate_field(field)
            if real_key:
                field_key = field
            else:
                # See if it's an alias for a field in jira
                # (then real_key and field_key are the same)
                field_key = args.project.field_to_id(field)
                if not field_key:
                    row.append('N/A')
                    continue
                real_key = field_key
            try:
                raw_fv = issue.field(real_key)
            except AttributeError:
                row.append('N/A')
                continue
            fk, fv = render_field_data(field_key, issue.raw['fields'], True, args.project.allow_code)
            if fk:
                val = fv
            else:
                val = raw_fv
            if val is None:
                val = ''
            row.append(truncate(val, fields[field]))
            if args.compact and val == '':
                continue
            if field not in found_fields:
                found_fields.append(field)
        output.append(row)

    header = not (args.format in ['csv'])
    if header:  # Fancy output: save real estate by removing columns
        delta = list(set(list(fields.keys())) - set(found_fields))
        for kill in delta:
            try:
                column = raw_fields.index(kill)
                raw_fields.pop(column)
            except ValueError:
                print(f'Bug: Tried to remove nonexistent column {kill}?')
                continue
            for row in output:
                row.pop(column)

    lines = render_matrix(output, fmt=args.format, header=header)
    return lines


def print_issues_by_state(issue_list, args=None):
    states = {}
    printed = 0

    for issue in issue_list:
        cstatus = issue.raw['fields']['status']['name']
        if cstatus not in states:
            states[cstatus] = []
        states[cstatus].append(issue)

    for key in states:
        if args and hasattr(args, 'status') and args.status and nym(key) != nym(args.status):
            continue
        hbar_under(key)
        for issue in states[key]:
            printed = printed + 1
            issue_info = EscapedString('  ') + issue_link_string(issue.key, args.project.jira.server_url)
            print(issue_info, end=' ')
            if args and hasattr(args, 'labels') and args.labels:
                print_labels(issue.raw, prefix='')
            print(issue.raw['fields']['summary'])
        print()
    return printed


def print_keys(issue_list):
    for issue in issue_list:
        print(issue.key)
    return False


def print_issues(issue_list, args=None, exclude_fields=[]):
    footer = (args.format in ('default'))
    total = len(issue_list)

    if not issue_list:
        print('No matching issues')
        footer = False
    elif not args:
        total = print_issues_by_state(issue_list, args)
    elif hasattr(args, 'quiet') and args.quiet:
        print_keys(issue_list)
        footer = False
    elif hasattr(args, 'fields') and args.fields is not None:
        total = print_issues_by_field(issue_list, args, exclude_fields)
    else:
        fields = args.project.get_user_data('default_fields')
        if fields:
            setattr(args, 'fields', fields)
            total = print_issues_by_field(issue_list, args, exclude_fields)
        else:
            total = print_issues_by_state(issue_list, args)
    if footer and total is not None:
        hbar_over(str(total) + ' result(s)')
    return True


def print_users(users):
    matrix = [['Name', 'User Name', 'Email Address']]

    for user in users:
        matrix.append([user.displayName, user.name, user.emailAddress])
    render_matrix(matrix)


# Returns the search name and fields if provided
def find_search(name, search_info):
    if name not in search_info:
        return (None, None)
    item = search_info[name]
    if isinstance(item, str):
        return (item, None)
    elif not isinstance(item, dict) or 'query' not in item:
        return (None, None)

    fields = None
    if 'fields' in item:
        fields = item['fields']
    return (item['query'], fields)


def search_jira(args):
    if args.user:
        users = args.project.search_users(args.user)
        if not users:
            print(f'No users match "{args.user}"')
            return (1, False)
        print_users(users)
        return (0, False)

    named = args.named_search
    fields = None
    if not args.text and not named:
        named = 'default'
    if named:
        searches = args.project.get_user_data('searches')
        (search_query, fields) = find_search(named, searches)
        if not search_query:
            print(f'No search configured: {named}')
            return (1, False)
        if args.text:
            additional = ' '.join(args.text)
            search_query = f'({additional}) AND {search_query}'

        # Field priority:
        # 1. cli fields
        # 2. per-search fields
        # 3. global fields
        if (not hasattr(args, 'fields') or args.fields is None) and fields:
            setattr(args, 'fields', fields)
        ret = args.project.search_issues(search_query)
    else:
        search_query = ' '.join(args.text)
        if args.raw:
            ret = args.project.search_issues(search_query)
        else:
            ret = args.project.search(search_query)

    # JIRA's text search borders on useless.
    # Prune any issues from output where the regex does not
    # match supplied field
    stripped = []
    if args.prune_regex:
        field = args.prune_regex[0]
        fid = args.project.field_to_id(field)
        regex = args.prune_regex[1]
        for issue in ret:
            val = issue.field(field)
            try:
                if val and re.search(regex, val):
                    stripped.append(issue)
                continue
            except TypeError:
                pass
            (_, val) = render_field_data(fid, issue.raw['fields'], True, args.project.allow_code)
            if val and re.search(regex, val):
                stripped.append(issue)
        ret = stripped

    if not ret:
        return (127, False)
    print_issues(ret, args)
    return (0, False)


def list_issues(args):
    # check for verbose
    if args.unassigned:
        userid = None
    elif args.user:
        userid = args.user
    else:
        userid = 'me'

    issues = args.project.list(status=args.status, userid=userid, all_issues=args.all)
    print_issues(issues, args)
    return (0, True)


def list_link_types(args):
    ltypes = args.project.link_types()
    matrix = [['Outward', 'Inward']]
    for lt in ltypes:
        matrix.append([lt.outward, lt.inward])
    render_matrix(matrix)
    return (0, True)


def list_states(args):
    states = args.project.states()
    namelen = 0
    for name in states:
        namelen = max(namelen, len(name))
    for name in states:
        vsep_print(None, 0, name, namelen, states[name]['name'])
    return (0, False)


def list_issue_types(args):
    issue_types = args.project.issue_types
    for itype in issue_types:
        print('  ', itype.name)
    return (0, False)


def issue_fields(args):
    if args.issue:
        issue = args.project.issue(args.issue)
        if not issue:
            print('No such issue:', args.issue)
            return (1, False)
        fields = args.project.fields(issue.raw['key'])
    elif args.type:
        md = args.project.issue_metadata(args.type)
        if md:
            fields = md['fields']
        else:
            print(f'No metadata for {args.type}')
            return (1, False)

    # Remove things we set elsewhere
    for field in ('assignee', 'issuelinks', 'comment'):
        if field in fields:
            del fields[field]

    # Remove things we don't support setting
    for field in ('issuetype', 'attachment', 'reporter', 'project'):
        if field in fields:
            del fields[field]

    display = False
    try:
        if args.operation:
            pass
    except AttributeError:
        display = True

    if display:
        matrix = [['Field', 'Allowed Values']]
        for field in fields:
            if field.startswith('customfield_'):
                fname = nym(fields[field]['name'])
            else:
                fname = nym(field)
            fvalue = ''
            if 'allowedValues' in fields[field]:
                values = []
                for val in fields[field]['allowedValues']:
                    if 'archived' in val and val['archived']:
                        continue
                    if 'name' in val:
                        values.append(val['name'])
                    elif 'value' in val:
                        values.append(val['value'])
                    else:
                        values.append(val['id'])
                fvalue = comma_separated(values)
            matrix.append([fname, fvalue])
        render_matrix(matrix)
        return (0, False)

    # Update a field
    field_name = args.name
    field_id = args.project.field_to_id(field_name)
    if field_id not in fields:
        raise ValueError(f'Update to {field_name} ({field_id}) is not allowed at this point')

    schema = fields[field_id]['schema']
    if schema['type'] == 'user':
        value = args.project.get_user(args.values[0])
    elif schema['type'] == 'array':
        # Special case: Resolve users before passing down
        if schema['items'] == 'user':
            value = [args.project.get_user(user) for user in args.values]
        else:
            value = args.values
    else:
        value = ' '.join(args.values)

    op = args.operation
    # Substitution only works on 'set' capable fields for now
    if args.operation == 'sub':
        op = 'set'
        if len(args.values) < 2:
            raise ValueError('Substitution requires an old value and a new value')
        oldval = args.values[0]
        newval = args.values[1]
        (_, orig_value) = render_field_data(field_id, issue.raw['fields'], True, args.project.allow_code)
        value = orig_value.replace(oldval, newval)

    try:
        issue.update_field(field_name, value, op, fields)
    except (AttributeError, ValueError) as e:
        print(e)
        return (1, False)
    return (0, False)


def split_issue_text(text):
    lines = text.split('\n')
    name = lines[0]
    desc = ''
    if not len(name):
        return (None, None)
    lines.pop(0)
    while len(lines) and lines[0] == '':
        lines.pop(0)
    if len(lines):
        desc = '\n'.join(lines)
    return (name, desc)


def new_issue(args):
    desc = None

    if args.text:
        name = ' '.join(args.text)
    else:
        text = editor()
        name, desc = split_issue_text(text)
        if name is None:
            print('Canceled')
            return (1, False)

    issue = args.project.new(name, desc, issue_type=args.type)
    if args.quiet:
        print(issue.raw['key'])
    else:
        print_issue(args.project, issue, False)
    return (0, True)


def print_creation_fields(metadata):
    nlen = 5
    fields = metadata['fields']
    ignore_fields = ('Reporter', 'Project', 'Issue Type')
    for field in fields:
        if fields[field]['name'] in ignore_fields:
            continue
        if field.startswith('customfield_'):
            nlen = max(nlen, len(nym(fields[field]['name'])))
        else:
            nlen = max(nlen, len(nym(field)))

    matrix = [['Field', 'R', 'Allowed Values']]

    for field in fields:
        if fields[field]['name'] in ignore_fields:
            continue
        if field.startswith('customfield_'):
            fname = nym(fields[field]['name'])
        else:
            fname = nym(field)
        fvalue = ''
        if fields[field]['required']:
            req = '*'
        else:
            req = ' '
        if 'allowedValues' in fields[field]:
            values = []
            for val in fields[field]['allowedValues']:
                if 'archived' in val and val['archived']:
                    continue
                if 'name' in val:
                    values.append(val['name'])
                elif 'value' in val:
                    values.append(val['value'])
                else:
                    values.append(val['id'])
            fvalue = comma_separated(values)
        matrix.append([fname, req, fvalue])
    render_matrix(matrix)


def _metadata_by_type(project, issuetype):
    try:
        metadata = project.issue_metadata(issuetype)
    except JIRAError as e:
        if 'text: Issue Does Not Exist' in str(e):
            print('The createmeta API does not exist on this JIRA instance.')
        else:
            print(e)
        return (1, False)

    if not metadata:
        list_issue_types(project.issue_types)
        raise ValueError(f'Invalid issue type: {issuetype}')
    return metadata


# new_issue is way too easy. Let's make it *incredibly* complicated!
def create_issue(args):
    desc = None
    issuetype = args.type if args.type else 'Task'

    # Do sanity check before hitting the JIRA API
    if len(args.args) % 2 == 1:
        print('Incorrect number of arguments (not divisible by 2)')
        return (1, False)

    metadata = _metadata_by_type(args.project, issuetype)

    values = {}
    argv = copy.copy(args.args)
    if len(argv) == 0:
        print_creation_fields(metadata)
        return (0, False)

    while len(argv):
        key = argv.pop(0)
        value = argv.pop(0)
        values[key] = value

    # Bug - error checking isn't done until later, but we need a
    # summary or the below code blows up.  So, you might pop up
    # $EDITOR only to find out later that you used an invalid
    # issue type.
    if 'summary' not in values:
        text = editor()
        name, desc = split_issue_text(text)
        if name is None:
            print('Canceled')
            return (1, False)
        values['summary'] = name
        if desc:
            values['description'] = desc

    values['issuetype'] = metadata['name']
    values['project'] = args.project.project_name

    issue = args.project.create(metadata['fields'], **values)
    if args.quiet:
        print(issue.raw['key'])
    else:
        print_issue(args.project, issue, False)
    return (0, True)


def _parse_creation_args(issue_data, required_fields=None, reserved_fields=None, translate_fields=None, start_vals=None):
    ret = {}
    if start_vals:
        ret = start_vals

    for key in issue_data:
        actual_key = key
        if translate_fields and key in translate_fields:
            actual_key = translate_fields[key]
        if not reserved_fields or actual_key not in reserved_fields:
            ret[actual_key] = issue_data[key]
    missing = []
    if required_fields:
        for key in required_fields:
            if key not in ret:
                missing.append(key)
        if missing:
            raise ValueError(f'Missing required fields: {missing}')
    return ret


def create_from_template(args):
    with open(args.template_file, 'r') as yaml_file:
        template = yaml_file.read()

    values = {}
    # Always render. there should be defaults.
    if args.vars:
        if len(args.vars) % 2 != 0:
            raise ValueError('Variable/value list is not divisible by 2')

        # Someone set up us the render
        argv = copy.copy(args.vars)
        while len(argv):
            key = argv.pop(0)
            value = argv.pop(0)
            values[key] = value

    interactive = sys.stdin.isatty() and not args.non_interactive

    # template_output is the raw text with jinja2 variable substitution
    # completed, not a yaml structure
    template_output = apply_values(template, values, interactive)

    template = yaml.safe_load(template_output)

    try:
        _validate_template(args.project, template)
    except jsonschema.exceptions.ValidationError as e:
        print(f"Provided template file is not valid: {args.template_file}")
        raise e

    if args.dry_run:
        print(template_output)
        return (0, True)

    all_filed = _create_from_template(args, template)

    # Need to refresh to that issues get re-fetched to include subtasks
    # TODO: Have subtask() update parent issues in _config['issue_map']
    args.project.delete_issue_map()
    for filed in all_filed:
        if args.quiet:
            if 'subtasks' in filed:
                print(filed['parent'] + ': ' + ', '.join(filed['subtasks']))
            else:
                print(filed['parent'])
        else:
            print_issue(args.project, args.project.issue(filed['parent']), False)
    return (0, True)


def _create_from_template(args, template):
    # Cache for issue createmeta information
    metadata_by_type = {}

    # TODO: consider using Jira's bulk issue creation
    # TODO: support reading arbitrary fields from the template
    all_filed = []  # We keep issue keys here because we'll need to refresh anyway

    existing_issue = None
    if args.apply:
        # Sanity checks:
        # 1. Issue exists
        existing_issue = args.project.issue(args.apply)
        if not existing_issue:
            raise ValueError(f'Cannot apply template to nonexisting issue {args.apply}')
        # 2. Template's issues attribute length is 1
        if len(template['issues']) != 1:
            raise ValueError('Undefined request: template is for multiple issues')

    projects = {}
    projects[args.project.project_name] = args.project

    for raw_issue in template['issues']:
        issue = {args.project.field_to_id(name): value for name, value in raw_issue.items()}
        reserved_fields = ['subtasks']
        required_fields = ['summary']
        if 'project' in issue:
            pname = issue['project']
        else:
            pname = args.project.project_name
        if pname not in metadata_by_type:
            metadata_by_type[pname] = {}
        if pname not in projects:
            projects[pname] = JiraProject(args.project.jira, pname, readonly=False, allow_code=args.project.allow_code)

        creation_fields = _parse_creation_args(issue, required_fields, reserved_fields)

        # Cache all metadata now (so we can debug subtask creation if needed.
        issuetype = creation_fields['issuetype']
        if issuetype not in metadata_by_type:
            metadata_by_type[pname][issuetype] = _metadata_by_type(projects[pname], issuetype)
        if 'subtasks' in issue and issue['subtasks']:
            metadata_by_type[pname][_subtask] = _metadata_by_type(projects[pname], _subtask)
        metadata = metadata_by_type[pname][issuetype]

        filed = {}
        if existing_issue:
            # Do not mess with issuetype if we're applying to existing issue
            del creation_fields['issuetype']
            existing_issue.update(**creation_fields)
            parent = existing_issue
        else:
            parent = projects[pname].create(metadata['fields'], **creation_fields)
        filed['parent'] = parent.key

        # Apply subtasks - but only to a parent which does not already have any
        # subtasks
        if ('subtasks' in issue and issue['subtasks']) and ('subtasks' not in parent.raw['fields'] or not parent.raw['fields']['subtasks']):
            # Set once
            filed['subtasks'] = []
            for subtask in issue['subtasks']:
                metadata = metadata_by_type[pname][_subtask]
                reserved_fields = ['subtasks', 'issuetype', 'parent']
                # required_fields are the same
                start_fields = {'issuetype': _subtask, 'project': pname}
                start_fields['parent'] = parent.key
                creation_fields = _parse_creation_args(subtask, required_fields, reserved_fields, start_vals=start_fields)

                child = projects[pname].create(metadata['fields'], **creation_fields)
                filed['subtasks'].append(child.key)
        all_filed.append(filed)

    return all_filed


def _validate_template(project, template):
    for i, issue in enumerate(template['issues']):
        template['issues'][i] = {project.field_to_id(name): value for name, value in issue.items()}

    schema_dir = files('jirate').joinpath('schemas')
    schemas = {}
    for schema_file in ('template.yaml', 'issue.yaml', 'subtask.yaml'):
        schemas[f"jirate:{schema_file}"] = yaml.safe_load(
            schema_dir.joinpath(schema_file).read_text())

    registry = Registry().with_contents([(k, v) for k, v in schemas.items()])
    validator = jsonschema.Draft202012Validator(schema=schemas['jirate:template.yaml'], registry=registry)

    # Will raise a ValidationError with details on what failed:
    validator.validate(template)
    return True


def validate_template(args):
    with open(args.template_file, 'r') as yaml_file:
        template = yaml.safe_load(yaml_file)

    _validate_template(args.project, template)

    # If we get here it means validation succeeded.
    print(f"Template {args.template_file} is valid.")
    return (0, True)


def generate_template(args):
    template = {}
    issue = args.project.issue(args.issue_id)
    if not issue:
        print('No such issue:', args.issue_id)
        return (1, False)

    # TODO: allow customizing allow_fields in the config
    template = _generate_template(issue.raw['fields'], args.project.field_to_alias, args.project.issue, args.all_fields)

    print(yaml_dump({'issues': [template]}))
    return (0, True)


def _generate_template(raw_issue, translate_fields, fetch_issue=None, all_fields=False, allow_fields=None):
    template = _serialize_issue(raw_issue, translate_fields, fetch_issue)

    if not all_fields:
        if allow_fields is not None:
            # Ensure these are in alias form, if set. Makes writing configs easier.
            allow_fields = [translate_fields(field) for field in allow_fields]
        template = _trim_template(template, allow_fields)
    return template


def _serialize_issue(raw_issue, translate_fields, fetch_issue=None):
    """
    Serializes raw JIRA issue fields for use in Jirate templates.

    Parameters:
      raw_issue: issue fields (typically issue.raw['fields']) (dict)
      translate_fields: field name translator (typically a JiraProject's field_to_alias method) (function)
      fetch_issue: issue data fetcher, used to get subtask data (typically a JiraProject's issue method) (function)

    Returns:
      Processed issue dict ready to be dumped as part of a YAML template (dict)
    """
    template = {}
    _subtasks = 'subtasks'  # ID form

    for field, value in raw_issue.items():
        if field == _subtasks and value:
            # The parent issue only includes some of the subtask data, so we need to fetch the rest.
            template[translate_fields(_subtasks)] = []
            for subtask_stub in raw_issue[_subtasks]:
                subtask = fetch_issue(subtask_stub['key'])
                template[translate_fields(_subtasks)].append(_serialize_issue(subtask.raw['fields'], translate_fields))
        else:
            _, template[translate_fields(field)] = render_field_data(field, raw_issue, as_object=True)

    return template


def _trim_template(template, allow_fields=None):
    """
    Returns a trimmed template containing only the fields from the input template that
    are both in an allowlist and initialized (not empty).
    """
    # Field names are already translated to aliases so we don't need to
    # deal with customfield_ nonsense here.
    if allow_fields is None:
        allow_fields = [
            'fixversions',
            'priority',
            'issue_type',
            'summary',
            'description',
            'story_points',
            'components',
            'versions',
            'labels',
            'sub_tasks',
        ]
    _subtasks = 'sub_tasks'  # Alias form, see above comment

    trimmed_fields = {}
    for field, value in template.items():
        if field not in allow_fields:
            continue
        # We can't just check truthiness because False or 0 could be a legitimate value
        if value is None:
            continue
        if (isinstance(value, list) or isinstance(value, dict)) and len(value) == 0:
            continue

        # We want the field and it isn't empty-ish
        if field == _subtasks and len(value) > 0:
            trimmed_fields[_subtasks] = [_trim_template(subtask, allow_fields) for subtask in value]
        else:
            trimmed_fields[field] = value
    return trimmed_fields


def new_subtask(args):
    desc = None
    parent_issue = args.project.issue(args.issue_id)
    if not parent_issue:
        print('No such issue:', args.issue_id)
        return (1, False)

    if args.text:
        name = ' '.join(args.text)
    else:
        text = editor()
        name, desc = split_issue_text(text)
        if name is None:
            print('Canceled')
            return (1, False)

    issue = args.project.subtask(parent_issue.raw['key'], name, desc)
    if args.quiet:
        print(issue.raw['key'])
    else:
        print_issue(args.project, issue, False)
    return (0, True)


def link_issues(args):
    left_issue = args.issue_left
    if not left_issue:
        print('No such issue:', args.issue_left)
        return (1, False)
    right_issue = args.issue_right
    if not right_issue:
        print('No such issue:', args.issue_right)
        return (1, False)
    link_name = ' '.join(args.text)

    args.project.link(left_issue, right_issue, link_name)
    return (0, True)


def unlink_issues(args):
    args.project.unlink(args.issue_left, args.issue_right)
    return (0, True)


def link_url(args):
    issue = args.issue
    if not issue:
        print('No such issue:', args.issue)
        return (1, False)
    url = args.url
    text = ' '.join(args.text)
    args.project.attach(issue, url, text)
    return (0, True)


def quote_reply(args):
    if args.text:
        raise ValueError('Can\'t both quote-reply and one-shot comment')

    issue_id = args.issue
    issue = args.project.issue(issue_id)

    if args.reply is True:
        # Find last comment if we didn't pick one to reply to; jira
        # keeps them chronologically according to add date
        last_cmt = issue.raw['fields']['comment']['comments'][-1]
        comment_id = last_cmt['id']
    else:
        comment_id = args.reply

    # Don't query jira server again when we have the data
    comment = None
    for cmt in issue.raw['fields']['comment']['comments']:
        if cmt['id'] == comment_id:
            comment = cmt
            break
    if not comment:
        return (1, False)

    starting_text = f"Quoth [~{comment['author']['name']}] - {pretty_date(comment['updated'])}:\n"
    starting_text = starting_text + '\n'.join(['┃ ' + item for item in comment['body'].strip().split('\n')])
    new_text = editor(starting_text)
    if 'visibility' in comment:
        group_name = comment['visibility']['value']
    else:
        group_name = None
    if not new_text or new_text == starting_text:
        print('Canceled')
        return (0, False)
    args.project.comment(issue_id, new_text, group_name)
    return (0, False)


def comment(args):
    if args.reply:
        return quote_reply(args)

    issue_id = args.issue

    if args.remove:
        comment_id = args.remove
        comment = args.project.get_comment(issue_id, comment_id)
        comment.delete()
        return (0, False)

    if args.edit:
        comment_id = args.edit
        comment = args.project.get_comment(issue_id, comment_id)
        if args.text:
            new_text = ' '.join(args.text)
        else:
            new_text = editor(comment.body)
            if not new_text:
                print('Canceled')
                return (0, False)

        update_args = {'body': new_text}
        update_anyway = False
        if args.group:
            if args.group.lower() == 'all':
                # This took some doing; it's not well-documented.
                # This clears the 'visibility' property of the comment,
                # making it viewable by all users
                update_args['visibility'] = {'identifier': None}
            else:
                update_args['visibility'] = {'type': 'group', 'value': args.group}
            update_anyway = True
        if update_anyway or comment.body != new_text:
            comment.update(**update_args)
        else:
            print('No changes')
        return (0, False)

    if args.group:
        group_name = args.group
    else:
        group_name = None

    if args.text:
        text = ' '.join(args.text)
    else:
        text = editor()

    if not len(text):
        print('Canceled')
        return (0, False)

    args.project.comment(issue_id, text, group_name)
    return (0, False)


def display_comment(server_url, comment, verbose, no_format):
    # Let's get fancy
    commentator_url = f"{server_url}/secure/ViewProfile.jspa?name={comment['updateAuthor']['key']}"
    commentator = link_string(comment['updateAuthor']['displayName'], commentator_url)
    print(commentator, '-', pretty_date(comment['updated']), '• ID:', comment['id'])
    if 'visibility' in comment:
        print('🔒', comment['visibility']['type'], '•', comment['visibility']['value'])
    hbar(20)
    md_print(comment['body'], no_format)
    print()


def print_labels(issue, prefix='Labels: '):
    if 'labels' in issue and len(issue['labels']):
        print(prefix, end='')
        for label in issue['labels']:
            print(label, end=' ')
        print()


def print_issue_links(issue, baseurl=None):
    hbar_under('Issue Links')
    matrix = []
    for link in issue['issuelinks']:
        if 'outwardIssue' in link:
            text = EscapedString(link['type']['outward'] + ' ') + issue_link_string(link['outwardIssue']['key'], baseurl)
            status = link['outwardIssue']['fields']['status']['name']
            desc = link['outwardIssue']['fields']['summary']
        elif 'inwardIssue' in link:
            text = EscapedString(link['type']['inward'] + ' ') + issue_link_string(link['inwardIssue']['key'], baseurl)
            status = link['inwardIssue']['fields']['status']['name']
            desc = link['inwardIssue']['fields']['summary']
        # color_string throws off length calculations
        matrix.append([text, status, desc])
    render_matrix(matrix, False, False)
    print()


def print_remote_links(links):
    hbar_under('External Links')
    matrix = []
    for link in links:
        # color_string throws off length calculations
        lid = str(link.raw['id'])
        text = link.raw['object']['title']
        url = link.raw['object']['url']
        if ret := link_string(text, url):
            matrix.append([lid, ret])
        else:
            matrix.append([lid, text, url])
    render_matrix(matrix, False, False)
    print()


def print_attachments(attachments):
    hbar_under('Attachments')
    matrix = []
    for attachment in attachments:
        # color_string throws off length calculations
        aid = str(attachment['id'])
        text = attachment['filename']
        url = attachment['content']
        if ret := link_string(text, url):
            matrix.append([aid, ret])
        else:
            matrix.append([aid, text, url])
    render_matrix(matrix, False, False)
    print()


# Dict from search or subtask list
def _print_issue_list(header, issues, baseurl=None):
    if not issues:
        return
    hbar_under(header)
    matrix = []
    for task in issues:
        if isinstance(task, str):
            task = issues[task]
        try:
            task_key = issue_link_string(task.key, baseurl)
            status = task.raw['fields']['status']['name']
            summary = task.raw['fields']['summary']
        except AttributeError:
            task_key = issue_link_string(task['key'], baseurl)
            status = task['fields']['status']['name']
            summary = task['fields']['summary']
        matrix.append([task_key, status, summary])
    render_matrix(matrix, False, False)
    print()


def print_subtasks(issue, baseurl=None):
    _print_issue_list('Sub-tasks', issue['subtasks'], baseurl)


def print_eausm_votes(project, issue):
    votes = project.eausm_issue_votes(issue)
    if votes and 'votes' in votes and len(votes['votes']):
        mx = [['Vote', 'Points']]
        for vote in votes['votes']:
            user = project.jira.user_by_key(vote['userId'])
            mx.append([user.displayName, vote['vote']])
        render_matrix(mx)
        print()


def print_issue(project, issue_obj, verbose=False, no_comments=False, no_format=False, allowed_fields=None):
    if verbose:
        # Get votes and watchers in verbose mode
        project.votes(issue_obj)
        project.watchers(issue_obj)

    issue = issue_obj.raw['fields']

    if allowed_fields:
        allowed_fields = parse_field_widths(allowed_fields)
        disp = {}
        allowed_ids = [project.field_to_id(field) for field in allowed_fields]
        for field_id in allowed_ids:
            if field_id in issue:
                disp[field_id] = issue[field_id]
        issue = disp

    key_link = issue_link_string(issue_obj.key, project.jira.server_url)
    lsize = max(len(key_link), max_field_width(issue, verbose, project.allow_code))
    lsize = max(lsize, len('Next States'))

    if 'summary' in issue and issue['summary']:
        vsep_print(' ', 0, key_link, lsize, issue['summary'])
    render_issue_fields(issue, verbose, project.allow_code, lsize)

    if verbose:
        vsep_print(' ', 0, 'ID', lsize, issue_obj.raw['id'])
        vsep_print(None, 0, 'URL', lsize, issue_obj.permalink())
        trans = project.transitions(issue_obj.raw['key'])
        if trans:
            vsep_print(' ', 0, 'Next States', lsize, [tr['name'] for tr in trans])
        else:
            vsep_print(None, 0, 'Next States', lsize, 'No valid transitions; cannot alter status')

    print()
    if 'description' in issue and issue['description']:
        md_print(issue['description'], no_format)
        print()

    if 'issuelinks' in issue and len(issue['issuelinks']):
        print_issue_links(issue, project.jira.server_url)

    # Don't print external links or votes unless in verbose mode since it's
    # another API call?
    if verbose:
        print_eausm_votes(project, issue_obj)

        links = project.remote_links(issue_obj)
        if links:
            print_remote_links(links)

        if 'attachment' in issue and len(issue['attachment']):
            print_attachments(issue['attachment'])

    if 'subtasks' in issue and len(issue['subtasks']):
        print_subtasks(issue, project.jira.server_url)

    if 'issuetype' in issue:
        for megalith in ('Epic', 'Feature'):
            if issue['issuetype']['name'] == megalith:
                ret = project.search_issues(f'"{megalith} Link" = "' + issue_obj.raw['key'] + '"')
                _print_issue_list(f'Issues in {megalith}', ret, project.jira.server_url)

    if no_comments or 'comment' not in issue:
        return
    if issue['comment']['comments']:
        hbar_under('Comments')

        for cmt in issue['comment']['comments']:
            display_comment(project.jira.server_url, cmt, verbose, no_format)


def cat(args):
    issues = []
    for issue_idx in args.issue_id:
        issue = args.project.issue(issue_idx, True)
        if not issue:
            print('No such issue:', issue_idx)
            return (127, False)
        issues.append(issue)

    if not args.fields:
        fields = args.project.get_user_data('issue_fields')
        if fields:
            setattr(args, 'fields', fields)

    if args.format in ['csv']:
        print_issues(issues, args)
        return (0, False)

    if args.no_format:
        no_format = args.no_format
    else:
        no_format = args.project.get_user_data('no_format')

    for issue in issues:
        print_issue(args.project, issue, args.verbose, args.no_comments, no_format, args.fields)
    return (0, False)


def join_issue_text(name, desc):
    if desc:
        return name + '\n\n' + desc
    return name + '\n\n'


def edit_issue(args):
    issue_idx = args.issue

    issue_obj = args.project.issue(issue_idx)
    issue = issue_obj.raw['fields']
    issue_text = join_issue_text(issue['summary'], issue['description'])
    if args.text:
        new_text = ' '.join(args.text)
    else:
        new_text = editor(issue_text)
    if not new_text:
        print('Canceled')
        return (0, False)
    name, desc = split_issue_text(new_text)
    update_args = {}
    if issue['summary'] != name and issue['summary']:
        update_args['summary'] = name
    if issue['description'] != desc:
        update_args['description'] = desc
    if update_args != {}:
        args.project.update_issue(issue_idx, **update_args)
    else:
        print('No changes')
    return (0, False)


def view_issue(args):
    issue_id = args.issue_id
    issue = args.project.issue(issue_id)
    if not issue:
        return (127, False)
    os.system('xdg-open ' + issue.permalink())
    return (0, False)


def assign_issue(args):
    args.project.assign(args.issue_id, args.user)
    return (0, False)


def unassign_issue(args):
    args.project.assign(args.issue_id, 'none')
    return (0, False)


def user_info(args):
    user_info = [GenericArgs(args.project.user)]
    print_users(user_info)
    return (0, False)


def component_ops(args):
    if args.remove:
        # Explicitly one at a time
        ret = args.project.remove_component(args.remove[0])
        return (0, False)

    if args.add:
        if len(args.add) == 1:
            ret = args.project.add_component(args.add[0])
        else:
            ret = args.project.add_component(args.add[0], ' '.join(args.add[1:]))
        if ret:
            return (0, False)
        return (1, False)

    return (1, False)


def call_api(args):
    data = args.project.api_call(args.resource, args.raw)
    if data:
        if args.raw:
            print(data)
        else:
            pretty_print(data)
        return (0, False)
    return (1, False)


def component_list(args):
    comps_data = args.project.components()
    comp_info = {}
    for comp in comps_data:
        if not args.search or re.search(args.search, comp.raw['name']) or not args.quiet and 'description' in comp.raw and re.search(args.search, comp.raw['description']):
            name = comp.raw['name']
            if 'description' not in comp.raw:
                comp_info[name] = {'name': name, 'description': ''}
            else:
                comp_info[name] = {'name': name, 'description': comp.raw['description'].strip()}
    comp_names = sorted(list(comp_info.keys()))

    if args.fields:
        field_arg = args.fields
    else:
        field_arg = args.project.get_user_data('component_fields')

    if field_arg:
        fields = parse_field_widths(field_arg, allowed_fields=['name', 'description'])
    else:
        fields = OrderedDict({'name': 0, 'description': 0})

    if args.quiet:
        for name in comp_names:
            print(name)
    else:
        keys = [fk for fk in fields.keys()]
        matrix = [keys]
        for name in comp_names:
            matrix.append([truncate(comp_info[name][fk], fields[fk]) for fk in keys])
        render_matrix(matrix, fmt=args.format)

    return (0, False)


def sprint_info(args):
    if args.sprint_id:
        search = f'sprint = {args.sprint_id}'
        if not args.all_types:
            search = search + f' and issuetype != {_subtask}'
        if not args.closed:
            search = search + ' and statusCategory != Done'
        if args.new:
            search = search + ' and statusCategory = New'
        if args.raw:
            if args.raw.lower().strip().starswith('order'):
                search = search + f' {args.raw}'
            else:
                search = search + f' and {args.raw}'
        # FIXME: This doesn't allow for field substring ("order" in the
        # "summary" field, for example)
        if not args.raw or 'order' not in args.raw.lower():
            search = search + ' order by rank desc'
        issues = args.project.search_issues(search)
        print_issues(issues, args, exclude_fields=['sprint'])
        return (0, False)

    # General Sprit information
    if args.closed:
        info = args.project.sprint_info(states=['active', 'future', 'closed'])
    else:
        info = args.project.sprint_info()

    board_by_id = {}
    for board in info['boards']:
        # This is a dict, we want the board, not key
        board = info['boards'][board]
        board_by_id[board.id] = board

    matrix = [['name', 'id', 'status', 'start', 'end', 'board']]
    for sprint in info['sprints']:
        sprint = info['sprints'][sprint]
        if sprint.state not in ('active', 'future') and not args.closed:
            continue
        try:
            board_name = board_by_id[sprint.originBoardId]
        except KeyError:
            board_name = '???'
        matrix.append([sprint.name, sprint.id, sprint.state, pretty_date(sprint.startDate), pretty_date(sprint.endDate), board_name])
    if len(info) > 1:
        header = not (args.format in ['csv'])
        render_matrix(matrix, fmt=args.format, header=header)

    return (0, False)


def eausm_vote(args):
    issues = args.project.issues(args.issue_id)
    for issue in issues:
        args.project.eausm_vote_issue(issue, args.vote)
    return (0, False)


def vote(args):
    issues = args.project.issues(args.issue_id)
    for issue in issues:
        if args.remove:
            args.project.jira.remove_vote(issue.key)
        else:
            args.project.jira.add_vote(issue.key)
    return (0, False)


def get_jira_project(project=None, config=None, config_file=None, **kwargs):
    # project: Project key
    # config: dict / pre-read JSON data
    if not config:
        config = get_config(config_file)
    allow_code = False

    if 'jira' not in config:
        print('No JIRA configuration available')
        return None
    jconfig = config['jira']

    if not project:
        if 'default_project' in jconfig and not project:
            project = jconfig['default_project']
        else:
            print('No JIRA project specified')
            return None

    # Allows users to represent custom fields in output.
    # Not recommended to enable.
    if 'here_there_be_dragons' in jconfig:
        if jconfig['here_there_be_dragons'] is True:
            allow_code = True

    # Configure fancy output rendering if specified
    if 'fancy_output' in jconfig and jconfig['fancy_output']:
        import jirate.decor  # NOQA
        jirate.decor.fancy_output = True
        if 'color_shift' in jconfig:
            jirate.decor.color_shift = int(jconfig['color_shift'])

    if not project:
        # Not sure why I used an array here
        project = jconfig['default_project']
    if 'proxies' not in jconfig:
        jconfig['proxies'] = {"http": "", "https": ""}

    if 'cache_expire' in jconfig:
        expire = jconfig['cache_expire']
    else:
        expire = None

    if 'cache_file' in jconfig:
        cache_file = jconfig['cache_file']
    else:
        cache_file = '~/.jirate.cache'

    jira = get_jira(jconfig)
    cache = RequestCache(jira._session, filename=cache_file, expire=expire)
    proj = JiraProject(jira, project, readonly=False, allow_code=allow_code)
    proj.request_cache = cache
    for key in jconfig:
        if key not in ['custom_fields', 'proxies', 'here_there_be_dragons', 'url', 'token', 'default_project', 'proxies']:
            proj.set_user_data(key, jconfig[key])

    if 'custom_fields' in jconfig:
        if isinstance(jconfig['custom_fields'], str):
            proj.custom_fields = get_config(jconfig['custom_fields'])
        else:
            proj.custom_fields = copy.deepcopy(jconfig['custom_fields'])
    else:
        proj.custom_fields = []

    # CLI field parsing definition
    field_info = None
    if 'field' in kwargs and kwargs['field']:
        field_name = kwargs['field'][0]
        field_info = json.loads(kwargs['field'][1])
        field_id = proj.field_to_id(field_name)
        found = False
        for cf in proj.custom_fields:
            if cf['id'] == field_id:
                found = True
                for key in field_info:
                    # TODO update custom field call in jboard?
                    cf[key] = field_info[key]
                break
        if not found:
            # No config present: Create a field definition on the fly
            field_info['id'] = field_id
            field_info['name'] = proj.field_to_human(field_id)
            proj.custom_fields.append(field_info)

    apply_field_renderers(proj.jira.fields(), False)
    if proj.custom_fields:
        reorder = True
        if 'custom_reorder' in jconfig:
            reorder = jconfig['custom_reorder']
            if reorder is not False:
                reorder = True
        apply_field_renderers(proj.custom_fields, reorder)
    return proj


def add_list_options(cmd,
                     fields_help='Display these fields in a table',
                     quiet_help='Only print issue IDs'):
    cmd.add_argument('-f', '--fields', help=fields_help)
    cmd.add_argument('-q', '--quiet', default=False, help=quiet_help, action='store_true')
    cmd.add_argument('--compact', default=False, help='Delete columns with no value set in matrix output', action='store_true')


def create_parser():
    parser = ComplicatedArgs()

    parser.add_argument('-c', '--config', help='Use this config file (instead of ~/.jirate.json)', default=None)
    parser.add_argument('-p', '--project', help='Use this JIRA project instead of default', default=None, type=str.upper)
    parser.add_argument('-f', '--format', help='Use this format for issue list output', default='default', choices=['default', 'csv'], type=str.lower)
    parser.add_argument('--x-format-field', nargs=2, help='Experimental: apply field formatting from the CLI (field, json)', default=None)
    parser.add_argument('--debug', help='Enable debugging', default=False, action='store_true')

    cmd = parser.command('whoami', help='Display current user information', handler=user_info)

    cmd = parser.command('ls', help='List issue(s)', handler=list_issues)
    cmd.add_argument('-U', '--unassigned', action='store_true', help='Display only issues with no assignee.')
    cmd.add_argument('-u', '--user', help='Display only issues assigned to the specific user.')
    cmd.add_argument('-l', '--labels', action='store_true', help='Display issue labels.')
    cmd.add_argument('-a', '--all', action='store_true', help='Display all issues; do not restrict to one project.')
    add_list_options(cmd)

    cmd.add_argument('status', nargs='?', default=None, help='Restrict to issues in this state')

    cmd = parser.command('search', help='Search issue(s)/user(s) with matching text', handler=search_jira)
    cmd.add_argument('-u', '--user', help='Search for user(s) (max)')
    cmd.add_argument('-n', '--named-search', help='Perform preconfigured named search for issues')
    cmd.add_argument('-r', '--raw', action='store_true', help='Perform raw JQL query')
    cmd.add_argument('--prune-regex', nargs=2, help='Prune results by checking named field against regular expression, removing any that do not match')
    add_list_options(cmd)
    cmd.add_argument('text', nargs='*', help='Search text')

    cmd = parser.command('cat', help='Print issue(s)', handler=cat)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    cmd.add_argument('-N', '--no-comments', action='store_true', default=False, help='Skip comments')
    cmd.add_argument('-n', '--no-format', action='store_true', help='Do not format output using Markdown')
    add_list_options(cmd)
    cmd.add_argument('issue_id', nargs='+', help='Target issue(s)', type=str.upper)

    cmd = parser.command('view', help='Display issue in browser', handler=view_issue)
    cmd.add_argument('issue_id', help='Target issue', type=str.upper)

    parser.command('ll', help='List states available to project', handler=list_states)
    parser.command('lt', help='List issue types available to project', handler=list_issue_types)
    parser.command('link-types', help='Display link types', handler=list_link_types)

    cmd = parser.command('assign', help='Assign issue', handler=assign_issue)
    cmd.add_argument('issue_id', help='Target issue', type=str.upper)
    cmd.add_argument('user', help='Target assignee')
    # cmd.add_argument('users', help='First is assignee; rest are watchers (if none, assign to self)', nargs='*')

    cmd = parser.command('unassign', help='Remove assignee from issue', handler=unassign_issue)
    cmd.add_argument('issue_id', help='Target issue', type=str.upper)

    cmd = parser.command('mv', help='Move issue(s) to new state', handler=move)
    cmd.add_argument('-m', '--mine', action='store_true', help='Also assign to myself')
    cmd.add_argument('-u', '--user', help='Also assign to user')
    cmd.add_argument('src', metavar='issue', nargs='+', help='Issue key(s)')
    cmd.add_argument('target', help='Target state')

    cmd = parser.command('new', help='Create a new issue', handler=new_issue)
    cmd.add_argument('-t', '--type', default='task', help='Issue type (project-dependent)')
    cmd.add_argument('-q', '--quiet', default=False, help='Only print new issue ID after creation (for scripting)', action='store_true')
    cmd.add_argument('text', nargs='*', help='Issue summary')

    cmd = parser.command('create', help='Create a new issue (advanced)', handler=create_issue)
    cmd.add_argument('-t', '--type', default='task', help='Issue type (project-dependent; default is "Task")')
    cmd.add_argument('-q', '--quiet', default=False, help='Only print new issue ID after creation (for scripting)', action='store_true')
    cmd.add_argument('args', nargs='*', help='field1 "value1" field2 "value2" ... fieldN "valueN".  If none specified, print out possible fields and (if applicable) allowed values. Fields marked with an asterisk are required.')

    cmd = parser.command('subtask', help='Create a new subtask', handler=new_subtask)
    cmd.add_argument('-q', '--quiet', default=False, help='Only print subtask ID after creation (for scripting)', action='store_true')
    cmd.add_argument('issue_id', help='Parent issue', type=str.upper)
    cmd.add_argument('text', nargs='*', help='Subtask summary')

    cmd = parser.command('link', help='Create link between two issues', handler=link_issues)
    cmd.add_argument('issue_left', help='First issue', type=str.upper)
    cmd.add_argument('text', nargs='+', help='Link text')
    cmd.add_argument('issue_right', help='Second issue', type=str.upper)

    cmd = parser.command('attach', help='Attach a web link to an issue', handler=link_url)
    cmd.add_argument('issue', help='Issue', type=str.upper)
    cmd.add_argument('url', help='URL to attach')
    cmd.add_argument('text', nargs='+', help='URL Description')

    cmd = parser.command('unlink', help='Remove link(s) between issues or an external link', handler=unlink_issues)
    cmd.add_argument('issue_left', help='First issue', type=str.upper)
    cmd.add_argument('issue_right', help='Second issue (or external link ID)', type=str.upper)

    cmd = parser.command('comment', help='Comment (or remove) on an issue', handler=comment)
    cmd.add_argument('-e', '--edit', help='Comment ID to edit')
    cmd.add_argument('-r', '--remove', help='Comment ID to remove')
    cmd.add_argument('-q', '--reply', nargs='?', help='Comment ID to quote and reply', default=False, const=True)
    cmd.add_argument('-g', '--group', help='Specify comment group visibility')
    cmd.add_argument('issue', help='Issue to operate on')
    cmd.add_argument('text', nargs='*', help='Comment text')

    cmd = parser.command('edit', help='Edit issue description or summary', handler=edit_issue)
    cmd.add_argument('issue', help='Issue')
    cmd.add_argument('text', nargs='*', help='New text')

    cmd = parser.command('field', help='Update field values for an issue', handler=issue_fields)
    cmd.add_argument('issue', help='Issue')
    cmd.add_argument('operation', help='Operation', choices=['add', 'set', 'remove', 'sub'])
    cmd.add_argument('name', help='Name of field to update')
    cmd.add_argument('values', help='Value(s) to update', nargs='*')

    cmd = parser.command('fields', help='List fields (and allowed values, when applicable)', handler=issue_fields)
    cmd.add_argument('-t', '--type', default=None, help='Fields available at creation time for the specified type')
    cmd.add_argument('issue', help='Existing Issue (more fields available here)', nargs='?')

    cmd = parser.command('close', help='Move issue(s) to closed/done/resolved', handler=close_issues)
    cmd.add_argument('--subtasks', help='Close subtasks, too', default=False, action='store_true')
    cmd.add_argument('-r', '--resolution', help='Set resolution on transition')
    cmd.add_argument('target', nargs='+', help='Target issue(s)')

    cmd = parser.command('call-api', help='Call an API directly and print the resulting JSON', handler=call_api)
    cmd.add_argument('--raw', help='Produce raw JSON instead of a Python object', default=False, action='store_true')
    cmd.add_argument('resource', help='Location sans host/REST version (e.g. self, issue/KEY-123')

    cmd = parser.command('component', help='Modify component(s)', handler=component_ops)
    cmd.add_argument('-a', '--add', help='Component to add', nargs='+')
    cmd.add_argument('-r', '--remove', help='Component to remove', nargs=1)

    cmd = parser.command('components', help='List components', handler=component_list)
    add_list_options(cmd, quiet_help='Just print component names')
    cmd.add_argument('-s', '--search', help='Search by regular expression')

    cmd = parser.command('template', help='Create issue from YAML template', handler=create_from_template)
    cmd.add_argument('template_file', help='Path to the template file')
    cmd.add_argument('--apply', help='Apply template to existing issue')
    cmd.add_argument('-n', '--non-interactive', default=False, help='Do not prompt for variables', action='store_true')
    cmd.add_argument('-q', '--quiet', default=False, help='Only print new issue IDs after creation (for scripting)', action='store_true')
    cmd.add_argument('--dry-run', default=False, help='Print template with variables substituted; do not file issues', action='store_true')
    cmd.add_argument('vars', help='Variables/values (name value name2 value2 ...)', nargs='*')

    cmd = parser.command('validate', help='Validate a YAML template for use with the "template" command',
                         handler=validate_template)
    cmd.add_argument('template_file', help='Path to the template file')

    cmd = parser.command('generate-template', help='Generate YAML template from existing issue', handler=generate_template)
    cmd.add_argument('issue_id', help='Issue to generate the template from', type=str.upper)
    cmd.add_argument('-a', '--all-fields', default=False, help='Include all fields, even ones that may not make sense for a '
                                                               'template',
                     action='store_true')

    cmd = parser.command('sprint', help='Get Sprint information', handler=sprint_info)
    cmd.add_argument('sprint_id', help='If present, display issues in specific sprint', type=int, nargs='?')
    cmd.add_argument('--all-types', '-A', help='When displaying sprint issues, include subtasks', action='store_true', default=False)
    cmd.add_argument('--new', help='When displaying issues, only list issues not in progress', default=False, action='store_true')
    cmd.add_argument('--raw', '-r', help='When displaying issues, include this additional JQL snippet')
    add_list_options(cmd)
    cmd.add_argument('--closed', help='Include closed sprints or issues', default=False, action='store_true')

    cmd = parser.command('eausm-vote', help='Apply your EZ Agile Planning vote', handler=eausm_vote)
    cmd.add_argument('issue_id', nargs='+', help='Target issue(s)', type=str.upper)
    cmd.add_argument('vote', help='Story Point Value', type=str.upper)

    cmd = parser.command('vote', help='Apply your vote to an issue', handler=vote)
    cmd.add_argument('issue_id', nargs='+', help='Target issue(s)', type=str.upper)
    cmd.add_argument('-r', '--remove', default=False, action='store_true', help='Remove vote from issue(s)')

    return parser


def update_args(args):
    # Special cases
    if len(args) == 3:
        if args[1] == 'field' and args[2] != '-h':
            return [args[0], 'fields', args[2]]
    if len(args) == 4:
        if args[1] == 'field' and '-t' in args:
            return [args[0], 'fields', args[2], args[3]]
    return args


def main():
    parser = create_parser()
    args = update_args(sys.argv)
    ns = parser.parse_args(args=args[1:])

    field = None
    if ns.x_format_field:
        field = ns.x_format_field

    try:
        project = get_jira_project(ns.project, config_file=ns.config, field=field)
    except KeyError:
        print('Configuration faile failed to parse correctly')
        sys.exit(1)
    except FileNotFoundError:
        print('Please create a configuration file (~/.jirate.json)')
        sys.exit(1)
    except Exception as err:
        print(err)
        sys.exit(1)

    # Pass this down in namespace to callbacks
    parser.add_arg('project', project)
    try:
        rc = parser.finalize(ns)
    except JIRAError as err:
        print(err)
        if ns.debug:
            project.request_cache.debug_dump()
        sys.exit(1)
    except Exception as err:
        print(err)
        sys.exit(1)
    if rc:
        ret = rc[0]
        save = rc[1]  # NOQA
    else:
        print('No command specified')
        ret = 0
        save = False  # NOQA

    project.request_cache.save()
    if ns.debug:
        project.request_cache.debug_dump()
    sys.exit(ret)


if __name__ == '__main__':
    main()
