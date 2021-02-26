#!/usr/bin/python3

import os
import re
# import yaml

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


def new_card(board, argv):
    # todo argparse here
    desc = ' '.join(argv)
    card = board.new(desc)
    print(card['idShort'], card['name'])
    return (0, False)


def refresh(board, argv):
    board.refresh()
    board.index_cards()
    return (0, True)


commands = {
    'ls': list_cards,
    'll': list_lists,
    'mv': move,
    'close': close,
    'new': new_card,
    'reopen': reopen,
    'refresh': refresh
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
