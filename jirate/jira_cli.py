#!/usr/bin/python3

import copy
import os
import sys
import yaml

import editor

from jira.exceptions import JIRAError

from jirate.args import ComplicatedArgs, GenericArgs
from jirate.jboard import JiraProject, get_jira
from jirate.decor import md_print, pretty_date, color_string, hbar_under, hbar, hbar_over, nym, vsep_print, vseparator
from jirate.decor import pretty_print  # NOQA
from jirate.config import get_config
from jirate.jira_fields import apply_field_renderers, render_issue_fields, max_field_width


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
    for issue in args.target:
        if not args.project.close(issue):
            ret = 1
    return (ret, False)


def print_issues_by_state(issue_list, args=None):
    states = {}

    for issue in issue_list:
        cstatus = issue.raw['fields']['status']['name']
        if cstatus not in states:
            states[cstatus] = []
        states[cstatus].append(issue)

    for key in states:
        if args and args.status and nym(key) != nym(args.status):
            continue
        hbar_under(key)
        for issue in states[key]:
            print('  ', issue.key, end=' ')
            if args and args.labels:
                print_labels(issue.raw, prefix='')
            print(issue.raw['fields']['summary'])
        print()


def print_users(users):
    nsize = len('Name')
    ksize = len('User Name')
    msize = len('Email Address')

    for user in users:
        nsize = max(nsize, len(user.displayName))
        ksize = max(ksize, len(user.name))
        msize = max(msize, len(user.emailAddress))

    header = 'Name'.ljust(nsize) + '   ' + 'User Name'.ljust(ksize) + '   ' + 'Email Address'.ljust(msize)
    hbar_under(header)
    for user in users:
        vsep_print(None, user.displayName, nsize, user.name, ksize, user.emailAddress)


def search_jira(args):
    if args.user:
        users = args.project.search_users(args.user)
        if not users:
            print('No users match "f{args.user}"')
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
    print_issues_by_state(ret)
    hbar_over(str(len(ret)) + ' result(s)')
    return (0, False)


def list_issues(args):
    # check for verbose
    if args.mine:
        userid = 'me'
    elif args.unassigned:
        userid = 'none'
    elif args.user:
        userid = args.user
    else:
        userid = None

    issues = args.project.list(userid=userid)
    print_issues_by_state(issues, args)
    return (0, True)


def list_link_types(args):
    ltypes = args.project.link_types()
    namelen = len('Outward')
    for lt in ltypes:
        namelen = max(namelen, len(lt.outward))
    blen = vsep_print(None, 'Outward', namelen, 'Inward')
    hbar(blen)
    for lt in ltypes:
        vsep_print(None, lt.outward, namelen, lt.inward)
    return (0, True)


def list_states(args):
    states = args.project.states()
    namelen = 0
    for name in states:
        namelen = max(namelen, len(name))
    for name in states:
        vsep_print(None, name, namelen, states[name]['name'])
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
        nlen = 0
        for field in fields:
            if field.startswith('customfield_'):
                nlen = max(nlen, len(nym(fields[field]['name'])))
            else:
                nlen = max(nlen, len(nym(field)))
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
                fvalue = ', '.join(values)
            vsep_print(' ', fname, nlen, fvalue)
        return (0, False)

    field = None
    for _field in fields:
        if args.name not in (field, fields[_field]['name'], nym(fields[_field]['name']), fields[_field]['fieldId'], nym(fields[_field]['fieldId'])):
            continue
        field = fields[_field]
        break

    if not field:
        key = issue.raw['key']
        print(f'No field like \'{args.name}\' field in {key}')
        return (1, False)

    ops = field['operations']
    if args.operation not in ops:
        print(f'Cannot perform {args.operation} on {args.issue}; try: {ops}')
        return (1, False)

    # Join stuff if it's not an array
    if 'schema' in field and field['schema']['type'] == 'array':
        start_val = args.values
    else:
        start_val = [' '.join(args.values)]

    # okay time to update them
    found = False
    send_val = []

    # Parse allowedValues and look for name, value, and ID, and their nyms
    if 'allowedValues' in field:
        # Validate that the name or value exists and create our array of IDs
        # corresponding to them.
        for val in start_val:
            found = False
            for av in field['allowedValues']:
                if 'archived' in av and av['archived']:
                    continue
                for key in ['name', 'value']:
                    if key not in av:
                        continue
                    if val not in (av[key], nym(av[key])):
                        continue
                    send_val.append({'id': av['id']})
                    found = True
                    break
                if found:
                    break
            if not found:
                print(f'Value {val} not allowed for {args.name}')
                return (1, False)

    # Start with our basic input otherwise; no validation done
    else:
        send_val = start_val

    update_args = []
    # If it's not an array, assume a string for now
    if 'schema' not in field or field['schema']['type'] != 'array':
        send_val = send_val[0]

    # Add and remove use a different format than 'set'.
    # There's also 'modify', but ... that one's even more complicated.
    if args.operation in ['add', 'remove']:
        update_args = {field['fieldId']: [{args.operation: val} for val in send_val]}
    else:
        update_args = {field['fieldId']: [{args.operation: send_val}]}
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


# new_issue is way too easy. Let's make it *incredibly* complicated!
def create_issue(args):
    auto_fields = ['reporter']
    desc = None
    issuetype = args.type if args.type else 'Task'

    # Do sanity check before hitting the JIRA API
    if len(args.args) % 2 == 1:
        print('Incorrect number of arguments (not divisible by 2)')
        return (1, False)

    try:
        metadata = args.project.issue_metadata(args.type)
    except JIRAError as e:
        if 'text: Issue Does Not Exist' in str(e):
            print('The createmeta API does not exist on this JIRA instance.')
        else:
            print(e)
        return (1, False)

    if not metadata:
        print('Invalid issue type:', issuetype)
        print(f'Valid issue types for {args.project.project_name}:')
        list_issue_types(args)
        return (1, False)

    values = {}
    argv = copy.copy(args.args)
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
        values['description'] = desc

    # Nope all the auto-populated things
    for field in auto_fields:
        if field in values:
            del values[field]

    commit_values = {}
    errors = 0

    issuetype = metadata['name']
    values['issuetype'] = issuetype
    values['project'] = args.project.project_name

    # resolve field names
    for field in metadata['fields']:
        if field in auto_fields:
            continue
        fieldname = metadata['fields'][field]['name']
        if field not in values and fieldname not in values and nym(fieldname) not in values:
            if metadata['fields'][field]['required']:
                print(f'Missing required field for {args.project.project_name}/{issuetype}: ' + nym(fieldname))
                errors = errors + 1
            continue
        if field in values:
            commit_values[field] = values[field]
            del values[field]
        if fieldname in values:
            commit_values[field] = values[fieldname]
            del values[fieldname]
        if nym(fieldname) in values:
            commit_values[field] = values[nym(fieldname)]
            del values[nym(fieldname)]

    if values:
        print('WARNING: Input fields is not empty:')
        pretty_print(values)

    if errors:
        print(f'{errors} errors; can\'t create issue')
        return (1, False)

    issue = args.project.create(**commit_values)
    if args.quiet:
        print(issue.raw['key'])
    else:
        print_issue(args.project, issue, False)
    return (0, True)


def create_from_template(args):
    # TODO: consider using Jira's bulk issue creation
    # TODO: support reading arbitrary fields from the template
    all_filed = []  # We keep issue keys here because we'll need to refresh anyway
    with open(args.template_file, 'r') as yaml_file:
        template = yaml.safe_load(yaml_file)

    for issue in template['issues']:
        filed = {}
        if 'description' not in issue:
            issue['description'] = ""
        parent = args.project.new(issue['summary'], description=issue['description'], issue_type=issue['issue_type'])
        filed['parent'] = parent.raw['key']

        if issue['subtasks']:
            filed['subtasks'] = []
            for subtask in issue['subtasks']:
                if 'description' not in subtask:
                    subtask['description'] = ""
                child = args.project.subtask(parent.raw['key'], subtask['summary'], subtask['description'])
                filed['subtasks'].append(child.raw['key'])
        all_filed.append(filed)

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


def refresh(args):
    args.project.refresh()
    args.project.index_issues()
    return (0, True)


def display_comment(action, verbose):
    print(pretty_date(action['updated']), '•', action['updateAuthor']['emailAddress'], '-', action['updateAuthor']['displayName'], '• ID:', action['id'])
    if 'visibility' in action:
        print('🔒', action['visibility']['type'], '•', action['visibility']['value'])
    hbar(20)
    md_print(action['body'])
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
    # pass 1: Get the lengths so we can draw separators
    sep = f' {vseparator} '
    lsize = 0
    rsize = 0
    for link in issue['issuelinks']:
        if 'outwardIssue' in link:
            text = link['type']['outward'] + ' ' + link['outwardIssue']['key']
            status = link['outwardIssue']['fields']['status']['name']
        elif 'inwardIssue' in link:
            text = link['type']['inward'] + ' ' + link['inwardIssue']['key']
            status = link['inwardIssue']['fields']['status']['name']

        if len(text) > lsize:
            lsize = len(text)
        if len(status) > rsize:
            rsize = len(status)
    # pass 2: print the stuff
    for link in issue['issuelinks']:
        if 'outwardIssue' in link:
            text = link['type']['outward'] + ' ' + link['outwardIssue']['key']
            status = link['outwardIssue']['fields']['status']
            desc = link['outwardIssue']['fields']['summary']
        elif 'inwardIssue' in link:
            text = link['type']['inward'] + ' ' + link['inwardIssue']['key']
            status = link['inwardIssue']['fields']['status']
            desc = link['inwardIssue']['fields']['summary']
        # color_string throws off length calculations
        vsep_print(' ', text.ljust(lsize) + sep + color_string(status['name'].ljust(rsize), status['statusCategory']['colorName']), lsize + rsize + 3, desc)
    print()


def print_remote_links(links):
    hbar_under('External Links')

    # pass 1: Get the lengths so we can draw separators
    lsize = 0
    rsize = 0
    for link in links:
        text = link.raw['object']['title']
        lid = str(link.raw['id'])
        if len(lid) > lsize:
            lsize = len(lid)
        if len(text) > rsize:
            rsize = len(text)
    # pass 2: print the stuff
    for link in links:
        # color_string throws off length calculations
        text = link.raw['object']['title']
        lid = str(link.raw['id'])
        url = link.raw['object']['url']
        vsep_print(' ', lid.ljust(lsize), lsize, text.ljust(rsize), rsize, url)
    print()


# Dict from search or subtask list
def _print_issue_list(header, issues):
    if not issues:
        return
    hbar_under(header)
    # pass 1: Get the lengths so we can draw separators
    sep = f' {vseparator} '
    lsize = 0
    rsize = 0
    for task in issues:
        if isinstance(task, str):
            task = issues[task]
        try:
            task_key = task.key
            status = task.raw['fields']['status']['name']
        except AttributeError:
            task_key = task['key']
            status = task['fields']['status']['name']
        if len(task_key) > lsize:
            lsize = len(task_key)
        if len(status) > rsize:
            rsize = len(status)
    # pass 2: print the stuff
    for task in issues:
        if isinstance(task, str):
            task = issues[task]
        try:
            task_key = task.key
            status = task.raw['fields']['status']
            summary = task.raw['fields']['summary']
        except AttributeError:
            task_key = task['key']
            status = task['fields']['status']
            summary = task['fields']['summary']
        # color_string throws off length calculations
        vsep_print(' ', task_key.ljust(lsize) + sep + color_string(status['name'].ljust(rsize), status['statusCategory']['colorName']), lsize + rsize + 3, summary)
    print()


def print_subtasks(issue):
    _print_issue_list('Sub-tasks', issue['subtasks'])


def print_issue(project, issue_obj, verbose=False, no_comments=False):
    issue = issue_obj.raw['fields']
    lsize = max(len(issue_obj.raw['key']), max_field_width(issue, verbose, project.allow_code))
    lsize = max(lsize, len('Next States'))

    vsep_print(' ', issue_obj.raw['key'], lsize, issue['summary'])
    render_issue_fields(issue, verbose, project.allow_code, lsize)

    if verbose:
        vsep_print(' ', 'ID', lsize, issue_obj.raw['id'])
        vsep_print(None, 'URL', lsize, issue_obj.permalink())
        trans = project.transitions(issue_obj.raw['key'])
        if trans:
            vsep_print(' ', 'Next States', lsize, [tr['name'] for tr in trans.values()])
        else:
            vsep_print(None, 'Next States', lsize, 'No valid transitions; cannot alter status')

    print()
    if issue['description']:
        md_print(issue['description'])
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
            display_comment(cmt, verbose)


def cat(args):
    issues = []
    for issue_idx in args.issue_id:
        issue = args.project.issue(issue_idx, True)
        if not issue:
            print('No such issue:', issue_idx)
            return (127, False)
        issues.append(issue)

    for issue in issues:
        print_issue(args.project, issue, args.verbose, args.no_comments)
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


def call_api(args):
    data = args.project.api_call(args.resource)
    if data:
        pretty_print(data)
        return (0, False)
    return (1, False)


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
    proj = JiraProject(jira, project, readonly=False, allow_code=allow_code, simplify=True)
    if 'searches' in jconfig:
        proj.set_user_data('searches', jconfig['searches'])
    if 'custom_fields' in jconfig:
        proj.custom_fields = copy.deepcopy(jconfig['custom_fields'])
        apply_field_renderers(proj.custom_fields)

    return proj


def create_parser():
    parser = ComplicatedArgs()

    parser.add_argument('-p', '--project', help='Use this JIRA project instead of default', default=None, type=str.upper)

    cmd = parser.command('whoami', help='Display current user information', handler=user_info)

    cmd = parser.command('ls', help='List issue(s)', handler=list_issues)
    cmd.add_argument('-m', '--mine', action='store_true', help='Display only issues assigned to me.')
    cmd.add_argument('-U', '--unassigned', action='store_true', help='Display only issues with no assignee.')
    cmd.add_argument('-u', '--user', help='Display only issues assigned to the specific user.')
    cmd.add_argument('-l', '--labels', action='store_true', help='Display issue labels.')
    cmd.add_argument('status', nargs='?', default=None, help='Restrict to issues in this state')

    cmd = parser.command('search', help='Search issue(s)/user(s) with matching text', handler=search_jira)
    cmd.add_argument('-u', '--user', help='Search for user(s) (max)')
    cmd.add_argument('-n', '--named-search', help='Perform preconfigured named search for issues')
    cmd.add_argument('-r', '--raw', action='store_true', help='Perform raw JQL query')
    cmd.add_argument('text', nargs='*', help='Search text')

    cmd = parser.command('cat', help='Print issue(s)', handler=cat)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    cmd.add_argument('-N', '--no-comments', action='store_true', default=False, help='Skip comments')
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
    cmd.add_argument('-t', '--type', default='task', help='Issue type (project-dependent)')
    cmd.add_argument('-q', '--quiet', default=False, help='Only print new issue ID after creation (for scripting)', action='store_true')
    cmd.add_argument('args', nargs='*', help='field1 "value1" field2 "value2" ... fieldN "valueN"')

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
    cmd.add_argument('target', nargs='+', help='Target issue(s)')

    cmd = parser.command('call-api', help='Call an API directly and print the resulting JSON', handler=call_api)
    cmd.add_argument('resource', help='Location sans host/REST version (e.g. self, issue/KEY-123')

    cmd = parser.command('template', help='Create issue from YAML template', handler=create_from_template)
    cmd.add_argument('template_file', help='Path to the template file')
    cmd.add_argument('-q', '--quiet', default=False, help='Only print new issue IDs after creation (for scripting)', action='store_true')

    # TODO: build template from existing issue(s)

    return parser


def main():
    parser = create_parser()
    ns = parser.parse_args()

    try:
        project = get_project(ns.project)
    except KeyError:
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
