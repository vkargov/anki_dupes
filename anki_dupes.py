# -*- coding: utf-8 -*-

# Show duplicates v0.5 aka Ada(update dupe answers)
# Shows card duplicates for a card below it.

# TODO
# Update timings on the duplicates.
# Remove the duct tape.
# Replace the chewing gum and putty with glue.
# Remove the possibility of creating an omnivoracious sentient black hole due to hash collision.

import anki, aqt, hashlib
from aqt.qt import debug

# _debug = True

# if _debug:
#     from aqt.qt import debug
#     from PyQt4.QtCore import pyqtRemoveInputHook
#     import sys
#     pyqtRemoveInputHook()
#     _log_file = open('ada.log', 'w')
#     def _log(s):
#         _log_file.write(s.encode("utf8") + '\n')
#         _log_file.flush()
#     _log("Python version:\n{}".format(sys.version))
# else:
#     def _log(s):
#         pass


################################################################################
# TERMINOLOGY
################################################################################
# {cards} ∈ note, e.g. {仮名, 漢字, 英語} ∈ 日本語
# or in other words, a "note" is a "unit of knowledge" and a "card" is all the
# flashcards based on this unit of knowledge
################################################################################
# TABLE cards:
################################################################################
# nid = note ID
# did = deck ID
# ord = ordinal wtf?
# mod = model
################################################################################
# DEBUGGING
################################################################################
# Call debug() from wherever you need and then
# just run anki from the console
#
# If navigation in pdb does not work, then chances are that readline is broken,
# to fix it do "import readline" and resolve it somehow
# e.g. by using LD_PRELOAD or installing the right package if available
################################################################################

class Ada:
    class QACacheEntry:
        """;)"""
        def __init__(self, cid, answer):
            self.cid = cid
            self.answere = answer

    def __init__(self):
        self.q2cid = {}                # Question => set(CardIDs)
        self.cid2qa = {}               # Card ID => {'q': Question, 'a': Answer}
        self.recursive = False         # Used to prevent recursive calls.
        self.question = None           # Currently processed question.

    @staticmethod
    def get_card_qa(collection, card_id):
        return collection.renderQA([card_id])[0]

    def add_cards_to_caches(self, collection, card_ids, did=None):
        for card_id in card_ids:
            if did:
                # Don't query deck for each card if we know it's the same for all of them.
                deck_id = did
            else:
                deck_id = 'SELECT did FROM cards WHERE id = {}'.format(card_id)

            deck_id = collection.db.scalar('SELECT did FROM cards WHERE id = {}'.format(card_id))
            qa = self.get_card_qa(collection, card_id)

            ht = self.q2cid[deck_id]
            if qa['q'] not in ht:
                ht[qa['q']] = set()
            ht[qa['q']].add(card_id)

            # We also keep the backwards CardID => {'q': Question, 'a': Answer}
            # relation needed when we need top dynamically update the main
            # dictionary if the user adds/edits/deletes cards.
            self.cid2qa[card_id] = qa

    def add_deck_to_caches(self, collection, deck_id):
        print('add_deck_to_caches(did={})'.format(deck_id))
        print('='*40)
        self.q2cid[deck_id] = {}
        card_ids = collection.db.list('SELECT id FROM cards WHERE did = {}'.format(deck_id))
        self.add_cards_to_caches(collection, card_ids, deck_id)

    def add_duplicate_answers(self, html, card_type, fields, model, data, collection):
        """Combine duplicate answers whenever the card is to be displayed
        data is [cid, nid, mid, did, ord, tags, flds]"""

        print('add_duplicate_answers(cid={}, did={}, recursive={}, html={})'.format(data[0], data[3], self.recursive, html.encode('utf8')))
        print('='*40)
        
        # Recursion may happen because reasons. Stolidly ignore it.
        # _log("add_dupe_answers: recursive={}".format(ada.recursive))
        if self.recursive:
            return html

        if card_type == 'q':
            self.question = html
        elif card_type == 'a':
            # Answers, on the other hand, are not. We'll need to walk through all of them that
            # match the question and merge them into one html to be displayed on the screen.

            self.recursive = True

            deck_id = data[3]

            if deck_id not in self.q2cid:
                self.add_deck_to_caches(collection, deck_id)

            # Make sure the card is "legitimate" and not an ad hoc card made e.g.
            # by previewCards@clayout.py. Those have incorrect deck names.
            # Handling them might be nice, but is also a gamble since it's
            # nigh impossible to guess the correct deck for them.
            # To investigate further, uncommend the else clause below.
            if self.question in self.q2cid[deck_id]:
                duplicate_card_ids = self.q2cid[deck_id][self.question]

                # Show the "true" answer at the top.
                united_html = html

                # Internally render QA for each sub-answer and join them together
                for duplicate_card_id in duplicate_card_ids:
                    duplicate_qa = self.cid2qa[duplicate_card_id]

                    if html != duplicate_qa['a']:
                        # Add the answer part of the HTML
                        united_html += duplicate_qa['a'][len(duplicate_qa['q']):]

                html = united_html
            # else:
            #     debug()

        self.recursive = False

        return html

    def add_note_to_caches(self, s):
        """Dynamic updates of our cache when the user adds/modifies/deletes cards"""
        self.add_cards_to_caches(s.col, [card.id for card in s.cards()])

    # When the user adds a card, new cards are not readily available for modification during note.flush().
    # TODO: perhaps updating only cards will suffice?
    def add_card_to_caches(self, s):
        self.add_cards_to_caches(s.col, s.id)
    
    def remove_cards_from_cache(self, s, card_ids, **args):
        """Remove cards from cache. Needed when the user moves them to another deck or deletes them."""
        for card_id, deck_id in s.db.execute('SELECT id, did FROM cards WHERE id in {}'.format(card_ids)):
            self.q2cid[deck_id][self.cid2qa[card_id]['q']].remove(card_id)
            del self.cid2qa[card_id]
            

    def remove_selected_cards_from_cache(self, s):
        """Remove selected cards from cache."""
        self.remove_cards_from_cache(s.selectedCards())

    def update_after_deck_change(self, s):
        """Update the plugin's hashes after the deck change."""
        self.update_caches(s.mw.col, s.selectedCards())

ada = Ada()
        
anki.hooks.addHook('mungeQA', ada.add_duplicate_answers);
anki.notes.Note.flush = anki.hooks.wrap(anki.notes.Note.flush, ada.add_note_to_caches, 'after')
anki.cards.Card.flush = anki.hooks.wrap(anki.cards.Card.flush, ada.add_card_to_caches, 'after')
anki.collection._Collection.remCards = anki.hooks.wrap(anki.collection._Collection.remCards, ada.remove_cards_from_cache, 'before')
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, ada.remove_selected_cards_from_cache, 'before')
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, ada.update_after_deck_change, 'after')
