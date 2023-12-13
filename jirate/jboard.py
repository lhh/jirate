#!/usr/bin/python3

import copy
import os
import types

from toolchest.strutil import list_or_splitstr

from jira import JIRA, JIRAError
from jira.utils import json_loads
from jira.resources import Issue

from jirate.decor import nym
from jirate.jira_input import transmogrify_input


def _resolve_field(obj, field_name):
    return obj._jirate._field(obj, field_name)


def _resolve_field_setup(jirate_obj, issue_obj):
    # Do NOT trample future python JIRA objects' field function.
    if hasattr(issue_obj, 'field'):
        raise Exception('API BREAK: \'field\' is now part of jira.resources.Issue. Please file a bug!')
    issue_obj._jirate = jirate_obj
    issue_obj.field = types.MethodType(_resolve_field, issue_obj)


class Jirate(object):
    """High-level wrapper for python-jira"""
    def __init__(self, jira):
        self.jira = jira
        self._user = None
        self._field_map = None

    @property
    def user(self):
        """This is the connected user (lazy-loaded)"""
        if self._user is None:
            # Get current user info and record it
            # This doesn't use self.jira.session().raw since this
            # doesn't have all the information available.
            self._user = self.jira.myself()
        return self._user

    def attach(self, issue_alias, url, description):
        """Attach an external URL to an issue

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key
          url: URL to attach (string)
          description: Description of link (string)
        """
        item = {'url': url, 'title': description}
        issue = self.issue(issue_alias)
        return self.jira.add_simple_link(issue, item)

    def search_users(self, username):
        """Wrapper for searching JIRA's user database

        Parameters:
          username: Partial username or email (string)

        Returns:
          list of jira.resources.User
        """
        # Search userlist for a username.  This is provided like this
        # so we can expand functionality later. Max is 50 by default;
        # we'll start with that
        users = self.jira.search_users(username)
        return users

    def field_map(self, name):
        if self._field_map is None:
            self._field_map = {}
            fields = self.jira.fields()
            for field in fields:
                self._field_map[field['name']] = field['id']
                alias = nym(field['name'])
                # if they're the same, don't store
                if alias == field['name']:
                    continue
                # append underscores for collisions
                # XXX hopefully this is extremely rare
                while alias in self._field_map:
                    alias = alias + '_'
                self._field_map[alias] = field['id']
        if name in self._field_map:
            return self._field_map[name]
        return name

    def search_issues(self, search_query):
        """Run a JQL search and assemble the results into one list

        Parameters:
          search_query: JQL query line (string)

        Returns:
          list of jira.resources.Issue
        """
        index = 0
        chunk_len = 50      # So we can detect end
        ret = []
        while True:
            issues = self.jira.search_issues(search_query, startAt=index, maxResults=chunk_len)
            if not len(issues):
                break
            ret.extend(issues)
            index = index + len(issues)
            if len(issues) < chunk_len:
                break
        for issue in ret:
            _resolve_field_setup(self, issue)
        return ret

    def _field(self, issue, field_name):
        """Reconcile a field in an issue with custom field defs
        on the jira server. Does not retrieve the issue from the
        JIRA server.

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key
          field_name: human readable field name

        Returns:
          field value, or none if not found

        Raises:
          AttributeError if the field does not exist.
        """
        # Don't return customfield if there's a direct match
        # obvious match
        if field_name in issue.raw['fields']:
            return issue.raw['fields'][field_name]
        fname = self.field_map(field_name)
        if fname in issue.raw['fields']:
            return issue.raw['fields'][fname]
        raise AttributeError(str(issue) + f' has no field like {field_name}')

    def field(self, issue_alias, field_name):
        """Reconcile a field in an issue with custom field defs
        on the jira server. Retrieves the issue from the server if
        needed.

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key
          field_name: human readable field name

        Returns:
          field value, or none if not found

        Raises:
          AttributeError if the field does not exist.
        """
        issue = self.issue(issue_alias)
        return self._field(issue, field_name)

    def fields(self, issue_alias):
        """Determine the fields available for an issue

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key

        Returns:
          dict of fields
        """
        issue = self.issue(issue_alias)
        # XXX HERE THERE BE DRAGONS
        # NOT IMPLEMENTED UPSTREAM
        url = os.path.join(issue.raw['self'], 'editmeta')
        field_blob = json_loads(self.jira._session.get(url))
        return field_blob['fields']

    def get_user(self, username):
        """Determine JIRA's normalized username for someone

        Parameters:
          username: email, display name or username

        Returns:
          username (string)
        """
        if '@' not in username:
            return username

        users = self.jira.search_users(username)
        if len(users) > 1:
            raise ValueError(f'Multiple matching users for \'{username}\'')
        elif not users:
            raise ValueError(f'No matching users for \'{username}\'')

        return users[0].name

    def api_call(self, uri):
        url = self.jira._get_url(uri)
        return json_loads(self.jira._session.get(url))

    def assign(self, issue_aliases, users=None):
        """Assign a set of issues to a user

        NOTE: Originally, the additional users were going to be set as
        watchers, which is another API call. We did this with Trello.
        Do we want to do that for JIRA, or should we have separate
        watch/unwatch?

        Parameters:
          issue_aliases: list of issue keys or IDs (list of strings)
          users: list of users (list of strings)

        Returns:
          list of issues successfully assigned to the user(s)
        """
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

    def get_comment(self, issue_alias, comment_id):
        """Retrieve raw comment for an issue

        Parameters:
          issue_alias: issue key or ID (string)
          comment_id: ID of comment to retrieve

        Returns:
          jira.resources.Comment
        """
        issue = self.issue(issue_alias)
        return self.jira.comment(issue.raw['key'], comment_id)

    def comment(self, issue_alias, text, visibility=None):
        """Attach a new comment to an issue

        Parameters:
          issue_alias: issue key or ID (string)
          text: Text to attach as comment

        Returns:
          requests.Response
        """
        issue = self.issue(issue_alias)
        if not issue:
            return None
        # Use simple comment mode to add a comment
        comment_data = {'body': text}
        if visibility:
            if isinstance(visibility, str):
                comment_data['visibility'] = {}
                comment_data['visibility']['type'] = 'group'
                comment_data['visibility']['value'] = visibility
            elif isinstance(visibility, dict):
                comment_data['visibility'] = visibility

        url = os.path.join(issue.raw['self'], 'comment')
        return self.jira._session.post(url, data=comment_data)

    def close(self, issues):
        """Close an issue

        XXX this might not be a usable API and/or may be a higher
        level transition than we want. Note that 'Closed' may also
        not be correct for a given project, since all transitions
        are per-project. We could do something intelligent with
        move, or delete this API altogether.

        Parameters:
          issues: list of issue keys or IDs (list of string)

        Returns:
          requests.Response
        """
        return self.move(issues, 'Closed')

    def create(self, **args):
        """Create a new issue using key/value pairs

        Parameters:
          **args: Dictionary of key/value pairs (dict)

        Returns:
          jira.resources.Issue
        """
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
        return ret

    def update_issue(self, issue_alias, **kwargs):
        """Update an issue using key/value pairs

        Parameters:
          **args: Dictionary of key/value pairs (dict)

        Returns:
          jira.resources.Issue (?)
        """
        issue = self.issue(issue_alias)
        if issue:
            return issue.update(**kwargs)

    def issue(self, issue_alias, verbose=False):
        """Retrieve an issue from JIRA

        XXX Cleanup vs. JiraProject

        Parameters:
          issue_alias: key or issue ID (string)

        Returns:
          jira.resources.Issue
        """
        if isinstance(issue_alias, Issue):
            return issue_alias
        issue_aliases = [issue_alias]
        if isinstance(issue_alias, int):
            issue_alias = str(issue_alias)
        if issue_alias.upper() != issue_alias:
            issue_aliases.append(issue_alias.upper())
        for alias in issue_aliases:
            try:
                issue = self.jira.issue(alias)
                if not issue:
                    continue
                _resolve_field_setup(self, issue)
                return issue
            except JIRAError:
                pass
        return None

    def issues(self, issue_list, verbose=False):
        """Retrieve one or more issues from JIRA

        Parameters:
          issue_list: string of keys or list of keys (strings)

        Returns:
          list of jira.resources.Issue or None
        """
        if isinstance(issue_list, Issue):
            return issue_list
        issues = list_or_splitstr(issue_list)

        ret = []
        for issue in issues:
            ret.append(self.issue(issue, verbose))
        if ret:
            return ret
        return None

    def transitions(self, issue):
        """Retrieve possible next-state transitions for an issue

        Parameters:
          issue_alias: key or issue ID (string)

        Returns:
          dict - {'state': 'id', 'state2': 'id2'}
        """
        if isinstance(issue, str):
            issue = self.issue(issue)
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
        """Execute a transition to move a set of issues to the desired status

        Jira doesn't have a status you can update; you have to retrieve possible
        transitions and satisfy those requirements. Each issue has its own transition map
        according to the issue type within a given project

        Parameters:
          issue_aliases: list keys or issue IDs (list of string)
          status: Desired status

        Returns:
          list of successfully moved issues (list of string)
        """
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
        """Wrapper for jira.issue_link_types()"""
        return self.jira.issue_link_types()

    def link(self, left_alias, right_alias, link_text):
        """Link two isues together using the noted link type

        Parameters:
          left_alias: left key or issue IDs (string)
          right_alias: right key or issue IDs (string)
          link_text: Desired link type

        Returns:
          ???
        """
        left = self.issue(left_alias)
        right = self.issue(right_alias)
        return self.jira.create_issue_link(link_text, left.raw['key'], right.raw['key'])

    def remote_links(self, issue_alias):
        """Obtain all remote links (URLs) attached to an issue

        Parameters:
          issue_alias: key or issue IDs (string)

        Returns:
          list of jira.resources.RemoteLink
        """
        issue = self.issue(issue_alias)
        links = self.jira.remote_links(issue.raw['id'])
        return links

    def unlink(self, left_alias, right_alias):
        """Break all links between to issues

        Parameters:
          left_alias: left key or issue IDs (string)
          right_alias: right key or issue IDs (string)

        Returns:
          count of links removed
        """
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


class JiraProject(Jirate):
    def __init__(self, jira, project, closed_status=None, readonly=False, allow_code=False, simplify=False):
        self.jira = jira
        self._ro = readonly
        self._config = None
        self._closed_status = closed_status
        self._project = self.jira.project(project)
        self._user = None
        self._issue_types = None
        self._simple = simplify
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

    def unlabel_issue(self, issue_alias, label_name):
        return False

    def status_to_id(self, status):
        status = nym(status)

        if status not in self._config['states']:
            raise KeyError('No such list: ' + status)
        if status in self._config['states']:
            return self._config['states'][status]['id']
        return status  # must be the ID

    def search_issues(self, text):
        # Override so we can index our return values
        if not text:
            return None
        ret = super().search_issues(text)
        self._index_issues(ret)
        return ret

    def _index_issue(self, issue):
        if issue.raw['key'] not in self._config['issue_map']:
            self._config['issue_map'][issue.raw['key']] = issue

    def _index_issues(self, issues):
        if 'issue_map' not in self._config:
            self._config['issue_map'] = {}

        for issue in issues:
            self._index_issue(issue)

    def index_issues(self, status=None):
        if status:
            status_id = self.status_to_id(status)
            open_issues = super().search_issues(f'PROJECT = {self.project_name} AND STATUS = {status_id}')
        else:
            open_issues = super().search_issues(f'PROJECT = {self.project_name} AND STATUS != {self._closed_status}')
        self._index_issues(open_issues)
        return open_issues

    def search(self, text):
        if not text:
            return None
        return self.search_issues(f'PROJECT = {self.project_name} AND STATUS != {self._closed_status} AND (text ~ "{text}")')

    def list(self, status=None, userid=None):
        if userid == 'me':
            userid = self.user['name']
        return self.index_issues(status)

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

    def states(self):
        return copy.copy(self._config['states'])

    def new(self, name, description=None, issue_type=None, parent=None):
        # Simple New creation requires understanding what the issuetypes are,
        # which vary on a per-project basis.  This is why "create" is separate
        # (and lower-level)
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

    def create(self, **args):
        # override so we can index our value
        ret = super().create(**args)
        self._index_issue(ret)
        return ret

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
            new_fields = self.jira.createmeta_fieldtypes(self.project_name, issue_type_id, params=data)
            fields.extend(new_fields['values'])
            if new_fields['isLast']:
                break
            start = start + chunk_len

        field_dict = {val['fieldId']: val for val in fields}
        metadata = {'self': itype.self, 'name': itype.name, 'id': itype.id, 'description': itype.description, 'subtask': itype.subtask, 'iconUrl': itype.iconUrl, 'fields': field_dict}
        return metadata

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


def get_jira(jconfig):
    """Wrapper to create a python-jira connection

    Parameters:
      jconfig: dict of 3 keys: url, token, proxies (optional)

    Returns:
      jira.JIRA
    """
    if 'url' not in jconfig:
        print('No JIRA URL specified')
        return None
    if 'token' not in jconfig:
        print('No JIRA token specified')
        return None
    if 'proxies' not in jconfig:
        jconfig['proxies'] = {"http": "", "https": ""}

    return JIRA(jconfig['url'], token_auth=jconfig['token'], proxies=jconfig['proxies'])
