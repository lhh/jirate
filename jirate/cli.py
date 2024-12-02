#!/usr/bin/python3

import os
import re
import sys
# import yaml

import editor

from trollo import TrelloApi

from jirate.args import ComplicatedArgs
from jirate.board import TrollyBoard
from jirate.decor import color_string, hbar_under, pretty_date, md_print
from jirate.config import get_config


def extract_bugzillas(card):
    ret = re.findall(r'://bugzilla\.redhat\.com/([0-9]+)', card['desc'])
    ret = list(set(ret) | set(re.findall(
                              r'://bugzilla\.redhat\.com/show_bug\.cgi\?id=([0-9]+)',
                              card['desc'])))
    return [int(r) for r in ret]


def bugzilla_refs(trello_list):
    ret = []
    for p in trello_list:
        ret = list(set(ret) | set(extract_bugzillas(p)))
    return ret


def trello_init(config):
    if config is not None:
        try:
            TRELLO_KEY = config['trello']['key']
            TRELLO_TOKEN = config['trello']['token']
        except IndexError:
            print('Please set your Trello key and token in your configuration file')
            exit(1)
    else:
        try:
            TRELLO_KEY = os.environ['TRELLO_KEY']
            TRELLO_TOKEN = os.environ['TRELLO_TOKEN']
        except KeyError:
            print('Please set your TRELLO_KEY and TRELLO_TOKEN variables or place them your config file')
            exit(1)

    if TRELLO_KEY is None:
        print("Please specify key in ~/.???")
        print("Visit this URL to obtain it:")
        print("  https://trello.com/app-key")
        exit(1)

    trello = TrelloApi(TRELLO_KEY)
    if not TRELLO_TOKEN:
        print("Visit this URL to get your token:")
        print('   https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=shale&key=' + TRELLO_KEY)
        exit(1)

    #
    # Wow very simple
    #
    trello.set_token(TRELLO_TOKEN)

    return trello


def move(args):
    if len(args.src) == 1:
        try:
            args.board.rename(args.src[0], args.target)
            return (0, True)
        except KeyError:
            pass

    if args.board.move(args.src, args.target):
        print('Moved', args.src, 'to', args.target)
        return (0, False)
    return (1, False)


def close_cards_in_lists(args):
    for archive_list in args.target:
        list_id = args.board.list_to_id(archive_list)
        args.board.trello.lists.archive_all_cards(list_id)
    return (0, False)


def close_cards(args):
    ret = 0
    if args.list:
        return close_cards_in_lists(args)
    for card in args.target:
        if not args.board.close(card):
            ret = 1
    return (ret, False)


def reopen_card(args):
    ret = 0
    for card in args.card:
        if not args.board.reopen(card):
            ret = 1
    return (ret, False)


def print_cards_simple(cards, args=None):
    lists = {}
    for card in cards:
        clist = cards[card]['list']
        if args and args.list and clist not in args.list:
            continue
        if clist not in lists:
            lists[clist] = []
        lists[clist].append(card)

    for key in lists:
        print(key)
        for card in lists[key]:
            print('  ', card, end=' ')
            if args and args.labels:
                print_labels(cards[card], prefix='')
            print(cards[card]['name'])


def search_cards(args):
    ret = args.board.search(' '.join(args.text))
    if not ret:
        return (127, False)
    print_cards_simple(ret)
    return (0, False)


def list_cards(args):
    # check for verbose
    if args.mine:
        userid = 'me'
    else:
        userid = None

    cards = args.board.list(userid=userid)
    print_cards_simple(cards, args)
    return (0, True)


def list_lists(args):
    default = args.board.default_list()
    lists = args.board.lists()
    for lname in lists:
        if lists[lname]['id'] == default:
            print(' •', lname, lists[lname]['name'])
        else:
            print('  ', lname, lists[lname]['name'])
    return (0, False)


def set_default(args):
    default = args.board.default_list()
    new_default = args.board.default_list(args.list)
    return (0, (default != new_default))


def split_card_text(text):
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


def new_card(args):
    desc = None
    if args.text:
        name = ' '.join(args.text)
    else:
        text = editor()
        name, desc = split_card_text(text)
        if name is None:
            print('Canceled')
            return (1, False)

    card = args.board.new(name, desc)
    print(card['idShort'], card['name'])
    return (0, True)


def comment(args):
    card_id = int(args.card)
    if args.text:
        text = ' '.join(args.text)
    else:
        text = editor()

    if not len(text):
        print('Canceled')
        return (0, False)

    args.board.comment(card_id, text)
    return (0, False)


def refresh(args):
    args.board.refresh()
    args.board.index_cards()
    return (0, True)


def action_null(action, arg=None):
    pass


def action_comment(action, verbose):
    data = action['data']
    if verbose:
        print(pretty_date(action['date']), '• Comment by', action['memberCreator']['username'], 'ID', action['id'])
    else:
        print(pretty_date(action['date']), '• Comment by', action['memberCreator']['username'])
    md_print(data['text'])


def display_move(action, verbose):
    if not verbose:
        return
    data = action['data']
    print(pretty_date(action['date']), '• Moved by', action['memberCreator']['username'])
    print('   ', data['listBefore']['name'], '→', data['listAfter']['name'])


def display_state(action, verbose):
    if not verbose:
        return
    data = action['data']
    if data['card']['closed']:
        print(pretty_date(action['date']), '• Closed by', action['memberCreator']['username'])
    else:
        print(pretty_date(action['date']), '• Opened by', action['memberCreator']['username'])


def display_card_update(action, verbose):
    if not verbose:
        return
    old = action['data']['old']
    new = action['data']['card']

    if 'desc' in old:
        print(pretty_date(action['date']), '• Description updated by', action['memberCreator']['username'])
        print('   ┄┉━ Old Description ━┉┄')
        md_print(old['desc'])
        print('   ┄┉━ New Description ━┉┄')
        md_print(new['desc'])
        print()
    if 'name' in old:
        print(pretty_date(action['date']), '• Summary updated by', action['memberCreator']['username'])
        print('   Old Name:', old['name'])
        print('   New Name:', new['name'])


update_map = {
    'idList': display_move,
    'closed': display_state,
    'due': action_null,           # Due date/time set
    'dueReminder': action_null,   # Due reminder set
    'pos': action_null,           # Priority change
    'name': display_card_update,  # Name updated
    'desc': display_card_update,  # Description updated
    'isTemplate': action_null     # Card is a template
}


def action_update(action, verbose):
    update_type = list(action['data']['old'].keys())[0]

    try:
        update_map[update_type](action, verbose)
    except KeyError:
        print('warning: unhandled action type:', action['type'] + ':' + update_type)


def action_create(action, verbose):
    print(pretty_date(action['date']), '• Created by', action['memberCreator']['username'])


action_map = {
    'commentCard': action_comment,
    'updateCard': action_update,
    'createCard': action_create,
    'addMemberToCard': action_null,
    'removeMemberFromCard': action_null,
    'addAttachmentToCard': action_null,
    'deleteAttachmentFromCard': action_null,
    'copyCard': action_null,
    'addChecklistToCard': action_null,
    'removeChecklistFromCard': action_null,
    'updateCheckItemStateOnCard': action_null,
    'updateCustomFieldItem': action_null
}


def display_action(action, verbose):
    try:
        action_map[action['type']](action, verbose)
    except KeyError:
        print('warning: unhandled action type:', action['type'])
        pass


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


def print_labels(card, prefix='Labels: '):
    if 'labels' in card and len(card['labels']):
        print(prefix, end='')
        for label in card['labels']:
            print(color_string(label['name'], 'white', bgcolor=label['color']), end=' ')
        print()


def print_card(board, card, verbose):
    sep = '┃'
    lsize = max(len(str(card['idShort'])), len('Assignee(s)'))

    print(str(card['idShort']).ljust(lsize), sep, card['name'])

    if verbose:
        print('ID'.ljust(lsize), sep, card['id'])
        print('URL'.ljust(lsize), sep, card['url'])

    print_labels(card, prefix='Labels'.ljust(lsize) + f' {sep} ')

    if 'idMembers' in card and card['idMembers']:
        board_members = board.members()
        print('Assignee(s)'.ljust(lsize), sep, end=' ')
        if verbose:
            print()
        for member in board_members:
            if member['id'] not in card['idMembers']:
                continue
            if verbose:
                print(' '.ljust(lsize), sep, '•', member['username'], '-', member['fullName'])
            else:
                print(member['username'], end=' ')
        if not verbose:
            print()

    if card['desc']:
        md_print(card['desc'])

    if int(card['badges']['attachments']):
        print()
        hbar_under('Attachments')
        attachments = board.trello.cards.get_attachments(card['id'])
        for attachment in attachments:
            display_attachment(attachment, verbose)

    print()
    hbar_under('Activity')

    for act in card['history']:
        display_action(act, verbose)


def cat(args):
    cards = []
    for card_idx in args.card_id:
        card = args.board.card(card_idx, True)
        if not card:
            print('No such card:', card_idx)
            return (127, False)
        cards.append(card)

    for card in cards:
        print_card(args.board, card, args.verbose)
    return (0, False)


def purge(args):
    dry_run = True

    if args.yes:
        dry_run = False

    cards = args.board.gc_cards('all', dry_run)
    labels = args.board.gc_labels(dry_run)
    if dry_run:
        if len(cards):
            for card in cards:
                print(' ', card, cards[card]['name'])
            print(f'The preceding {len(cards)} cards would be purged.')
        if len(labels):
            print(f'{len(labels)} unnamed labels would be purged.')
        if len(cards) or len(labels):
            print('Rerun with \'--yes\' to actually perform this operation.')
    else:
        if len(cards):
            print(f'Purged {len(cards)} cards')
        if len(labels):
            print(f'Purged {len(labels)} unnamed labels')

    return (0, False)


def join_card_text(name, desc):
    return name + '\n\n' + desc


def edit_card(args):
    if args.comment:
        comment_id = args.item
        comment = args.board.trello.actions.get(comment_id)
        if args.text:
            new_text = ' '.join(args.text)
        else:
            new_text = editor(comment['data']['text'])
            if not new_text:
                print('Canceled')
                return (0, False)
        if comment['data']['text'] != new_text:
            args.board.trello.actions.update(comment_id, new_text)
        else:
            print('No changes')
        return (0, False)

    card_idx = args.item
    card = args.board.card(card_idx)
    card_text = join_card_text(card['name'], card['desc'])
    if args.text:
        new_text = ' '.join(args.text)
    else:
        new_text = editor(card_text)
    if not new_text:
        print('Canceled')
        return (0, False)
    name, desc = split_card_text(new_text)
    if card['name'] != name or card['desc'] != desc:
        args.board.trello.cards.update(card['id'], name=name, desc=desc)
    else:
        print('No changes')
    return (0, False)


def labels(board, verbose):
    print('Labels:')
    labels = board.labels()
    labels_sorted = sorted(labels, key=lambda val: val['name'].lower())
    for label in labels_sorted:
        if not label['name']:
            label['name'] = 'UNNAMED'
        label_text = '  ' + color_string(label['name'], 'white', bgcolor=label['color'])
        if verbose:
            label_text = label_text + '  ' + label['id']
        print(label_text)
    return (0, False)


def label_card(args):
    verbose = args.verbose
    if not args.target and not args.new:
        return labels(args.board, verbose)

    if args.color:
        if not args.target:
            print('Changing colors requires a label.')
            return (1, False)
        if args.board.label_color(args.target[0], args.color):
            return (0, False)
        return (1, False)

    if args.rename:
        if not args.target or len(args.target) < 2:
            print('Renaming a label requires an old name and a new name.')
            return (1, False)
        if args.board.label_rename(args.target[0], args.target[1]):
            return (0, True)
        return (1, False)

    if args.remove:
        if len(args.target) < 2:
            args.board.delete_label(args.target[0])
        else:
            args.board.unlabel_card(args.target[0], args.target[1])
        return (0, False)
    args.board.label_card(args.target[0], args.target[1])
    return (0, False)


def link(args):
    card_id = args.card
    url = args.url
    if not len(args.name):
        name = url
    else:
        name = ' '.join(args.name)

    args.board.link(card_id, url, name)
    return (0, False)


def detach(args):
    card_id = args.card
    info = ' '.join(args.name)
    args.board.detach(card_id, info)
    return (0, False)


def view_card(args):
    card_id = args.card_id
    card = args.board.card(card_id)
    if not card:
        return (127, False)
    os.system('xdg-open ' + card['shortUrl'])
    return (0, False)


def members(args):
    members = args.board.members()
    for member in members:
        if args.verbose:
            uname = member['username']
            mname = member['fullName']
            mid = member['id']
            print(f'{uname} "{mname}" {mid}')
        else:
            print(member['username'])
    return (0, False)


def assign_card(args):
    args.board.assign(args.card_id, args.members)
    return (0, False)


def unassign_card(args):
    args.board.unassign(args.card_id, args.members)
    return (0, False)


def get_board(board_name=None, config_file=None):
    config = get_config(config_file)
    board_id = None
    readonly = False

    # Backwards compatibility
    if config is None:
        try:
            board_id = os.environ['TROLLY_BOARD']
        except KeyError:
            print('Please set a TROLLY_BOARD environment variable')
            raise

        try:
            readonly = os.environ['TROLLY_READONLY']
            if readonly in ('1', 'true', 'True', 'yes', 'Yes'):
                readonly = True
        except KeyError:
            pass
    else:
        if board_name is None:
            try:
                board_name = config['trello']['default_board']
            except IndexError:
                pass
        for board in config['trello']['boards']:
            # take first board if none specified and no default
            if board_name is None:
                board_name = board['name']
            if board_name == board['name']:
                board_id = board['id']
                readonly = False
                try:
                    readonly = board['readonly']
                    if readonly in ('1', 'true', 'True', 'yes', 'Yes'):
                        readonly = True
                except KeyError:
                    pass
                break

    board = trello_init(config)
    return TrollyBoard(board, board_id, readonly=readonly)


def create_parser():
    parser = ComplicatedArgs()

    parser.add_argument('-c', '--config', help='Use this config file (instead of ~/.jirate.json)', default=None)
    parser.add_argument('-b', '--board', help='Use this Trello board (from config file)', default=None)

    cmd = parser.command('ls', help='List card(s)', handler=list_cards)
    cmd.add_argument('-m', '--mine', action='store_true', help='Display only cards assigned to me.')
    cmd.add_argument('-l', '--labels', action='store_true', help='Display card labels.')
    cmd.add_argument('list', nargs='*', help='Restrict to cards in these list(s)')

    cmd = parser.command('search', help='List card(s) with matching text', handler=search_cards)
    cmd.add_argument('text', nargs='*', help='Search text')

    cmd = parser.command('cat', help='Print card(s)', handler=cat)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    cmd.add_argument('card_id', nargs='+', help='Target card(s)')

    cmd = parser.command('view', help='Display card in browser', handler=view_card)
    cmd.add_argument('card_id', help='Target card')

    parser.command('ll', help='List lists on board', handler=list_lists)

    cmd = parser.command('label', help='Manage labels', handler=label_card)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    cmd.add_argument('-r', '--remove', help='Remove label from a card. If no card is specified, removes the label from the board', action='store_true', default=False)
    cmd.add_argument('--color', help='Specify a label\'s color',
                     choices=['blue', 'green', 'orange', 'purple', 'red', 'yellow', 'sky', 'lime', 'pink', 'black'])
    cmd.add_argument('--rename', action='store_true', default=False, help='Rename a label')
    cmd.add_argument('-n', '--new', help='Create a new label')
    cmd.add_argument('target', help='Target Card/Label', nargs='*')

    cmd = parser.command('assign', help='Assign card to board member(s)', handler=assign_card)
    cmd.add_argument('card_id', help='Target card')
    cmd.add_argument('members', help='Board members (if none, assign to self)', nargs='*')

    cmd = parser.command('unassign', help='Remove assignee(s) from card', handler=unassign_card)
    cmd.add_argument('card_id', help='Target card')
    cmd.add_argument('members', help='Card assignees (if none, remove only self)', nargs='*')

    cmd = parser.command('mv', help='Move card(s) or rename a list', handler=move)
    cmd.add_argument('src', metavar='card|list_name', nargs='+', help='Card IDs or list to rename')
    cmd.add_argument('target', help='Target list name')

    cmd = parser.command('new', help='Create a new card', handler=new_card)
    cmd.add_argument('text', nargs='*', help='Card title')

    cmd = parser.command('comment', help='Comment on a card', handler=comment)
    cmd.add_argument('card', help='Card to comment on')
    cmd.add_argument('text', nargs='*', help='Comment text')

    cmd = parser.command('members', help='Manipulate board members', handler=members)
    cmd.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    cmd = parser.command('edit', help='Edit card/comment text', handler=edit_card)
    cmd.add_argument('-c', '--comment', action='store_true', help='Edit a comment')
    cmd.add_argument('item', help='Item to edit (card or comment ID)')
    cmd.add_argument('text', nargs='*', help='New text')

    cmd = parser.command('close', help='Close (archive) card(s) or all cards in a list(s)', handler=close_cards)
    cmd.add_argument('-l', '--list', action='store_true', help='Act on lists')
    cmd.add_argument('target', nargs='+', help='Target card(s)/list(s)')

    cmd = parser.command('reopen', help='Reopen (send to board) card(s)', handler=reopen_card)
    cmd.add_argument('card', nargs='+', help='Card IDs reopen')

    cmd = parser.command('link', help='Add a link to a card', handler=link)
    cmd.add_argument('card', help='Target card')
    cmd.add_argument('url', help='URL to link')
    cmd.add_argument('name', nargs='*', help='Text for link')

    cmd = parser.command('detach', help='Remove attachment or link from card', handler=detach)
    cmd.add_argument('card', help='Target card')
    cmd.add_argument('name', nargs='+', help='ID, URL, filename, or name of attachment')

    cmd = parser.command('default', help='Set default list for new cards', handler=set_default)
    cmd.add_argument('list', help='List name')

    cmd = parser.command('purge', help='Remove archived cards and labels from the board', handler=purge)
    cmd.add_argument('--yes', default=False, action='store_true', help='Really do it')

    parser.command('refresh', help='Refresh board configuration', handler=refresh)

    return parser


def main():
    parser = create_parser()
    ns = parser.parse_args()

    try:
        board = get_board(ns.board, config_file=ns.config)
    except KeyError:
        sys.exit(1)

    # Pass this down in namespace to callbacks
    parser.add_arg('board', board)
    rc = parser.finalize(ns)
    if rc:
        ret = rc[0]
        save = rc[1]
    else:
        print('No command specified')
        ret = 0
        save = False
    if save:
        # print('Saving...')
        board.save_config()
    sys.exit(ret)


if __name__ == '__main__':
    main()
