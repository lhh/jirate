# jirate
High-level CLI for Trello and JIRA

# Installation
`pip install -r requirements.txt`
`pip install .`

# Notes - Jira
- You must configure your default project, token, and URL by creating ~/.jirate.json
- Whenever operating on your default project, you do not need to include it in operations. In the below examples, if your default project was `MYISSUE`, you could omit it when calling operations on `MYISSUE-123` and simply provide `123`
- Project keys are case insensitive from the CLI; they are automatically translated to upper-case.

# Examples - Jira
- cat (print) a task:
  - `jirate cat MYISSUE-123`
  - `jirate cat -v MYISSUE-123`
  - `jirate -p myissue cat 123`
- View an issue in your browser (xdg-open):
  - `jirate view MYISSUE-123`
  - `jirate -p myissue view 123`
- Create new Task. This spawns an editor. First line is your summary, the third lines and subsequent become the description:
  - `jirate new`
- Create new specified issue type with a summary:
  - `jirate new -t Bug This is my Bug Summary`
  - `jirate new -t Bug "This is my Bug Summary"`
  - `jirate -p myissue new -t Task "This is my Task Summary"`
- Print out the fields and allowed values (if applicable) to be used when creating a new Epic:
  - `jirate create -t epic`
- Create an issue (advanced) with custom fields:
  - `jirate create -t Story story_points 3 summary "This is my summary" description "This is my description" assignee my-user-id`
- Move several issues to closed and set resolution to "Won't Do":
  - `jirate mv -r "won't do" MYISSUE-123 OTHERPROJECT-234 closed`
  - `jirate close -r "won't do" MYISSUE-123 OTHERPROJECT-234`
- List issues assigned to you in your default project:
  - `jirate ls`
- Search for all unresolved issues assigned to you:
  - `jirate search`
- Search for all issues assigned to you and display the a table with key (always displayed on left), status, priority, and summary (with width limited to 20 characters):
  - `jirate search --fields status,priority,summary:20`
- Execute a raw search and display just the priority:
  - `jirate search -r "field1 is not EMPTY" --fields priority`
- List the fields for an issue and display any values which are allowed:
  - `jirate fields MYISSUE-123`
- Add (or remove) several Jira usernames to (or from) the Contributors field:
  - `jirate field MYISSUE-123 add|remove contributors user1,user2`
- Comment on an issue (spawns editor):
  - `jirate comment MYISSUE-123`
- Edit a comment on an issue (see cat):
  - `jirate comment MYISSUE-123 -e 12345667`
- List components:
  - `jirate components`
  - `jirate components -q`
  - `jirate -p OTHERPROJECT components`
- Search component names and descriptions for a regex:
  - `jirate components -s kernel`
