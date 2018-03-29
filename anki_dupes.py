# -*- coding: utf-8 -*-

################################################################################
# DESCRIPTION
################################################################################
# Show duplicates v0.6 aka Ada(update dupe answers).
# Shows card duplicates for a card below it.
################################################################################
# TERMINOLOGY
################################################################################
# {cards} ∈ note, e.g. {仮名, 漢字, 英語} ∈ 日本語
# or in other words, a "note" is a "unit of knowledge" and a "card" is all the
# flashcards based on this unit of knowledge
################################################################################
# TABLE cards
################################################################################
# nid = note ID
# did = deck ID
# ord = ordinal wtf?
# mod = model
################################################################################
# DEBUGGING
################################################################################
# * Call debug() from wherever you need and then just run anki from the console
# * To inspect state without breaking, use the debug window (Ctrl + Shift + ;)
#   Then use "sys.modules['anki_dupes'].ada" to get access the plugin object.
#
# If navigation in pdb does not work, then chances are that readline is not
# linked properly. To fix it, try "import readline", take note of the error
# message, and start workig from there somehow, e.g. by using LD_PRELOAD or
# installing the right package if available.
################################################################################
# TODO
################################################################################
# * Update timings on the duplicates.
# * Maybe re-enable support for the preview mode.
# * Make sure the plugin works with the cram mode & tags, I never use them.
# * Remove the duct tape.
# * Replace the chewing gum and putty with glue.
# * Remove the possibility of creating an omnivoracious sentient black hole due
#   to hash collisions.
################################################################################

import anki, aqt, hashlib, inspect
from aqt.qt import debug
from anki.utils import stripHTMLMedia

class Ada:
    class QACacheEntry:
        """;)"""
        def __init__(self, cid, answer):
            self.cid = cid
            self.answere = answer

    def __init__(self, anki, aqt):
        # Initialize caches & state variables
        self.q2cid = {}                # Question => set(CardIDs)
        self.cid2qa = {}               # Card ID => {'q': Question, 'a': Answer}
        self.recursive = False         # Used to prevent recursive calls.
        self.question = None           # Currently processed question.

        # Install all hooks
        anki.hooks.addHook('mungeQA', self.add_duplicate_answers);
        anki.notes.Note.flush = anki.hooks.wrap(anki.notes.Note.flush, self.update_caches_for_note, 'after')
        anki.cards.Card.flush = anki.hooks.wrap(anki.cards.Card.flush, self.update_caches_for_card, 'after')
        anki.collection._Collection.remCards = anki.hooks.wrap(anki.collection._Collection.remCards, self.remove_cards_from_cache, 'before')
        aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, self.remove_selected_cards_from_cache, 'before')
        aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, self.update_after_deck_change, 'after')

    @staticmethod
    def get_card_qa(collection, card_id):
        return collection.renderQA([card_id])[0]

    def add_cards_to_caches(self, collection, card_ids, did=None, update=False):
        """Add chosen cards for caches.
        did: Specifices the deck if it's known beforehand.
                Justification: Performance. It should save us from running redundant DB queries.
        update: Remove old caches if set to True. Should be set if the cards had been added before.
                Justification: Performance. It's not an error to remove uncached cards, but it takes more time.
        """

        # Or else we'll remember composite answers which is NOT what we want to do.
        was_recursive = self.recursive
        self.recursive = True
        
        if update:
            self.remove_cards_from_cache(collection, card_ids)
        
        for card_id in card_ids:            
            if did:
                # Don't query deck for each card if we know it's the same for all of them.
                deck_id = did
            else:
                deck_id = collection.db.scalar('SELECT did FROM cards WHERE id = {}'.format(card_id))

            if deck_id not in self.q2cid:
                self.q2cid[deck_id] = {}

            # print('Card id = {}'.format(card_id))
            qa = self.get_card_qa(collection, card_id)

            ht = self.q2cid[deck_id]
            q = stripHTMLMedia(qa['q'])
            if q not in ht:
                ht[q] = set()
            ht[q].add(card_id)

            # We also keep the backwards CardID => {'q': Question, 'a': Answer}
            # relation needed when we need top dynamically update the main
            # dictionary if the user adds/edits/deletes cards.
            self.cid2qa[card_id] = qa

        self.recursive = was_recursive

    def add_deck_to_caches(self, collection, deck_id):
        card_ids = collection.db.list('SELECT id FROM cards WHERE did = {}'.format(deck_id))
        self.add_cards_to_caches(collection, card_ids, deck_id)

    def add_duplicate_answers(self, html, card_type, fields, model, data, collection):
        """Combine duplicate answers whenever the card is to be displayed
        data is [cid, nid, mid, did, ord, tags, flds]"""

        # print('add_duplicate_answers(cid={}, did={}, recursive={}, html={})'.format(data[0], data[3], self.recursive, html.encode('utf8')))
        # print('='*40)
        
        # Recursion may happen because reasons. Stolidly ignore it.
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

            q = stripHTMLMedia(self.question)
            # Make sure the card is "legitimate" and not an ad hoc card made e.g.
            # by previewCards@clayout.py. Those have incorrect deck IDs.
            # Seeing duplicates in previews might be nice (and the plugin used to do that),
            # but is also a gamble since it's nigh impossible to guess the correct deck for them.
            # To investigate further, install the anki source code and uncomment the else clause below.
            if (deck_id in self.q2cid) and (q in self.q2cid[deck_id]):
                duplicate_card_ids = self.q2cid[deck_id][q]

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

    def update_caches_for_note(self, s):
        """Dynamic updates of our cache when the user adds/modifies/deletes cards"""
        # print inspect.stack()[0][3]
        self.add_cards_to_caches(s.col, [card.id for card in s.cards()], update=True)

    # When the user adds a card, new cards are not readily available for
    # modification during note.flush().
    def update_caches_for_card(self, s):
        # print inspect.stack()[0][3]
        self.add_cards_to_caches(s.col, [s.id], update=True)
    
    def remove_cards_from_cache(self, s, card_ids, **kwargs):
        """Remove cards from cache. Needed when the user moves them to another deck or deletes them."""
        # print inspect.stack()[0][3]
        query = 'SELECT id, did FROM cards WHERE id in {}'.format(anki.utils.ids2str(card_ids))
        for card_id, deck_id in s.db.execute(query):
            try:
                q = stripHTMLMedia(self.cid2qa[card_id]['q'])
                self.q2cid[deck_id][q].remove(card_id)
                del self.cid2qa[card_id]
            except KeyError:
                # Trying to remove a card that has not been added yet is NOT an error.
                pass

    def remove_selected_cards_from_cache(self, s):
        """Remove selected cards from cache."""
        # print inspect.stack()[0][3]
        self.remove_cards_from_cache(s.mw.col, s.selectedCards())

    def update_after_deck_change(self, s):
        """Update the plugin's hashes after the deck change."""
        # print inspect.stack()[0][3]
        self.add_cards_to_caches(s.mw.col, s.selectedCards())

ada = Ada(anki, aqt)
