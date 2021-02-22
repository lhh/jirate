#!/usr/bin/python3

import copy
import json
# import yaml
from collections import OrderedDict


_TROLLY_CONFIG_CARD = 'META:TROLLY_CONFIG'


def nym(s):
    z = s.lower().replace(' ', '_')
    z.replace('\t', '_')
    return z


def get_config_card(trello, board_id):
    results = trello.search.run(_TROLLY_CONFIG_CARD, idBoards=board_id, modelTypes='cards')
    if results['cards']:
        # print('Found:', results['cards'])
        return results['cards'][0]

    return None


def _get_board_config(trello, config_card):
    # print('Parsing config card: ', config_card)
    try:
        ret = json.loads(config_card['desc'])
        return ret
    except json.decoder.JSONDecodeError:
        return None


def get_board_config(trello, board_id):
    return _get_board_config(trello, get_config_card(trello, board_id))


def set_board_config(trello, board_id, config_data):
    config_card = get_config_card(trello, board_id)
    if not config_card:
        trello.cards.new
    trello.cards.update(config_card['id'], desc=json.dump(config_data), )


class TrollyBoard(object):
    def __init__(self, trello, url):
        self._trello = trello

        if url.startswith('http'):
            board_id = url.rsplit('/', 1)
        else:
            board_id = url

        self._board = trello.boards.get(board_id)
        self._board_id = self._board['id']

        config_card = get_config_card(trello, self._board_id)
        if config_card:
            self._config_card = config_card['id']
            self._config = _get_board_config(trello, config_card)
        else:
            self._config_card = None
            self._config = None

        self.refresh()
        self.save_config()

    def refresh(self):
        lists = self._trello.boards.get_list(self._board_id)

        if not self._config:
            self._config = {'lists': {}, 'map': OrderedDict(), 'default_list': None, 'card_idx': 0}
            self._config['card_map'] = {}
            self._config['card_rev_map'] = {}

        # XXX this shouldn't be needed; but the search ignores closed lists
        curr_lists = set([item['id'] for item in lists])
        config_lists = set(self._config['map'].keys())
        to_remove = list(config_lists - curr_lists)

        # If we closed a list, unlink it
        for listid in to_remove:
            # purge from our lists
            if listid in self._config['map']:
                # print('Unlinking list', listid)
                del self._config['lists'][self._config['map'][listid]]
                del self._config['map'][listid]

        for item in lists:
            # XXX consistency checks for the configuration?
            # print('checking', item['id'])

            if not self._config['default_list'] or self._config['default_list'] not in self._config['map']:
                # print('Resetting default start list to', item['id'])
                self._config['default_list'] = item['id']

            # Update in case we renamed list on the UI side
            if item['id'] in self._config['map']:
                self._config['lists'][self._config['map'][item['id']]]['name'] = item['name']
                continue

            val = {}
            val['name'] = item['name']
            val['id'] = item['id']
            name = nym(val['name'])
            while name in self._config['lists']:
                name = name + '_'
            self._config['lists'][name] = val
            self._config['map'][item['id']] = name

        # Rebuild our reversemap just in case
        rev_map = {val: key for key, val in self._config['card_map'].items()}
        self._config['card_rev_map'] = rev_map

    def _list_to_id(self, list_alias):
        if list_alias not in self._config['lists'] and list_alias not in self._config['map']:
            raise KeyError('No such list: ' + list_alias)
        if list_alias in self._config['lists']:
            return self._config['lists'][list_alias]['id']
        return list_alias  # must be the ID

    def card_index_to_id(self, index):
        if 'card_rev_map' not in self._config:
            return None
        if 'card_idx' not in self._config:
            return None
        if index not in self._config['card_rev_map']:
            return None
        return self._config['card_rev_map'][index]

    def _index_cards(self, cards):
        if 'card_map' not in self._config:
            self._config['card_map'] = {}
        if 'card_rev_map' not in self._config:
            self._config['card_rev_map'] = {}
        if 'card_idx' not in self._config:
            self._config['card_idx'] = 0

        for card in cards:
            # Nondecreasing Integer map for cards
            if card['id'] not in self._config['card_map']:
                self._config['card_idx'] = self._config['card_idx'] + 1
                cid = card['id']
                idx = self._config['card_idx']

                # Store forward and reverse maps
                self._config['card_map'][cid] = idx
                self._config['card_rev_map'][idx] = cid

    def gc_cards(self):
        cards = self._trello.boards.get_card_filter('closed', self._board_id)
        for card in cards:
            cid = card['id']
            if cid not in self._config['card_map']:
                continue
            del self._config['card_rev_map'][self._config['card_map'][cid]]
            del self._config['card_map'][cid]

    def index_cards(self, list_alias=None, gc=False):
        if list_alias is None:
            cards = self._trello.boards.get_card_filter('open', self._board_id)
        else:
            cards = self._trello.lists.get_card(self._list_to_id(list_alias))
        self._index_cards(cards)

    def list_cards(self, list_alias):
        cards = self._trello.lists.get_card(self._list_to_id(list_alias))
        self._index_cards(cards)

        ret = {}
        for card in cards:
            val = {}
            val['id'] = card['id']
            val['name'] = card['name']
            ret[self._config['card_map'][card['id']]] = val
        return ret

    def move_cards(self, card_indices, list_alias):
        list_id = self._list_to_id(list_alias)
        if list_alias not in self._config['lists'] and list_alias not in self._config['card_map']:
            raise KeyError('No such list: ' + list_alias)

        if not isinstance(card_indices, list):
            card_indices = [card_indices]
        fails = []
        moves = []
        for idx in card_indices:
            card_id = self._config['card_rev_map'][idx]
            if not card_id:
                fails.append(idx)
            else:
                moves.append(card_id)

        if fails:
            raise ValueError('No such card(s): ' + str(fails))
        for card in moves:
            self._trello.cards.update(card, idList=list_id)

    def default_list(self, list_alias):
        if list_alias not in self._config['lists'] and list_alias not in self._config['map']:
            raise KeyError('No such list: ' + list_alias)
        if list_alias in self._config['lists']:
            self._config['default_list'] = self._config['lists'][list_alias]['id']
        elif list_alias in self._config['map']:
            self._config['default_list'] = list_alias
        else:
            raise Exception('Code path error')

    def rename_list(self, list_alias, new_name):
        if list_alias not in self._config['lists'] and list_alias not in self._config['map']:
            raise KeyError('No such list: ' + list_alias)

        if list_alias in self._config['lists']:
            list_id = self._config['lists'][list_alias]['id']
            list_name = list_alias
        elif list_alias in self._config['map']:
            list_name = self._config['map'][list_alias]
            list_id = list_alias

        self._config['map'][list_id] = new_name
        val = self._config['lists'][list_name]
        del self._config['lists'][list_name]
        self._config['lists'][new_name] = val

    def get_lists(self):
        return copy.copy(self._config['lists'])

    def save_config(self):
        config_str = json.dumps(self._config, indent=2)

        if not self._config_card:
            # print('Creating config card')
            list_id = list(self._config['map'].keys())[0]
            card = self._trello.cards.new(_TROLLY_CONFIG_CARD, list_id)
            self._config_card = card['id']

        self._trello.cards.update(self._config_card, desc=config_str)

    def config(self):
        return copy.copy(self._config)

    def set_user_data(self, key, userdata):
        if key in ('default_list', 'lists', 'map', 'card_map', 'card_rev_map', 'card_idx'):
            return KeyError('Reserved configuration keyword: ' + key)
        self._config['userdata']
        self.save_config()
