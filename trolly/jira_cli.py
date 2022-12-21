#!/usr/bin/python3

import json
import os
import sys

import editor

from jira import JIRA

from trolly.args import ComplicatedArgs
from trolly.jboard import JiraProject
from trolly.decor import md_print, pretty_date, color_string, hbar_under


def jira_get_config():
    config_file = open(os.path.expanduser('~/.trolly.json'))
    config_data = config_file.read()
    config_file.close()
    config = json.loads(config_data)

    return config


def move(args):
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


def print_issues_simple(issues, args=None):
    states = {}
    if args:
        project_states = args.project.states()

    for issue in issues:
        cstatus = issues[issue]['fields']['status']['name']
        if args and args.status:
            status = project_states[args.status]['name']
            if cstatus != status:
                continue
        if cstatus not in states:
            states[cstatus] = []
        states[cstatus].append(issue)

    for key in states:
        print(key)
        for issue in states[key]:
            print('  ', issue, end=' ')
            if args and args.labels:
                print_labels(issues[issue], prefix='')
            print(issues[issue]['fields']['summary'])


def search_issues(args):
    ret = args.project.search(' '.join(args.text))
    if not ret:
        return (127, False)
    print_issues_simple(ret)
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
    print_issues_simple(issues, args)
    return (0, True)


def list_states(args):
    states = args.project.states()
    for name in states:
        print('  ', name, states[name]['name'])
    return (0, False)


def list_issue_types(args):
    issue_types = args.project.issue_types()
    for itype in issue_types:
        print('  ', itype.name)
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
    print_issue(args.project, issue, False)
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
    print_issue(args.project, issue, False)
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
        if comment.body != new_text:
            comment.update(body=new_text)
        else:
            print('No changes')
        return (0, False)

    if args.text:
        text = ' '.join(args.text)
    else:
        text = editor()

    if not len(text):
        print('Canceled')
        return (0, False)

    args.project.comment(issue_id, text)
    return (0, False)


def refresh(args):
    args.project.refresh()
    args.project.index_issues()
    return (0, True)


def display_comment(action, verbose):
    print(pretty_date(action['updated']), '*', action['updateAuthor']['emailAddress'], '-', action['updateAuthor']['displayName'], '* ID:', action['id'])
    md_print(action['body'])
    print()


def display_state(action, verbose):
    if not verbose:
        return
    data = action['data']
    if data['issue']['closed']:
        print(action['date'], '- Closed by', action['memberCreator']['username'])
    else:
        print(action['date'], '- Opened by', action['memberCreator']['username'])


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


def print_issue(project, issue_obj, verbose):
    issue = issue_obj.raw['fields']

    lsize = max(len(issue_obj.raw['key']), len('Next States'))
    sep = '┃'

    print(issue_obj.raw['key'].ljust(lsize), sep, issue['summary'])
    print('Created'.ljust(lsize), sep, pretty_date(issue['created']), end=' ')
    if issue['created'] != issue['updated']:
        dstr = pretty_date(issue['updated'])
        print(f'(Updated {dstr})')
    else:
        print()

    if 'parent' in issue and issue['parent']:
        print('Parent'.ljust(lsize), sep, issue['parent']['key'])
    print('Status'.ljust(lsize), sep, color_string(issue['status']['name'], 'white', issue['status']['statusCategory']['colorName']))

    if verbose:
        print('Creator'.ljust(lsize), sep, issue['creator']['emailAddress'], '-', issue['creator']['displayName'])
        if issue['reporter'] is not None and issue['reporter']['emailAddress'] != issue['creator']['emailAddress']:
            print('Reporter'.ljust(lsize), sep, issue['reporter']['emailAddress'], '-', issue['creator']['displayName'])
        print('Type'.ljust(lsize), sep, issue['issuetype']['name'])
        print('ID'.ljust(lsize), sep, issue_obj.raw['id'])
        print('URL'.ljust(lsize), sep, issue_obj.permalink())

    if 'assignee' in issue and issue['assignee'] and 'name' in issue['assignee']:
        print('Assignee'.ljust(lsize), sep, end=' ')
        print(issue['assignee']['emailAddress'], '-', issue['assignee']['displayName'])
        # todo: add watchers (verbose)
    print_labels(issue, prefix='Labels'.ljust(lsize) + f' {sep} ')

    if verbose:
        trans = project.transitions(issue_obj.raw['key'])
        print('Next States'.ljust(lsize), sep, end=' ')
        if trans:
            print([tr['name'] for tr in trans.values()])
        else:
            print('No valid transitions; cannot alter status')

    print()
    if issue['description']:
        md_print(issue['description'])
        print()

    # todo: separate function for this kind of thing
    if 'issuelinks' in issue and len(issue['issuelinks']):
        hbar_under('Issue Links')
        # pass 1: Get the lengths so we can draw separators
        lsize = 0
        rsize = 0
        for link in issue['issuelinks']:
            if 'outwardIssue' in link:
                text = link['type']['outward'] + ' ' + link['outwardIssue']['key']
                status = link['outwardIssue']['fields']['status']
            elif 'inwardIssue' in link:
                text = link['type']['inward'] + ' ' + link['inwardIssue']['key']
                status = link['inwardIssue']['fields']['status']

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
            print(text.ljust(lsize), sep, color_string(status['name'].ljust(rsize), status['statusCategory']['colorName']), sep, desc)
        print()

    # todo: separate function for this kind of thing
    if 'subtasks' in issue and len(issue['subtasks']):
        hbar_under('Sub-tasks')
        # pass 1: Get the lengths so we can draw separators
        lsize = 0
        rsize = 0
        for task in issue['subtasks']:
            task_key = task['key']
            status = task['fields']['status']['name']
            if len(task_key) > lsize:
                lsize = len(task_key)
            if len(status) > rsize:
                lsize = len(status)
        # pass 2: print the stuff
        for task in issue['subtasks']:
            task_key = task['key']
            status = task['fields']['status']
            print(task_key, sep, color_string(status['name'], status['statusCategory']['colorName']), sep, task['fields']['summary'])
        print()

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
        print_issue(args.project, issue, args.verbose)
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


def get_project(project=None):
    config = jira_get_config()

    if 'jira' not in config:
        print('No JIRA configuration available')
        return None
    if 'url' not in config['jira']:
        print('No JIRA URL specified')
        return None
    if 'token' not in config['jira']:
        print('No JIRA token specified')
        return None
    if 'default_project' not in config['jira']:
        print('No default JIRA project specified')
        return None

    jconfig = config['jira']
    if not project:
        # Not sure why I used an array here
        project = jconfig['default_project']

    jira = JIRA(jconfig['url'], token_auth=jconfig['token'])
    return JiraProject(jira, project, readonly=False)


def create_parser():
    parser = ComplicatedArgs()

    parser.add_argument('-p', '--project', help='Use this JIRA project instead of default', default=None, type=str.upper)

    cmd = parser.command('ls', help='List issue(s)', handler=list_issues)
    cmd.add_argument('-m', '--mine', action='store_true', help='Display only issues assigned to me.')
    cmd.add_argument('-U', '--unassigned', action='store_true', help='Display only issues with no assignee.')
    cmd.add_argument('-u', '--user', help='Display only issues assigned to the specific user.')
    cmd.add_argument('-l', '--labels', action='store_true', help='Display issue labels.')
    cmd.add_argument('status', nargs='?', default=None, help='Restrict to issues in this state')

    cmd = parser.command('search', help='List issue(s) with matching text', handler=search_issues)
    cmd.add_argument('text', nargs='*', help='Search text')

    cmd = parser.command('cat', help='Print issue(s)', handler=cat)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    cmd.add_argument('issue_id', nargs='+', help='Target issue(s)', type=str.upper)

    cmd = parser.command('view', help='Display issue in browser', handler=view_issue)
    cmd.add_argument('issue_id', help='Target issue', type=str.upper)

    parser.command('ll', help='List states available to project', handler=list_states)
    parser.command('lt', help='List issue types available to project', handler=list_issue_types)

    cmd = parser.command('assign', help='Assign issue', handler=assign_issue)
    cmd.add_argument('issue_id', help='Target issue', type=str.upper)
    cmd.add_argument('user', help='Target assignee')
    # cmd.add_argument('users', help='First is assignee; rest are watchers (if none, assign to self)', nargs='*')

    cmd = parser.command('unassign', help='Remove assignee from issue', handler=unassign_issue)
    cmd.add_argument('issue_id', help='Target issue', type=str.upper)
    # cmd.add_argument('members', help='Issue assignees/watchers (if none, remove only self)', nargs='*')

    cmd = parser.command('mv', help='Move issue(s) to new state', handler=move)
    cmd.add_argument('src', metavar='issue', nargs='+', help='Issue key(s)')
    cmd.add_argument('target', help='Target state')

    cmd = parser.command('new', help='Create a new issue', handler=new_issue)
    cmd.add_argument('-t', '--type', default='task', help='Issue type (project-dependent)')
    cmd.add_argument('text', nargs='*', help='Issue summary')

    cmd = parser.command('subtask', help='Create a new subtask', handler=new_subtask)
    cmd.add_argument('issue_id', help='Parent issue', type=str.upper)
    cmd.add_argument('text', nargs='*', help='Subtask summary')

    cmd = parser.command('comment', help='Comment (or remove) on an issue', handler=comment)
    cmd.add_argument('-e', '--edit', help='Comment ID to edit')
    cmd.add_argument('-r', '--remove', help='Comment ID to remove')
    cmd.add_argument('issue', help='Issue to operate on')
    cmd.add_argument('text', nargs='*', help='Comment text')

    cmd = parser.command('edit', help='Edit comment text', handler=edit_issue)
    cmd.add_argument('issue', help='Issue')
    cmd.add_argument('text', nargs='*', help='New text')

    cmd = parser.command('close', help='Move issue(s) to closed/done/resolved', handler=close_issues)
    cmd.add_argument('target', nargs='+', help='Target issue(s)')

    return parser


def main():
    parser = create_parser()
    ns = parser.parse_args()

    try:
        project = get_project(ns.project)
    except KeyError:
        sys.exit(1)

    # Pass this down in namespace to callbacks
    parser.add_arg('project', project)
    rc = parser.finalize(ns)
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
