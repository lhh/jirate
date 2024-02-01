#!/usr/bin/python3

import copy
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
from jirate.decor import pretty_print  # NOQA
from jirate.config import get_config
from jirate.jira_fields import apply_field_renderers, render_issue_fields, max_field_width, render_field_data
from jirate.jira_input import transmogrify_input


def move(args):
    if args.user:
        args.project.assign(args.src, args.user)
    if args.mine:
        args.project.assign(args.src, 'me')
    if args.project.move(args.src, args.target):
        print('Moved', args.src, 'to', args.target)
        return (0, False)
    return (1, False)


def close_issues(args):
    ret = 0
    close_args = {}
    if args.resolution:
        close_args['resolution'] = args.resolution
    for issue in args.target:
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


def print_issues_by_field(issue_list, args=None):
    # TODO: sort by column
    fields = OrderedDict({'key': 0})
    fields = parse_field_widths(args.fields, ignore_fields=['key'], starting_fields=fields)

    output = []
    output.append(list(fields.keys()))
    del fields['key']

    found_fields = []
    for issue in issue_list:
        if args and hasattr(args, 'status') and args.status:
            if nym(issue.field('status')['name']) != nym(args.status):
                continue
        row = []
        row.append(issue.key)
        for field in fields:
            field_key = args.project.field_map(field, issue)
            if not field_key:
                row.append('N/A')
                continue
            try:
                raw_fv = issue.field(field_key)
            except AttributeError:
                row.append('N/A')
                continue
            if field not in found_fields:
                found_fields.append(field)
            fk, fv = render_field_data(field_key, issue.raw['fields'], None, args.project.allow_code)
            if fk:
                val = fv
            else:
                val = raw_fv
            row.append(truncate(val, fields[field]))
        output.append(row)

    delta = list(set(list(fields.keys())) - set(found_fields))
    for kill in delta:
        column = None
        for header in range(0, len(output[0])):
            if kill == output[0][header]:
                column = header
                break
        if column is None:
            print(f'Bug: Tried to remove nonexistent column {kill}?')
            continue
        for row in output:
            row.pop(column)

    render_matrix(output)


def print_issues_by_state(issue_list, args=None):
    states = {}

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
            print('  ', issue.key, end=' ')
            if args and args.labels:
                print_labels(issue.raw, prefix='')
            print(issue.raw['fields']['summary'])
        print()


def print_issues(issue_list, args=None):
    if not args:
        return print_issues_by_state(issue_list, args)

    if hasattr(args, 'fields') and args.fields is not None:
        return print_issues_by_field(issue_list, args)

    fields = args.project.get_user_data('default_fields')
    if fields:
        setattr(args, 'fields', fields)
        return print_issues_by_field(issue_list, args)

    return print_issues_by_state(issue_list, args)


def print_users(users):
    matrix = [['Name', 'User Name', 'Email Address']]

    for user in users:
        matrix.append([user.displayName, user.name, user.emailAddress])
    render_matrix(matrix)


def search_jira(args):
    if args.user:
        users = args.project.search_users(args.user)
        if not users:
            print(f'No users match "{args.user}"')
            return (1, False)
        print_users(users)
        return (0, False)

    named = args.named_search
    if not args.text and not named:
        named = 'default'
    if named:
        searches = args.project.get_user_data('searches')
        if named not in searches:
            print(f'No search configured: {named}')
            return (1, False)
        search_query = searches[named]
        ret = args.project.search_issues(search_query)
    else:
        search_query = ' '.join(args.text)
        if args.raw:
            ret = args.project.search_issues(search_query)
        else:
            ret = args.project.search(search_query)

    if not ret:
        return (127, False)
    print_issues(ret, args)
    hbar_over(str(len(ret)) + ' result(s)')
    return (0, False)


def list_issues(args):
    # check for verbose
    if args.unassigned:
        userid = None
    elif args.user:
        userid = args.user
    else:
        userid = 'me'

    issues = args.project.list(userid=userid)
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
    for field in ('description', 'summary', 'assignee', 'issuelinks', 'comment'):
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

    # TODO multi-field sets?
    # transmogrify_input - should this be done in jboard.update_issue?
    # Note that if answer is yes, we have to fetch field metadata there,
    # so we'll want to cache it or pass it down to avoid extra API calls
    field_args = {args.name: ' '.join(args.values)}
    output_args = transmogrify_input(fields, **field_args)

    if not output_args:
        print(f'No field like {args.name} in {issue.key}')
        return (1, False)

    # Set up for the rest
    field_ids = [key for key in output_args.keys()]
    field_id = field_ids[0]
    field = fields[field_id]
    send_val = output_args[field_id]

    ops = field['operations']
    if args.operation not in ops:
        print(f'Cannot perform {args.operation} on {args.issue}; try: {ops}')
        return (1, False)

    # Add and remove use a different format than 'set'.
    # There's also 'modify', but ... that one's even more complicated.
    if args.operation in ['add', 'remove']:
        update_args = {field_id: [{args.operation: val} for val in send_val]}
    else:
        update_args = {field_id: [{args.operation: send_val}]}

    args.project.update_issue(issue.raw['key'], **update_args)
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
        print(f'Valid issue types for {project.project_name}:')
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
        template = yaml.safe_load(yaml_file)

    try:
        validate_template(args)
    except jsonschema.exceptions.ValidationError as e:
        print(f"Provided template file is not valid: {args.template_file}")
        raise e

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
    _subtask = 'Sub-task'  # To prevent case / typos / etc

    # TODO: consider using Jira's bulk issue creation
    # TODO: support reading arbitrary fields from the template
    all_filed = []  # We keep issue keys here because we'll need to refresh anyway

    for issue in template['issues']:
        reserved_fields = ['subtasks']
        required_fields = ['summary']
        if 'project' in issue:
            pname = issue['project']
        else:
            pname = args.project.project_name
        if pname not in metadata_by_type:
            metadata_by_type[pname] = {}

        creation_fields = _parse_creation_args(issue, required_fields, reserved_fields)

        # Cache all metadata now (so we can debug subtask creation if needed.
        issuetype = creation_fields['issuetype']
        if issuetype not in metadata_by_type:
            metadata_by_type[pname][issuetype] = _metadata_by_type(args.project, issuetype)
        if 'subtasks' in issue and issue['subtasks']:
            metadata_by_type[pname][_subtask] = _metadata_by_type(args.project, _subtask)
        metadata = metadata_by_type[pname][issuetype]

        filed = {}
        parent = args.project.create(metadata['fields'], **creation_fields)
        filed['parent'] = parent.key

        if 'subtasks' in issue and issue['subtasks']:
            # Set once
            filed['subtasks'] = []
            for subtask in issue['subtasks']:
                metadata = metadata_by_type[pname][_subtask]
                reserved_fields = ['subtasks', 'issuetype', 'parent']
                # required_fields are the same
                start_fields = {'issuetype': _subtask, 'project': pname}
                start_fields['parent'] = parent.key
                creation_fields = _parse_creation_args(subtask, required_fields, reserved_fields, start_vals=start_fields)

                child = args.project.create(metadata['fields'], **creation_fields)
                filed['subtasks'].append(child.key)
        all_filed.append(filed)

    return all_filed


def validate_template(args):
    with open(args.template_file, 'r') as yaml_file:
        template = yaml.safe_load(yaml_file)

    schema_dir = files('jirate').joinpath('schemas')
    schemas = {}
    for schema_file in ('template.yaml', 'issue.yaml', 'subtask.yaml'):
        schemas[f"jirate:{schema_file}"] = yaml.safe_load(
            schema_dir.joinpath(schema_file).read_text())

    registry = Registry().with_contents([(k, v) for k, v in schemas.items()])
    validator = jsonschema.Draft202012Validator(schema=schemas['jirate:template.yaml'], registry=registry)

    # Will raise a ValidationError with details on what failed:
    validator.validate(template)
    # If we get here it means validation succeeded.
    print(f"Template {args.template_file} is valid.")
    return (0, True)


def new_subtask(args):
    desc = None
    parent_issue = args.project.issue(args.issue_id)

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
    right_issue = args.issue_right
    link_name = ' '.join(args.text)

    args.project.link(left_issue, right_issue, link_name)
    return (0, True)


def unlink_issues(args):
    args.project.unlink(args.issue_left, args.issue_right)
    return (0, True)


def link_url(args):
    issue = args.issue
    url = args.url
    text = ' '.join(args.text)
    args.project.attach(issue, url, text)
    return (0, True)


def comment(args):
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


def display_comment(action, verbose, no_format):
    print(pretty_date(action['updated']), '•', action['updateAuthor']['emailAddress'], '-', action['updateAuthor']['displayName'], '• ID:', action['id'])
    if 'visibility' in action:
        print('🔒', action['visibility']['type'], '•', action['visibility']['value'])
    hbar(20)
    md_print(action['body'], no_format)
    print()


def display_attachment(attachment, verbose):
    print('  ' + attachment['name'])
    if verbose:
        print('    ID:', attachment['id'])
    if attachment['isUpload']:
        if attachment['filename'] != attachment['name']:
            print('    Filename:', attachment['filename'])
    else:
        if attachment['url'] != attachment['name']:
            print('    URL:', attachment['url'])


def print_labels(issue, prefix='Labels: '):
    if 'labels' in issue and len(issue['labels']):
        print(prefix, end='')
        for label in issue['labels']:
            print(label, end=' ')
        print()


def print_issue_links(issue):
    hbar_under('Issue Links')
    matrix = []
    for link in issue['issuelinks']:
        if 'outwardIssue' in link:
            text = link['type']['outward'] + ' ' + link['outwardIssue']['key']
            status = link['outwardIssue']['fields']['status']['name']
            desc = link['outwardIssue']['fields']['summary']
        elif 'inwardIssue' in link:
            text = link['type']['inward'] + ' ' + link['inwardIssue']['key']
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
        text = link.raw['object']['title']
        lid = str(link.raw['id'])
        url = link.raw['object']['url']
        matrix.append([lid, text, url])
    render_matrix(matrix, False, False)
    print()


# Dict from search or subtask list
def _print_issue_list(header, issues):
    if not issues:
        return
    hbar_under(header)
    matrix = []
    for task in issues:
        if isinstance(task, str):
            task = issues[task]
        try:
            task_key = task.key
            status = task.raw['fields']['status']['name']
            summary = task.raw['fields']['summary']
        except AttributeError:
            task_key = task['key']
            status = task['fields']['status']['name']
            summary = task['fields']['summary']
        matrix.append([task_key, status, summary])
    render_matrix(matrix, False, False)
    print()


def print_subtasks(issue):
    _print_issue_list('Sub-tasks', issue['subtasks'])


def print_issue(project, issue_obj, verbose=False, no_comments=False, no_format=False):
    issue = issue_obj.raw['fields']
    lsize = max(len(issue_obj.raw['key']), max_field_width(issue, verbose, project.allow_code))
    lsize = max(lsize, len('Next States'))

    vsep_print(' ', 0, issue_obj.raw['key'], lsize, issue['summary'])
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
    if issue['description']:
        md_print(issue['description'], no_format)
        print()

    if 'issuelinks' in issue and len(issue['issuelinks']):
        print_issue_links(issue)

    # Don't print external links unless in verbose mode since it's another API call?
    if verbose:
        links = project.remote_links(issue_obj)
        if links:
            print_remote_links(links)

    if 'subtasks' in issue and len(issue['subtasks']):
        print_subtasks(issue)

    if issue['issuetype']['name'] == 'Epic':
        ret = project.search_issues('"Epic Link" = "' + issue_obj.raw['key'] + '"')
        _print_issue_list('Issues in Epic', ret)

    if no_comments:
        return
    if issue['comment']['comments']:
        hbar_under('Comments')

        for cmt in issue['comment']['comments']:
            display_comment(cmt, verbose, no_format)


def cat(args):
    issues = []
    for issue_idx in args.issue_id:
        issue = args.project.issue(issue_idx, True)
        if not issue:
            print('No such issue:', issue_idx)
            return (127, False)
        issues.append(issue)

    for issue in issues:
        print_issue(args.project, issue, args.verbose, args.no_comments, args.no_format)
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
        render_matrix(matrix)

    return (0, False)


def get_project(project=None, config=None, config_file=None):
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

    if not project:
        # Not sure why I used an array here
        project = jconfig['default_project']
    if 'proxies' not in jconfig:
        jconfig['proxies'] = {"http": "", "https": ""}

    jira = get_jira(jconfig)
    proj = JiraProject(jira, project, readonly=False, allow_code=allow_code)
    for key in jconfig:
        if key not in ['custom_fields', 'proxies', 'here_there_be_dragons', 'url', 'token', 'default_project', 'proxies']:
            proj.set_user_data(key, jconfig[key])

    if 'custom_fields' in jconfig:
        proj.custom_fields = copy.deepcopy(jconfig['custom_fields'])
        apply_field_renderers(proj.custom_fields)
    else:
        apply_field_renderers()

    return proj


def create_parser():
    parser = ComplicatedArgs()

    parser.add_argument('-p', '--project', help='Use this JIRA project instead of default', default=None, type=str.upper)

    cmd = parser.command('whoami', help='Display current user information', handler=user_info)

    cmd = parser.command('ls', help='List issue(s)', handler=list_issues)
    cmd.add_argument('-U', '--unassigned', action='store_true', help='Display only issues with no assignee.')
    cmd.add_argument('-u', '--user', help='Display only issues assigned to the specific user.')
    cmd.add_argument('-l', '--labels', action='store_true', help='Display issue labels.')
    cmd.add_argument('-f', '--fields', help='Display these fields in a table.')
    cmd.add_argument('status', nargs='?', default=None, help='Restrict to issues in this state')

    cmd = parser.command('search', help='Search issue(s)/user(s) with matching text', handler=search_jira)
    cmd.add_argument('-u', '--user', help='Search for user(s) (max)')
    cmd.add_argument('-n', '--named-search', help='Perform preconfigured named search for issues')
    cmd.add_argument('-r', '--raw', action='store_true', help='Perform raw JQL query')
    cmd.add_argument('-f', '--fields', help='Display these fields in a table.')
    cmd.add_argument('text', nargs='*', help='Search text')

    cmd = parser.command('cat', help='Print issue(s)', handler=cat)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    cmd.add_argument('-N', '--no-comments', action='store_true', default=False, help='Skip comments')
    cmd.add_argument('-n', '--no-format', action='store_true', help='Do not format output using Markdown')
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
    cmd.add_argument('-g', '--group', help='Specify comment group visibility')
    cmd.add_argument('issue', help='Issue to operate on')
    cmd.add_argument('text', nargs='*', help='Comment text')

    cmd = parser.command('edit', help='Edit issue description or summary', handler=edit_issue)
    cmd.add_argument('issue', help='Issue')
    cmd.add_argument('text', nargs='*', help='New text')

    cmd = parser.command('field', help='Update field values for an issue', handler=issue_fields)
    cmd.add_argument('issue', help='Issue')
    cmd.add_argument('operation', help='Operation', choices=['add', 'set', 'remove'])
    cmd.add_argument('name', help='Name of field to update')
    cmd.add_argument('values', help='Value(s) to update', nargs='*')

    cmd = parser.command('fields', help='List fields (and allowed values, when applicable)', handler=issue_fields)
    cmd.add_argument('-t', '--type', default=None, help='Fields available at creation time for the specified type')
    cmd.add_argument('issue', help='Existing Issue (more fields available here)', nargs='?')

    cmd = parser.command('close', help='Move issue(s) to closed/done/resolved', handler=close_issues)
    cmd.add_argument('-r', '--resolution', help='Set resolution on transition')
    cmd.add_argument('target', nargs='+', help='Target issue(s)')

    cmd = parser.command('call-api', help='Call an API directly and print the resulting JSON', handler=call_api)
    cmd.add_argument('--raw', help='Produce raw JSON instead of a Python object', default=False, action='store_true')
    cmd.add_argument('resource', help='Location sans host/REST version (e.g. self, issue/KEY-123')

    cmd = parser.command('component', help='Modify component(s)', handler=component_ops)
    cmd.add_argument('-a', '--add', help='Component to add', nargs='+')
    cmd.add_argument('-r', '--remove', help='Component to remove', nargs=1)

    cmd = parser.command('components', help='List components', handler=component_list)
    cmd.add_argument('-f', '--fields', help='Field delimiters', default=None)
    cmd.add_argument('-q', '--quiet', help='Just print component names', default=False, action='store_true')
    cmd.add_argument('-s', '--search', help='Search by regular expression')

    cmd = parser.command('template', help='Create issue from YAML template', handler=create_from_template)
    cmd.add_argument('template_file', help='Path to the template file')
    cmd.add_argument('-q', '--quiet', default=False, help='Only print new issue IDs after creation (for scripting)', action='store_true')

    cmd = parser.command('validate', help='Validate a YAML template for use with the "template" command',
                         handler=validate_template)
    cmd.add_argument('template_file', help='Path to the template file')

    # TODO: build template from existing issue(s)

    return parser


def main():
    parser = create_parser()
    ns = parser.parse_args()

    try:
        project = get_project(ns.project)
    except KeyError:
        sys.exit(1)
    except FileNotFoundError:
        print('Please create a configuration file (~/.jirate.json)')
        sys.exit(1)
    except JIRAError as err:
        print(err)
        sys.exit(1)

    # Pass this down in namespace to callbacks
    parser.add_arg('project', project)
    try:
        rc = parser.finalize(ns)
    except JIRAError as err:
        print(err)
        sys.exit(1)
    if rc:
        ret = rc[0]
        save = rc[1]  # NOQA
    else:
        print('No command specified')
        ret = 0
        save = False  # NOQA
    sys.exit(ret)


if __name__ == '__main__':
    main()
