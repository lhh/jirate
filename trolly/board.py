#!/usr/bin/python3

import bz2
import copy
import json


_TROLLY_CONFIG_CARD = 'META:TROLLY_CONFIG'


def nym(s):
    z = s.lower().replace(' ', '_')
    z.replace('\t', '_')
    return z


# WARNING WARNING WARNING - upon first creation, there's a race between the time
# trello searching finds the card.  It's 10~30 seconds.
def get_config_card(trello, board_id):
    results = trello.search.run(_TROLLY_CONFIG_CARD, idBoards=board_id, modelTypes='cards')
    if results['cards']:
        # print('Found:', results['cards'])
        return results['cards'][0]

    return None


def _get_board_config(trello, config_card):
    try:
        ret = json.loads(config_card['desc'])
    except json.decoder.JSONDecodeError:
        return None

    # Not an attachment
    if 'attached' not in ret or not ret['attached']:
        return ret

    attachments = trello.cards.get_attachments(config_card['id'])
    config_id = None
    for suspect in attachments:
        if not suspect['isUpload']:
            continue
        if suspect['name'] != 'trolly-config.bz2':
            continue
        config_id = suspect['id']
        break

    if not config_id:
        return None
    try:
        config_attachment = trello.cards.get_attachment(config_card['id'], config_id, max_size=(1024 * 1024 * 4))
    except json.decoder.JSONDecodeError:
        return None

    config_data = json.loads(bz2.decompress(config_attachment['data']).decode('utf-8'))
    return config_data


def get_board_config(trello, board_id):
    return _get_board_config(trello, get_config_card(trello, board_id))


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
            print('warning: no configuration')
            self._config_card = None
            self._config = None

        self.refresh()

    def refresh(self):
        lists = self._trello.boards.get_list(self._board_id)

        if not self._config:
            self._config = {'lists': {}, 'list_map': {}, 'default_list': None, 'card_idx': 0}
            self._config['card_map'] = {}
            self._config['card_rev_map'] = {}

        # XXX this shouldn't be needed; but the search ignores closed lists
        curr_lists = set([item['id'] for item in lists])
        config_lists = set(self._config['list_map'].keys())
        to_remove = list(config_lists - curr_lists)

        # If we closed a list, unlink it
        for listid in to_remove:
            # purge from our lists
            if listid in self._config['list_map']:
                # print('Unlinking list', listid)
                del self._config['lists'][self._config['list_map'][listid]]
                del self._config['list_map'][listid]

        for item in lists:
            # XXX consistency checks for the configuration?
            # print('checking', item['id'])

            if not self._config['default_list'] or self._config['default_list'] not in self._config['list_map']:
                # print('Resetting default start list to', item['id'])
                self._config['default_list'] = item['id']

            # Update in case we renamed list on the UI side
            if item['id'] in self._config['list_map']:
                self._config['lists'][self._config['list_map'][item['id']]]['name'] = item['name']
                continue

            val = {}
            val['name'] = item['name']
            val['id'] = item['id']
            name = nym(val['name'])
            while name in self._config['lists']:
                name = name + '_'
            self._config['lists'][name] = val
            self._config['list_map'][item['id']] = name

        # Rebuild our reversemap just in case
        rev_map = {val: key for key, val in self._config['card_map'].items()}
        self._config['card_rev_map'] = rev_map

    def _list_to_id(self, list_alias):
        if list_alias not in self._config['lists'] and list_alias not in self._config['list_map']:
            raise KeyError('No such list: ' + list_alias)
        if list_alias in self._config['lists']:
            return self._config['lists'][list_alias]['id']
        return list_alias  # must be the ID

    def card_id(self, index):
        if 'card_rev_map' not in self._config:
            return None
        if index not in self._config['card_rev_map']:
            return None
        return self._config['card_rev_map'][index]

    def _index_cards(self, cards):
        if 'card_map' not in self._config:
            self._config['card_map'] = {}
        if 'card_rev_map' not in self._config:
            self._config['card_rev_map'] = {}

        for card in cards:
            # Nondecreasing Integer map for cards
            if card['id'] not in self._config['card_map']:
                cid = card['id']
                idx = int(card['idShort'])

                # Store forward and reverse maps
                self._config['card_map'][cid] = idx
                self._config['card_rev_map'][idx] = cid

    # Prune all invisible or closed cards from our tables
    # Originally, this would look for cards which are closed, but due to how
    # Trello's filters work, it's quicker to simply scrap our tables and
    # reindex them.
    #
    # board_cleanup = 'list': prune all cards not on a current in-use list
    #               = 'all': prune all archived cards and cards as above
    def gc_cards(self, board_cleanup=None, dry_run=False):
        if board_cleanup not in (None, 'all', 'list'):
            raise ValueError('Invalid value for board_cleanup: ' + board_cleanup)
        cards = self._trello.boards.get_card_filter('visible', self._board_id)
        self._config['card_rev_map'] = {}
        self._config['card_map'] = {}
        self._index_cards(cards)

        if board_cleanup is None:
            return None

        # Completely nuke everything that is not on a visible list. This cannot
        # be undone and is destructive.  However, for long-lived boards,
        # old cards pile up and slow things down.
        ret = {}
        all_cards = self._trello.boards.get_card_filter('all', self._board_id)
        for card in all_cards:
            # We just indexed these
            if ((board_cleanup == 'all' and card['id'] in self._config['card_map']) or (board_cleanup == 'list' and card['idList'] in self._config['list_map'])):
                continue
            if card['id'] == self._config_card:
                continue
            item = {'id': card['id'], 'name': card['name']}
            ret[card['idShort']] = item
            if not dry_run:
                self._trello.cards.delete(card['id'])
        return ret

    def index_cards(self, list_alias=None):
        if list_alias is None:
            cards = self._trello.boards.get_card_filter('visible', self._board_id)
        else:
            cards = self._trello.lists.get_card(self._list_to_id(list_alias))
        self._index_cards(cards)
        return cards

    def list(self, list_alias=None):
        cards = self.index_cards(list_alias)

        ret = {}
        for card in cards:
            if card['closed']:
                continue
            if card['idList'] not in self._config['list_map']:
                continue
            val = {}
            val['id'] = card['id']
            val['name'] = card['name']
            val['list'] = self._config['list_map'][card['idList']]
            ret[self._config['card_map'][card['id']]] = val
        return ret

    def card(self, card_index):
        card_id = int(card_index)
        if card_index not in self._config['card_rev_map'] and card_index not in self._config['card_map']:
            self.index_cards()

        if card_index in self._config['card_rev_map']:
            card_id = self._config['card_rev_map'][card_index]
        elif card_index not in self._config['card_map']:
            card_id = card_index
        else:
            return None

        return self._trello.cards.get(card_id)

    def move(self, card_indices, list_alias):
        list_id = self._list_to_id(list_alias)
        if list_alias not in self._config['lists'] and list_alias not in self._config['list_map']:
            raise KeyError('No such list: ' + list_alias)

        if not isinstance(card_indices, list):
            card_indices = [card_indices]
        fails = []
        moves = []
        for idx in card_indices:
            idx = int(idx)
            card_id = self._config['card_rev_map'][idx]
            if not card_id:
                fails.append(idx)
            else:
                moves.append(card_id)

        # Do nothing unless we can move all the cards
        if fails:
            raise ValueError('No such card(s): ' + str(fails))
        for card in moves:
            self._trello.cards.update(card, idList=list_id)
        return moves

    def default_list(self, list_alias=None):
        if list_alias is None:
            return self._config['default_list']
        if list_alias not in self._config['lists'] and list_alias not in self._config['list_map']:
            raise KeyError('No such list: ' + list_alias)
        if list_alias in self._config['lists']:
            self._config['default_list'] = self._config['lists'][list_alias]['id']
        elif list_alias in self._config['list_map']:
            self._config['default_list'] = list_alias
        else:
            raise Exception('Code path error')

    def rename(self, list_alias, new_name):
        if list_alias not in self._config['lists'] and list_alias not in self._config['list_map']:
            raise KeyError('No such list: ' + list_alias)

        if list_alias in self._config['lists']:
            list_id = self._config['lists'][list_alias]['id']
            list_name = list_alias
        elif list_alias in self._config['list_map']:
            list_name = self._config['list_map'][list_alias]
            list_id = list_alias

        self._config['list_map'][list_id] = new_name
        val = self._config['lists'][list_name]
        del self._config['lists'][list_name]
        self._config['lists'][new_name] = val

    def lists(self):
        return copy.copy(self._config['lists'])

    def new(self, name, description=None, start_list=None):
        if start_list is None:
            start_list = self._config['default_list']
        list_id = self._list_to_id(start_list)
        return self._trello.cards.new(name, list_id, description)

    def close(self, card_idx):
        card_idx = int(card_idx)
        card_id = self._config['card_rev_map'][card_idx]
        return self._trello.cards.update_closed(card_id, True)

    def reopen(self, card_idx):
        card_idx = int(card_idx)
        if card_idx in self._config['card_rev_map']:
            card_id = self._config['card_rev_map'][card_idx]
            card = self._trello.cards.update_closed(card_id, False)
            return card

        # Search our board
        cards = self._trello.boards.get_card_filter('all', self._board_id)
        for card in cards:
            if int(card['idShort']) != card_idx:
                continue
            # Reopen card
            if card['closed']:
                self._trello.cards.update_closed(card['id'], False)
            # Send to our default list if it was in an archived list
            if card['idList'] not in self._config['list_map']:
                self._trello.cards.update(card['id'],
                                          idList=self._config['default_list'])
            return card

    def save_config(self):
        # Create our config card if not present
        if not self._config_card:
            # print('Creating config card')
            list_id = list(self._config['list_map'].keys())[0]
            card = self._trello.cards.new(_TROLLY_CONFIG_CARD, list_id)
            self._config_card = card['id']
            # Hide our config card
            self._trello.cards.update_closed(card['id'], True)

        # Store config as text in description if <=15kb, otherwise store as
        # attachment
        config_str = json.dumps(self._config, indent=2)
        if len(config_str) <= 15360:  # Trello limit is 16k for descriptions
            if 'attached' in self._config:
                # Sadly, need to do two dumps
                del self._config['attached']
                config_str = json.dumps(self._config, indent=2)
            self._trello.cards.update(self._config_card, desc=config_str)
            return

        if 'attached' not in self._config:
            new_desc = json.dumps({'attached': True})
            self._trello.cards.update(self._config_card, desc=new_desc)
            self._config['attached'] = True
            config_str = json.dumps(self._config, indent=2)

        config_info = config_str.encode('utf-8')

        attachments = self._trello.cards.get_attachments(self._config_card)
        old_config = None
        for suspect in attachments:
            if not suspect['isUpload']:
                continue
            if suspect['name'] != 'trolly-config.bz2':
                continue
            old_config = suspect['id']
            break

        # Upload new attachment, then purge the old one, just in case we
        # crash - better to have two (one slightly out of date) than none
        self._trello.cards.new_file_attachment(self._config_card, 'trolly-config.bz2',
                                               bindata=bz2.compress(config_info))
        if old_config:
            self._trello.cards.delete_attachment(old_config, self._config_card)

    def config(self):
        return copy.copy(self._config)

    def set_user_data(self, key, userdata):
        if key in ('default_list', 'lists', 'list_map', 'card_map', 'card_rev_map'):
            return KeyError('Reserved configuration keyword: ' + key)
        self._config['userdata']
        self.save_config()
