#!/usr/bin/python3

import bz2
import copy
import json

from jirate.decor import nym


_TROLLY_CONFIG_CARD = 'META:TROLLY_CONFIG'


# WARNING WARNING WARNING - upon first creation, there's a race between the time
# trello searching finds the card.  It's 10~30 seconds.
def get_config_card(trello, board_id):
    results = trello.search.run(_TROLLY_CONFIG_CARD, idBoards=board_id, modelTypes='cards')
    if results['cards']:
        # print('Found:', results['cards'])
        return results['cards'][0]

    return None


# XXX work around the fact that json doesn't let you index by integers?
def _fix_config(my_config):
    if 'card_rev_map' not in my_config:
        return my_config

    nmap = {int(key): val for key, val in my_config['card_rev_map'].items()}
    my_config['card_rev_map'] = nmap
    return my_config


def _get_board_config(trello, config_card):
    try:
        ret = json.loads(config_card['desc'])
    except json.decoder.JSONDecodeError:
        return None

    # Not an attachment
    if 'attached' not in ret or not ret['attached']:
        return _fix_config(ret)

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
    return _fix_config(config_data)


def get_board_config(trello, board_id):
    return _get_board_config(trello, get_config_card(trello, board_id))


def _suspect(stuff, field, value, exact=False):
    # Pass 1: exact match
    for item in stuff:
        if field not in item:
            continue
        if item[field] == value:
            return item

    if exact:
        return None

    # Pass 2/3: try lowercase or nym()
    for item in stuff:
        if field not in item:
            continue
        if item[field].lower() == value.lower():
            return item
        if nym(item[field]) == nym(value):
            return item
    return None


def _search_attachments(attachments, info):
    # Check by ID
    attachment = _suspect(attachments, 'id', info, exact=True)
    if attachment:
        return attachment

    # 3-way inexact name search
    attachment = _suspect(attachments, 'name', info)
    if attachment:
        return attachment

    # OK, filename and URL
    attachment = _suspect(attachments, 'filename', info, exact=True)
    if attachment:
        return attachment

    attachment = _suspect(attachments, 'url', info, exact=True)
    if attachment:
        return attachment
    return None


class TrollyBoard(object):
    def __init__(self, trello, url, readonly=False):
        self.trello = trello

        if url.startswith('http'):
            board_id = url.rsplit('/', 1)
        else:
            board_id = url

        self._board = trello.boards.get(board_id)
        self._board_id = self._board['id']
        self._ro = readonly

        self._config_card = None
        self._config = None
        if not readonly:
            config_card = get_config_card(trello, self._board_id)
            if config_card:
                self._config_card = config_card['id']
                self._config = _get_board_config(trello, config_card)

        self.refresh()
        if not self._config_card:
            self.index_cards()

    def refresh(self):
        if not self._config:
            self._config = {'lists': {},
                            'list_map': {},
                            'default_list': None,
                            'card_map': {},
                            'card_rev_map': {}}

        self.refresh_lists()

        # Rebuild our reversemap just in case
        rev_map = {int(val): key for key, val in self._config['card_map'].items()}
        self._config['card_rev_map'] = rev_map

    def refresh_lists(self):
        lists = self.trello.boards.get_list(self._board_id)
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

    # Unlike lists, don't use nyms for now
    def refresh_labels(self, force=True):
        if not force and 'labels' in self._config:
            return
        self._config['labels'] = self.trello.boards.get_labels(self._board_id, limit=1000)

    def labels(self):
        self.refresh_labels(False)
        return self._config['labels']

    def label_card(self, card_idx, label_name):
        card = self.card(card_idx)
        label = _suspect(card['labels'], 'name', label_name)
        if label:
            return card

        self.refresh_labels(False)
        label = _suspect(self._config['labels'], 'name', label_name)
        if label:
            return self.trello.cards.new_label_idLabel(card['id'], label['id'])
        return self.trello.cards.new_label(card['id'], label_name)

    def label_color(self, label_name, color):
        self.refresh_labels(False)
        label = _suspect(self._config['labels'], 'name', label_name)
        if label:
            return self.trello.labels.update(label['id'], color=color)
        return None

    def label_rename(self, label_name, new_name):
        self.refresh_labels(False)
        label = _suspect(self._config['labels'], 'name', label_name)
        if label:
            return self.trello.labels.update(label['id'], name=new_name)
        return None

    def refresh_members(self, force=True):
        if not force and 'labels' in self._config:
            return
        self._config['members'] = self.trello.boards.get_member(self._board_id)
        return self._config['members']

    def members(self):
        return self.refresh_members(False)

    def assign(self, card_idx, users):
        card = self.card(card_idx)
        if not card:
            return None
        if users:
            members = self.members()
            if not isinstance(users, list):
                users = [users]
            user_ids = [mb['id'] for mb in members if mb['username'] in users]
            if 'me' in users:
                user = self.trello.members.me()
                if user['id'] not in user_ids:
                    user_ids.append(user['id'])
        else:
            # Just me
            user = self.trello.members.me()
            user_ids = [user['id']]
        for user in user_ids:
            self.trello.cards.new_member(card['id'], user)

    def unassign(self, card_idx, users):
        card = self.card(card_idx)
        if not card:
            return None
        if users:
            members = self.members()
            if not isinstance(users, list):
                users = [users]
            user_ids = [mb['id'] for mb in members if mb['username'] in users]
            if 'me' in users:
                user = self.trello.members.me()
                if user not in users:
                    users.append(user)
        else:
            # Just me
            user = self.trello.members.me()
            user_ids = [user['id']]
        for user in user_ids:
            self.trello.cards.delete_member_idMember(user, card['id'])

    def unlabel_card(self, card_idx, label_name):
        card = self.card(card_idx)
        if not card:
            return None
        if 'labels' not in card:
            return card
        label = _suspect(card['labels'], 'name', label_name)
        if label:
            return self.trello.cards.delete_label_idLabel(label['id'], card['id'])
        return card

    def delete_label(self, label_name):
        self.refresh_labels(True)
        label = _suspect(self._config['labels'], 'name', label_name)
        if label:
            self.trello.labels.delete(label['id'])
        return label

    def gc_labels(self, dry_run=False):
        self.refresh_labels()
        ret = []
        for label in self._config['labels']:
            if 'name' not in label or not label['name']:
                ret.append(label)
        if not dry_run:
            for label in ret:
                self.trello.labels.delete(label['id'])
        return ret

    def list_to_id(self, list_alias):
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

    def _index_card(self, card):
        if card['id'] not in self._config['card_map']:
            cid = card['id']
            idx = int(card['idShort'])

            # Store forward and reverse maps
            self._config['card_map'][cid] = idx
            self._config['card_rev_map'][idx] = cid

    def _index_cards(self, cards):
        if 'card_map' not in self._config:
            self._config['card_map'] = {}
        if 'card_rev_map' not in self._config:
            self._config['card_rev_map'] = {}

        for card in cards:
            self._index_card(card)

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
        cards = self.trello.boards.get_card_filter('visible', self._board_id)
        self._config['card_rev_map'] = {}
        self._config['card_map'] = {}
        self._index_cards(cards)

        if board_cleanup is None:
            return None

        # Completely nuke everything that is not on a visible list. This cannot
        # be undone and is destructive.  However, for long-lived boards,
        # old cards pile up and slow things down.
        ret = {}
        all_cards = self.trello.boards.get_card_filter('all', self._board_id)
        for card in all_cards:
            # We just indexed these
            if ((board_cleanup == 'all' and card['id'] in self._config['card_map']) or (board_cleanup == 'list' and card['idList'] in self._config['list_map'])):
                continue
            if card['id'] == self._config_card:
                continue
            item = {'id': card['id'], 'name': card['name']}
            ret[card['idShort']] = item
            if not dry_run:
                self.trello.cards.delete(card['id'])
        return ret

    def index_cards(self, list_alias=None):
        if list_alias is None:
            cards = self.trello.boards.get_card_filter('visible', self._board_id)
        else:
            cards = self.trello.lists.get_card(self.list_to_id(list_alias))
        self._index_cards(cards)
        return cards

    def _simplify_card_list(self, cards, userid=None):
        ret = {}
        for card in cards:
            if card['closed']:
                continue
            if card['idList'] not in self._config['list_map']:
                continue
            if userid is not None and userid not in card['idMembers']:
                continue
            val = {}
            val['id'] = card['id']
            val['name'] = card['name']
            val['list'] = self._config['list_map'][card['idList']]
            if 'labels' in card:
                val['labels'] = card['labels']
            ret[self._config['card_map'][card['id']]] = val
        return ret

    def search(self, text):
        if not text:
            return None
        ret = self.trello.search.run(text)
        return self._simplify_card_list(ret['cards'])

    def list(self, list_alias=None, userid=None):
        if userid == 'me':
            user = self.trello.members.me()
            userid = user['id']
        cards = self.index_cards(list_alias)
        return self._simplify_card_list(cards, userid)

    def card(self, card_index, verbose=False):
        need_index = False
        try:
            card_index = int(card_index)
            if card_index not in self._config['card_rev_map']:
                need_index = True
        except ValueError:
            if card_index not in self._config['card_map']:
                need_index = True
        if need_index:
            self.index_cards()

        if card_index in self._config['card_rev_map']:
            card_id = self._config['card_rev_map'][card_index]
        elif card_index in self._config['card_map']:
            card_id = card_index
        else:
            return None

        card = self.trello.cards.get(card_id)
        if verbose:
            actions = self.trello.cards.get_action(card_id, filter='all')
            card['history'] = actions
        return card

    def move(self, card_indices, list_alias):
        list_id = self.list_to_id(list_alias)
        if list_alias not in self._config['lists'] and list_alias not in self._config['list_map']:
            raise KeyError('No such list: ' + list_alias)

        if not isinstance(card_indices, list):
            card_indices = [card_indices]
        fails = []
        moves = []
        refreshed = False
        for idx in card_indices:
            try:
                idx = int(idx)
            except ValueError:
                raise ValueError('Not an index: ' + idx)
            try:
                card_id = self._config['card_rev_map'][idx]
            except KeyError:
                card_id = None

            # Only fetch once per call
            if not card_id and not refreshed:
                card = self.card(idx)
                if card:
                    card_id = card['id']
            if not card_id:
                fails.append(idx)
            else:
                moves.append(card_id)

        # Do nothing unless we can move all the cards
        if fails:
            raise ValueError('No such card(s): ' + str(fails))
        for card in moves:
            self.trello.cards.update(card, idList=list_id)
        return moves

    def link(self, index, url, text):
        card = self.card(index)
        if not card:
            raise ValueError('No such card: ' + str(index))
        return self.trello.cards.new_attachment(card['id'], url, text)

    def attach(self, index, filename):
        # Attach a physical file to a card.
        pass

    def detach(self, index, info):
        # Remove link/attachment by ID or name.
        # If ambiguous (>1 with same name)
        # raise valueerror
        card = self.card(index)
        if not card:
            raise ValueError('No such card: ' + str(index))

        attachments = self.trello.cards.get_attachments(card['id'])
        attachment = _search_attachments(attachments, info)
        if not attachment:
            return None
        return self.trello.cards.delete_attachment(attachment['id'], card['id'])

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
        return self._config['default_list']

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
        list_id = self.list_to_id(start_list)
        ret = self.trello.cards.new(name, list_id, description)
        self._index_card(ret)
        return ret

    def comment(self, card_idx, text):
        card = self.card(card_idx)
        return self.trello.cards.new_action_comment(card['id'], text)

    def close(self, card_idx):
        card_idx = int(card_idx)
        card_id = self._config['card_rev_map'][card_idx]
        return self.trello.cards.update_closed(card_id, True)

    def reopen(self, card_idx):
        card_idx = int(card_idx)
        if card_idx in self._config['card_rev_map']:
            card_id = self._config['card_rev_map'][card_idx]
            card = self.trello.cards.update_closed(card_id, False)
            return card

        # Search our board
        cards = self.trello.boards.get_card_filter('all', self._board_id)
        for card in cards:
            if int(card['idShort']) != card_idx:
                continue
            # Reopen card
            if card['closed']:
                self.trello.cards.update_closed(card['id'], False)
            # Send to our default list if it was in an archived list
            if card['idList'] not in self._config['list_map']:
                self.trello.cards.update(card['id'],
                                         idList=self._config['default_list'])
            return card

    def save_config(self):
        if self._ro:
            return

        # Create our config card if not present
        if not self._config_card:
            # print('Creating config card')
            list_id = list(self._config['list_map'].keys())[0]
            card = self.trello.cards.new(_TROLLY_CONFIG_CARD, list_id)
            self._config_card = card['id']
            # Hide our config card
            self.trello.cards.update_closed(card['id'], True)

        # Store config as text in description if <=15kb, otherwise store as
        # attachment
        if 'labels' in self._config:
            del self._config['labels']
        config_str = json.dumps(self._config, indent=2)
        if len(config_str) <= 15360:  # Trello limit is 16k for descriptions
            if 'attached' in self._config:
                # Sadly, need to do two dumps
                del self._config['attached']
                config_str = json.dumps(self._config, indent=2)
            self.trello.cards.update(self._config_card, desc=config_str)
            return

        if 'attached' not in self._config:
            new_desc = json.dumps({'attached': True})
            self.trello.cards.update(self._config_card, desc=new_desc)
            self._config['attached'] = True
            config_str = json.dumps(self._config, indent=2)

        config_info = config_str.encode('utf-8')

        attachments = self.trello.cards.get_attachments(self._config_card)
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
        self.trello.cards.new_file_attachment(self._config_card, 'trolly-config.bz2',
                                              bindata=bz2.compress(config_info))
        if old_config:
            self.trello.cards.delete_attachment(old_config, self._config_card)

    def config(self):
        return copy.copy(self._config)

    def set_user_data(self, key, userdata):
        if key in ('default_list', 'lists', 'list_map', 'card_map', 'card_rev_map'):
            return KeyError('Reserved configuration keyword: ' + key)
        self._config['userdata']
        self.save_config()
