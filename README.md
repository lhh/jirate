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
Configuration is a JSON document stored as `~/.jirate.json` - an example can be found in the `contrib/jirate.json` file in this repository.
### JIRA configuration fields
- `url` (Required) - URL to your JIRA instance
- `token` (Required) - A valid personal access token for your account
- `default_project` (Required) - Default project to use when interacting with JIRA
- `here_there_be_dragons` (Optional) - Set to `true` if you intend to use custom code to render JIRA custom field data
- `default_fields` (Optional) - When displaying lists of issues, display these fields (and optional field widths) by default
- `searches` (Optional) - List of JQL searches and their names.  The special search named `default` is applied when one runs `jirate search`.
- `custom_fields` (Optional) - Raw (or cooked, if you prefer) field definitions following the same conventions as the jira `/field` data.
- `proxies` (Optional) - HTTP and/or HTTPS proxies to use

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

## Templates
- Generate a template from an existing issue:
  - `jirate generate-template MYISSUE-123 > my-template.yaml`
- File a new issue from a template:
  - `jirate template my-template.yaml`

## Inter-issue links and external links
- Create a link between two issues:
  - `jirate link PROJ-123 depends on PROJTWO-111`
- Clear all links between two issues:
  - `jirate unlink PROJ-123 PROJTWO-111`
- Attach external link to an issue:
  - `jirate attach PROJ-123 http://www.github.com Github Home`

# Advanced
## API hackery
- Call an API
  - `jirate call-api /field`
