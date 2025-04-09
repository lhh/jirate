# jirate
High-level CLI for JIRA and Trello

# Installation
- From source:
  - `pip install -r requirements.txt`
  - `pip install .`
- From PyPi:
  - `pip install jirate`
- In a locally-built container:
  - `make`
  - `./jirate-c [args]`

# Notes
## Configuration
Configuration is one of:
- a JSON document stored as `~/.jirate.json` - an example can be found in the `contrib/jirate.json` file in this repository.
- a YAML document stored as `~/.jirate.yaml` - an example can be found in the `contrib/jirate.yaml` file in this repository.
### JIRA configuration fields
- `url` (Required) - URL to your JIRA instance
- `token` (Required) - A valid personal access token for your account
- `default_project` (Required) - Default project to use when interacting with JIRA
- `eausm` (Optional) - Set to `false` to disable EZ Agile Planning voting
- `here_there_be_dragons` (Optional) - Set to `true` if you intend to use custom code to render JIRA custom field data
- `default_fields` (Optional) - When displaying lists of issues (e.g. `list`, `search`, `cat` for more than one issue), display these fields (and optional field widths) by default.  Key is always the left-most field, and is always included.
- `issue_fields` (Optional) - When displaying issues (or a list) using `cat`, display only these fields by default.  Key is always the left-most field, and is always included.  Summary is not automatically included.  Note: The order of field specification precedence when using `cat` to determine field list is: command line, `issue_fields`, `default_fields`.
- `no_format` (Optional) - Set to `true` if you would prefer Jirate not attempt to render JIRA comments and descriptions as markdown (JIRA text isn't markdown, so the markdown processor often gets this wrong)
- `searches` (Optional) - List of JQL searches and their names.  The special search named `default` is applied when one runs `jirate search`.
- `custom_reorder` (Optional) - Defaults to true. If set to false, custom field definitions will not reorder base JIRA fields when listing issues.
- `custom_fields` (Optional) - One of:
  - Custom field rendering definitions in the format of the jira `/field` data with some additional fields (see below)
  - A filename pointing to custom field definitions, or
- `proxies` (Optional) - HTTP and/or HTTPS proxies to use
- `cache_expire` (Optional) - Number of seconds to cache certain JIRA configuration data locally (default: `300`; `0` means no expiration)
- `cache_file` (Optional) - Where to store cached JIRA configuration data (default: `~/.jirate.cache`)
- `fancy_output` (Optional) - If set to true, render some things as links and enable per-line visual separation for tables
- `color_shift` (Optional) - Tune color separation when using `fancy_output`. (0..128; default=16)

### JIRA Custom field display configuration
Each field in `custom_fields` is a dictionary. Jirate only cares about a few fields when defining custom rendering; most fields it automatically discerns by asking the server for the `/field` data:
- `id` (Required) - the JIRA custom field name (`customfield_xxxxx`).
- `name` (Required) - Generally this should come from your JIRA instance, but you can rename it to whatever you like if you want.
- `display` (Optional) - false (to not display this field) or one of several built in renderers:`string, any, number, value, name, version, user, value_list, email_list, name_list, date, datetime`
- `disabled` (Optional) - If set to `true`, do not allow rendering of this field, even if requested
- `verbose` (Optional) - If set to `true`, only display this field when someone requests verbose output or requests this field explicitly
- `code` (Optional) - when `here_there_be_dragons` is set to true, insert a snippet of Python code to render your data.  The field is passed to your one-line of code as `field`; all fields in the issue are passed in as `fields`.  You'll need to know the custom field ID of any field you are trying to reference.
  - `code` can also be something like: `#~/filename.py:function_name`. If defined in this way, `~/filename.py` should contain `def function_name(field, fields)` in it. `field` is the raw value of the current field being processed, and `fields` is the JSON data for all fields in the issue.

## Operation
- Trello support is somewhat unmaintained as the maintainers do not have access to a commercial Trello instance any longer. Taking patches.
- Whenever operating on your default project, you do not need to include it in operations. In the below examples, if your default project was `MYISSUE`, you could omit it when calling operations on `MYISSUE-123` and simply provide `123`
- Project keys are case insensitive from the CLI; they are automatically translated to upper-case.

# Examples
## Displaying individual issues
- cat (print) a task:
  - `jirate cat MYISSUE-123`
  - `jirate cat -v MYISSUE-123`
  - `jirate -p myissue cat 123`
- View an issue in your browser (xdg-open):
  - `jirate view MYISSUE-123`
  - `jirate -p myissue view 123`
  - `jirate view 123`

## Creating issues
- Listing issue types available
  - `jirate lt`
  - `jirate -p MYPROJECT lt`
- Listing issue fields, whether they are required, and, if applicable, allowed values for a specific issue type
  - `jirate create -t Bug`
  - `jriate -p MYPROJECT create -t Epic`

### Simple: Using the 'new' and 'subtask' commands
- Create new Task. This spawns an editor. First line is your summary, the third lines and subsequent become the description (think: git commit message):
  - `jirate new`
- Create a subtask for an issue (spawns editor):
  - `jirate subtask MYISSUE-123`
- Create new specified issue type with a summary (but no description):
  - `jirate new -t Bug This is my Bug Summary`
  - `jirate new -t Bug "This is my Bug Summary"`
  - `jirate -p myissue new -t Task "This is my Task Summary"`

### Flexible: Using the 'create' command
- Creating an issue with custom fields:
  - `jirate create -t Story story_points 3 summary "This is my summary" description "This is my description" assignee my-user-id`

## Listing issues
- List open issues in the default project assigned to you
  - `jirate ls`
- List open, unassigned issues in the default project assigned to you
  - `jirate ls -U`
- List open issues assigned to `other-user` in the default project:
  - `jirate ls -u other-user`

## Searching issues
- Search for all unresolved issues assigned to you (unless you overrode the search named `default` in your configuration file):
  - `jirate search`
- Execute the search named `foo` defined in your `searches` list in `~/.jirate.json`:
  - `jirate search -n foo`
- Search for all issues assigned to you and display the a table with key (always displayed on left), status, priority, and summary (with width limited to 20 characters):
  - `jirate search --fields status,priority,summary:20`
- Execute a raw search and display just the key and priority:
  - `jirate search -r "field1 is not EMPTY" --fields priority`

## Updating issues
- Assign an issue
  - `jirate assign MYISSUE-123 me` - assign to yourself
  - `jirate assign MYISSUE-123 other-user` - assign to `other-user`
- Unassign an issue
  - `jirate unassign MYISSUE-123`
- Editing the summary or description of an issue (spawns editor):
  - `jirate edit MYISSUE-123`
- Comment on an issue (spawns editor):
  - `jirate comment MYISSUE-123`
- Edit a comment on an issue (see cat):
  - `jirate comment 123 -e 12345667`
- Make that comment private to the Employee group (case/space sensitive; quote if needed):
  - `jirate comment 123 -e 12345667 -g Employee`
- Make that comment public:
  - `jirate comment 123 -e 12345667 -g all`
- Move several issues to closed and set resolution to "Won't Do":
  - `jirate mv -r "won't do" MYISSUE-123 OTHERPROJECT-234 closed`
  - `jirate close -r "won't do" MYISSUE-123 OTHERPROJECT-234`
- Move several issues to `In Progress` and assign them to yourself:
  - `jirate mv -m ISSUE-1 ISSUE-2 ISSUE-3 in_progress`
- Move several issues to `In Progress` and assign them to `other-user`:
  - `jirate mv -u other-user ISSUE-1 ISSUE-2 ISSUE-3 in_progress`
- List issues assigned to you in your default project:
  - `jirate ls`
- List the fields for an issue and display any values which are allowed to be updated (and, if applicable, allowed values):
  - `jirate fields MYISSUE-123`
- Updating the value of most fields (note: does not support the Any type schema):
  - `jirate field 123 set severity critical`
  - `jirate field 123 set customfield_123455934 critical`
  - `jirate field 123 set priority minor`
- Setting a list field to a set of values:
  - `jirate field 123 set contributors user1,user2,user3`
- Add (or remove) several Jira usernames to (or from) the Contributors field:
  - `jirate field MYISSUE-123 add|remove contributors user1,user2`

## Components
- List components:
  - `jirate components`
  - `jirate components -q`
  - `jirate -p OTHERPROJECT components`
- Search component names and descriptions for a regex:
  - `jirate components -s kernel`

## Inter-issue links and external links
- Create a link between two issues:
  - `jirate link PROJ-123 depends on PROJTWO-111`
- Clear all links between two issues:
  - `jirate unlink PROJ-123 PROJTWO-111`
- Attach external link to an issue:
  - `jirate attach PROJ-123 http://www.github.com Github Home`

# Advanced
## CSV output
Jirate can output individual issues in CSV format, which is a bit easier to parse than JSON or text data.
- `jirate -f csv [cat|search|sprint|components]`
## Templates
Jirate has powerful templating - templates are a combination of Jinja2 and YAML.  Note that typical syntax differs from Jinja2 since double-braces are used by Jira, we use `{@` and `@}` instead.
- Generate a template from an existing issue:
  - `jirate generate-template MYISSUE-123 > my-template.yaml`
- File a new issue from a template:
  - `jirate template my-template.yaml version 1.2`
### Template fields
Because Jirate resolves field IDs to human-readable values, it's possible to use the human-readable field names in your templates. There are some strange exceptions, but most custom fields are supported as long as your project's creation metadata supports the field.
### Template variables
There are two typical methods of setting default values.
- `{% set var=var or "1.0 %}`
- `{@var|default('1.0')@}`

Jirate ignores variables in templates which start with underscores. This allows you to use Jinja2 code to slice up existing variables or to create derived variable values from user input. The first usage of a variable in a template - even in a YAML comment - is what tells Jirate to require the variable from the user. Here's an example of creating a `_version_next` by slicing up the `version` value given to us by a user:

```
# {@version@} - version to stand up
{% set _version_info = version.split('.') %}
{% set _ = _version_info.append(((_version_info.pop()|int) + 1)|string) %}
{% set _version_next = _version_info|join('.') %}`
```

Now `{@_version_next@}` can be used within fields inside your template.
### Applying templates after issue creation
This is useful for when a user needs to create a set of known tasks, but does not have the full context for what is entailed yet. They might generate stub 30 issues, then generate a template from the first one and apply it to the other 29.
- `jirate template --apply MYISSUE-123 mytemplate.yaml version 1.0`


## API hackery
- Call an API
  - `jirate call-api /field`
