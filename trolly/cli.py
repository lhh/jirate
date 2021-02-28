#!/usr/bin/python3

import os
import re
# import yaml

import editor

from trollo import TrelloApi

from trolly import board


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


# config = get_config("~/.trellosync")
def trello_init():
    TRELLO_KEY = os.environ['TRELLO_KEY']
    TRELLO_TOKEN = os.environ['TRELLO_TOKEN']

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


def move(board, argv):
    if len(argv) < 2:
        raise ValueError('move requires at least 2 arguments')

    target = argv.pop()
    if len(argv) == 1:
        try:
            board.rename(argv[0], target)
            return (0, True)
        except KeyError:
            pass

    if board.move(argv, target):
        print('Moved', argv, 'to', target)
        return (0, False)
    return (1, False)


def close(board, argv):
    if board.close(argv[0]):
        return (0, False)
    return (1, False)


def reopen(board, argv):
    if board.reopen(argv[0]):
        return (0, False)
    return (1, False)


def list_cards(board, argv):
    if not argv:
        cards = board.list()
    else:
        cards = board.list(argv[0])

    lists = {}
    for card in cards:
        clist = cards[card]['list']
        if clist not in lists:
            lists[clist] = []
        lists[clist].append([card, cards[card]['name']])

    for key in lists:
        print(key)
        for item in lists[key]:
            print('  ', item[0], item[1])
    return (0, True)


def list_lists(board, argv):
    default = board.default_list()
    lists = board.lists()
    for lname in lists:
        if lists[lname]['id'] == default:
            print(' *', lname, lists[lname]['name'])
        else:
            print('  ', lname, lists[lname]['name'])
    return (0, False)


def set_default(board, argv):
    default = board.default_list()
    new_default = board.default_list(argv[0])
    return (0, (default != new_default))


def new_card(board, argv):
    desc = None
    if argv:
        name = ' '.join(argv)
    else:
        text = editor()
        lines = text.split('\n')
        name = lines[0]
        if not len(name):
            print('New card creation canceled.')
            return (1, False)
        lines.pop(0)
        while len(lines) and lines[0] == '':
            lines.pop(0)
        if len(lines):
            desc = '\n'.join(lines)

    card = board.new(name, desc)
    print(card['idShort'], card['name'])
    return (0, True)


def comment(board, argv):
    if not argv:
        return (1, False)

    card_id = int(argv.pop(0))
    if argv:
        text = ' '.join(argv)
    else:
        text = editor()

    board.comment(card_id, text)
    return (0, False)


def refresh(board, argv):
    board.refresh()
    board.index_cards()
    return (0, True)


def action_null(action):
    pass


def action_comment(action):
    data = action['data']
    print(action['date'], '- Comment by', action['memberCreator']['username'])
    print('=====')
    print(data['text'])


def display_move(action):
    data = action['data']
    print(action['date'], '- Moved by', action['memberCreator']['username'])
    print('   ', data['listBefore']['name'], '→', data['listAfter']['name'])


def display_state(action):
    data = action['data']

    if data['card']['closed']:
        print(action['date'], '- Closed by', action['memberCreator']['username'])
    else:
        print(action['date'], '- Opened by', action['memberCreator']['username'])


update_map = {
    'idList': display_move,
    'closed': display_state,
    'desc': action_null
}


def action_update(action):
    update_type = list(action['data']['old'].keys())[0]

    try:
        update_map[update_type](action)
    except KeyError:
        print('warning: unhandled action type:', action['type'] + ':' + update_type)


def action_create(action):
    print(action['date'], '- Created by', action['memberCreator']['username'])


action_map = {
    'commentCard': action_comment,
    'updateCard': action_update,
    'createCard': action_create,
    'addAttachmentToCard': action_null,
    'deleteAttachmentFromCard': action_null
}


def display_action(action):
    try:
        action_map[action['type']](action)
    except KeyError:
        print('warning: unhandled action type:', action['type'])
        pass


def cat(board, argv):
    card = board.card(argv[0], True)
    if not card:
        return (127, False)

    print(card['idShort'], '-', card['name'])
    if card['desc']:
        print()
        print(card['desc'])
    print()
    print('Activity')
    print('--------')

    for act in card['history']:
        display_action(act)

    return (0, False)


def purge(board, argv):
    dry_run = True

    if len(argv) and argv[0] == '--yes':
        dry_run = False

    cards = board.gc_cards('all', dry_run)
    if dry_run:
        print(f'These {len(cards)} cards would be purged:')
        for card in cards:
            print(' ', card, cards[card]['name'])
        print('Rerun with \'--yes\' to actually perform this operation.')
    else:
        print(f'Purged {len(cards)} cards')

    return (0, False)


commands = {
    'ls': list_cards,
    'll': list_lists,
    'comment': comment,
    'default': set_default,
    'mv': move,
    'cat': cat,
    'close': close,
    'new': new_card,
    'reopen': reopen,
    'refresh': refresh,
    'purge': purge
}


def parse(board):
    import sys
    argv = sys.argv
    argv.pop(0)

    if not len(argv):
        print('No command specified')
        sys.exit(0)
    cmd = argv.pop(0)
    ret, save = commands[cmd](board, argv)
    if save:
        # print('Saving...')
        board.save_config()
    sys.exit(ret)


def get_board():
    my_board = os.environ['TROLLY_BOARD']
    tboard = trello_init()
    return board.TrollyBoard(tboard, my_board)


def main():
    parse(get_board())


if __name__ == '__main__':
    main()
