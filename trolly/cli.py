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
    if board.move(argv, target):
        print('Moved', argv, 'to', target)
        return 0
    return 1


def close(board, argv):
    if board.close(argv[0]):
        return 0
    return 1


def reopen(board, argv):
    if board.close(argv[0]):
        return 0
    return 1


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


def new_card(board, argv):
    # todo argparse here
    desc = ' '.join(argv)
    card = board.new(desc)
    print(card['idShort'], card['name'])


def refresh(board, argv):
    board.refresh()
    board.save_config()


commands = {
    'list': list_cards,
    'move': move,
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
    sys.exit(commands[cmd](board, argv))


def get_board():
    my_board = os.environ['TROLLY_BOARD']
    tboard = trello_init()
    return board.TrollyBoard(tboard, my_board)


def main():
    parse(get_board())


if __name__ == '__main__':
    main()
