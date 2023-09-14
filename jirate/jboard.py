#!/usr/bin/python3

import copy
import os

from jira import JIRAError
from jira.utils import json_loads
from jira.resources import Issue

from jirate.decor import nym
from jirate.jira_input import transmogrify_input


class JiraProject(object):
    def __init__(self, jira, project, closed_status=None, readonly=False, allow_code=False):
        self.jira = jira
        self._ro = readonly
        self._config = None
        self._closed_status = closed_status
        self._project = self.jira.project(project)
        self._user = None
        self._issue_types = None
        self.custom_fields = None
        self.project_name = project
        self.allow_code = allow_code
        self.refresh()

        if self._closed_status is None:
            # guess at common closed states
            for status in ['CLOSED', 'DONE', 'RESOLVED']:
                try:
                    self.status_to_id(status)
                    self._closed_status = status
                    break
                except KeyError:
                    pass

    @property
    def user(self):
        if self._user is None:
            # Get current user info and record it
            url = self._project._get_url('myself')
            self._user = json_loads(self.jira._session.get(url))
        return self._user

    def refresh(self):
        if not self._config:
            self._config = {'states': {},
                            'issue_map': {},
                            'issue_rev_map': {}}

        self.refresh_lists()
        # self.index_issues()

    def refresh_lists(self):
        # DANGER DANGER - using private stuff because upstream doesn't have it
        spath = os.path.join(self._project._resource, 'statuses')
        url = self._project._get_url(spath.format(str(self._project)))
        status_info = json_loads(self.jira._session.get(url))
        status_ids = []
        statuses = []

        for task_type in status_info:
            for status in task_type['statuses']:
                if status['id'] not in status_ids:
                    status_ids.append(status['id'])
                    statuses.append(status)

        for item in statuses:
            val = {}
            val['name'] = item['name']
            val['id'] = item['id']
            name = nym(val['name'])
            while name in self._config['states']:
                name = name + '_'
            self._config['states'][name] = val

    def delete_issue_map(self):
        self._config['issue_map'] = {}

    def search_users(self, username):
        # max is 50 by default; we'll start with that
        users = self.jira.search_users(username)
        return users

    def get_user(self, username):
        # JIRA has internal names that need to be used by API calls;
        # resolve email address if needed
        if '@' not in username:
            return username

        users = self.jira.search_users(username)
        if len(users) > 1:
            raise ValueError(f'Multiple matching users for \'{username}\'')
        elif not users:
            raise ValueError(f'No matching users for \'{username}\'')

        return users[0].name

    def assign(self, issue_aliases, users=None):
        # Eventually: first in list = assignee, rest are watchers
        if isinstance(users, str):
            users = [users]
        if isinstance(issue_aliases, str):
            issue_aliases = [issue_aliases]

        for idx in issue_aliases:
            issue = self.issue(idx)
            if not issue:
                continue

            user_ids = []

            # first is assignee
            if users:
                for user in users:
                    if user == 'me':
                        user = self.user['name']
                    if user == 'none':
                        user_ids.append(None)
                    if user not in user_ids:
                        user_ids.append(self.get_user(user))
            else:
                # Just me
                user = self.user['name']
                user_ids = [user]
                # user_ids = [user['id']]

            if not len(users):
                return

            user = user_ids.pop(0)
            issue.update(assignee=user)

    def update_issue(self, issue_alias, **kwargs):
        issue = self.issue(issue_alias)
        if issue:
            return issue.update(**kwargs)

    def unlabel_issue(self, issue_alias, label_name):
        return False

    def fields(self, issue_alias):
        issue = self.issue(issue_alias)
        # XXX HERE THERE BE DRAGONS
        # NOT IMPLEMENTED UPSTREAM
        url = os.path.join(issue.raw['self'], 'editmeta')
        field_blob = json_loads(self.jira._session.get(url))
        return field_blob['fields']

    def status_to_id(self, status):
        status = nym(status)

        if status not in self._config['states']:
            raise KeyError('No such list: ' + status)
        if status in self._config['states']:
            return self._config['states'][status]['id']
        return status  # must be the ID

    def attach(self, issue_alias, url, description):
        item = {'url': url, 'title': description}
        issue = self.issue(issue_alias)
        return self.jira.add_simple_link(issue, item)

    def _index_issue(self, issue):
        if issue.raw['key'] not in self._config['issue_map']:
            self._config['issue_map'][issue.raw['key']] = issue

    def _index_issues(self, issues):
        if 'issue_map' not in self._config:
            self._config['issue_map'] = {}

        for issue in issues:
            self._index_issue(issue)

    def _search_issues(self, search_query):
        index = 0
        chunk_len = 50      # So we can detect end
        ret = []
        while True:
            issues = self.jira.search_issues(search_query, startAt=index, maxResults=chunk_len)
            if not len(issues):
                break
            self._index_issues(issues)
            ret.extend(issues)
            index = index + len(issues)
            if len(issues) < chunk_len:
                break
        return ret

    def index_issues(self, status=None):
        if status:
            status_id = self.status_to_id(status)
            open_issues = self._search_issues(f'PROJECT = {self.project_name} AND STATUS = {status_id}')
        else:
            open_issues = self._search_issues(f'PROJECT = {self.project_name} AND STATUS != {self._closed_status}')
        self._index_issues(open_issues)
        return open_issues

    def _simplify_issue_list(self, issues, userid=None):
        ret = {}

        for issue in issues:
            issue_info = issue.raw['fields']
            if userid is not None:
                if userid != 'none':  # Special keyword for unassigned
                    if 'assignee' not in issue_info or not issue_info['assignee']:
                        continue
                    # Accept name, key, or email address transparently
                    user = [issue_info['assignee']['name'],
                            issue_info['assignee']['key'],
                            issue_info['assignee']['emailAddress']]
                    if userid not in user:
                        # last ditch effort: search email address field
                        if '@' in userid:
                            continue
                        if not issue_info['assignee']['emailAddress'].startswith(userid + '@'):
                            continue
                else:
                    if 'assignee' in issue_info and issue_info['assignee']:
                        continue

            val = {}
            val['id'] = issue.raw['id']
            val['key'] = issue.raw['key']
            val['fields'] = {}
            val['fields']['status'] = issue_info['status']
            val['fields']['summary'] = issue_info['summary']
            if 'labels' in issue_info:
                val['labels'] = issue_info['labels']

            ret[issue.raw['key']] = val
        return ret

    def search(self, text):
        if not text:
            return None
        ret = self._search_issues(f'PROJECT = {self.project_name} AND STATUS != {self._closed_status} AND (text ~ "{text}")')
        return self._simplify_issue_list(ret)

    def list(self, status=None, userid=None):
        if userid == 'me':
            userid = self.user['name']
        issues = self.index_issues(status)
        return self._simplify_issue_list(issues, userid)

    def issue(self, issue_alias, verbose=False):
        if isinstance(issue_alias, Issue):
            return issue_alias
        issue_aliases = [issue_alias]
        if issue_alias.upper() != issue_alias:
            issue_aliases.append(issue_alias.upper())
        if '-' not in issue_alias:
            issue_aliases.append(self.project_name.upper() + f'-{issue_alias}')
        for alias in issue_aliases:
            if alias in self._config['issue_map']:
                return self._config['issue_map'][alias]
            try:
                issue = self.jira.issue(alias)
                if not issue:
                    continue
                self._index_issue(issue)
                return issue
            except JIRAError:
                pass
        return None

    def search_issues(self, text):
        if not text:
            return None
        ret = self._search_issues(text)
        return self._simplify_issue_list(ret)

    def transitions(self, issue):
        if isinstance(issue, str):
            issue = self.issue(issue)
        # {'state': 'id', 'state2': 'id2' }
        possible = {}
        url = os.path.join(issue.raw['self'], 'transitions')
        transitions = json_loads(self.jira._session.get(url))
        for transition in transitions['transitions']:
            possible[transition['to']['id']] = {'id': transition['id'], 'name': transition['to']['name']}
        if not possible:
            return None
        return possible

    def _find_transition(self, issue, status):
        transitions = self.transitions(issue)
        for state_id in transitions:
            if transitions[state_id]['name'] == status or nym(transitions[state_id]['name']) == status or str(state_id) == str(status):
                return transitions[state_id]['id']
        return None

    def move(self, issue_aliases, status):
        if not isinstance(issue_aliases, list):
            issue_aliases = [issue_aliases]

        fails = []
        moves = []
        issues = []
        for idx in issue_aliases:
            issue = self.issue(idx)
            if not issue:
                fails.append(idx)
                continue
            if idx in moves:
                continue
            # Don't double-move (if someone specified the same item twice)
            moves.append(idx)
            issues.append(issue)

        # Jira doesn't have a status you can update; you have to retrieve possible
        # transitions and satisfy those requirements. Each issue has its own transition map
        # according to the issue type.
        # Future improvements:
        # * cache transitions (one set per issue type)
        # * list
        if fails:
            raise ValueError('No such issue(s): ' + str(fails))
        for issue in issues:
            transition = self._find_transition(issue, status)
            if not transition:
                continue

            # POST /rest/api/2/issue/{issueIdOrKey}/transitions
            url = os.path.join(issue.raw['self'], 'transitions')
            self.jira._session.post(url, data={'transition': {'id': transition}})
        return moves

    def link_types(self):
        return self.jira.issue_link_types()

    def link(self, left_alias, right_alias, link_text):
        left = self.issue(left_alias)
        right = self.issue(right_alias)
        return self.jira.create_issue_link(link_text, left.raw['key'], right.raw['key'])

    def remote_links(self, issue_alias):
        issue = self.issue(issue_alias)
        links = self.jira.remote_links(issue.raw['id'])
        return links

    def unlink(self, left_alias, right_alias):
        left = self.issue(left_alias)
        right = self.issue(right_alias)

        if not right:
            extlink = self.jira.remote_link(left.raw['key'], str(right_alias))
            self.jira._session.delete(extlink.raw['self'])
            return 1

        info = left.raw['fields']

        if 'issuelinks' not in info or not info['issuelinks']:
            return 0

        right_name = right.raw['key']
        count = 0
        for link in info['issuelinks']:
            link_id = None
            if 'inwardIssue' in link and link['inwardIssue']['key'] == right_name:
                link_id = link['id']
            if 'outwardIssue' in link and link['outwardIssue']['key'] == right_name:
                link_id = link['id']
            if link_id:
                count = count + 1
                self.jira.delete_issue_link(link_id)
        return count

    def states(self):
        return copy.copy(self._config['states'])

    def create(self, **args):
        # Structures for certain things need to be adjusted, because JIRA.
        # parent key is special because we do our own shortcuts.  Overwrite
        # project if we're creating a subtask
        if 'parent' in args and isinstance(args['parent'], str):
            parent_issue = self.issue(args['parent'])
            parent_key = parent_issue.raw['key']
            project = parent_issue.raw['fields']['project']['key']
            args['parent'] = {'key': parent_key}
            args['project'] = project

        # Transmogrify other fields
        new_args = transmogrify_input(**args)

        ret = self.jira.create_issue(**new_args)
        self._index_issue(ret)
        return ret

    def new(self, name, description=None, issue_type=None, parent=None):
        if parent:
            if issue_type != 'Sub-task':
                raise ValueError('Specifying a parent only valid for Sub-task type')

        issuetypes = self.issue_types
        resolved_issue_type = None
        if issue_type is not None:
            for itype in issuetypes:
                if itype.name.upper() == issue_type.upper():
                    resolved_issue_type = itype.name
                    break
            if not resolved_issue_type:
                raise ValueError(f'No such issue type: {issue_type}')
        else:
            resolved_issue_type = issuetypes[0].name

        args = {}
        args['project'] = self.project_name
        args['summary'] = name
        args['issuetype'] = resolved_issue_type
        if parent is not None:
            args['parent'] = parent
        if description:
            args['description'] = description

        return self.create(**args)

    def subtask(self, parent, name, description=None):
        return self.new(name, description, 'Sub-task', parent)

    @property
    def issue_types(self):
        if not self._issue_types:
            self._issue_types = self._project.issueTypes
        return self._issue_types

    # Returns a dict that JIRA should just give us.
    def issue_metadata(self, issue_type_or_id):
        itype = None
        for issuetype in self.issue_types:
            if issuetype.id == issue_type_or_id or nym(issuetype.name) == nym(issue_type_or_id):
                itype = issuetype
        if not itype:
            return None

        issue_type_id = itype.id
        fields = []
        start = 0
        chunk_len = 50
        while True:
            data = {'startAt': start, 'maxResults': chunk_len}
            new_fields = self.jira._get_json(f'issue/createmeta/{self.project_name}/issuetypes/{issue_type_id}', params=data)
            fields.extend(new_fields['values'])
            if new_fields['isLast']:
                break
            start = start + chunk_len

        field_dict = {val['fieldId']: val for val in fields}
        metadata = {'self': itype.self, 'name': itype.name, 'id': itype.id, 'description': itype.description, 'subtask': itype.subtask, 'iconUrl': itype.iconUrl, 'fields': field_dict}
        return metadata

    def get_comment(self, issue_alias, comment_id):
        issue = self.issue(issue_alias)
        return self.jira.comment(issue.raw['key'], comment_id)

    def comment(self, issue_alias, text):
        issue = self.issue(issue_alias)
        if not issue:
            return None
        # Use simple comment mode to add a comment
        url = os.path.join(issue.raw['self'], 'comment')
        return self.jira._session.post(url, data={'body': text})

    def close(self, issues):
        return self.move(issues, 'Closed')

    def config(self):
        return copy.copy(self._config)

    def get_user_data(self, key):
        if key in ('states', 'issue_map', 'issue_rev_map'):
            return KeyError('Reserved configuration keyword: ' + key)
        if key in self._config:
            return copy.copy(self._config[key])
        return None

    def set_user_data(self, key, userdata):
        if key in ('states', 'issue_map', 'issue_rev_map'):
            return KeyError('Reserved configuration keyword: ' + key)
        self._config[key] = copy.copy(userdata)
