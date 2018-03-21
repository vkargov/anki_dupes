# -*- coding: utf-8 -*-

# Show duplicates v0.5 aka Ada(update dupe answers)
# Shows card duplicates for a card below it.

# TODO
# Update timings on the duplicates.
# Remove the duct tape.
# Replace the chewing gum and putty with glue.
# Remove the possibility of creating an omnivoracious sentient black hole due to hash collision.

import anki, aqt, hashlib

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
# {cards} ∈ note, e.g. {仮名, 漢字, 英語} ∈ 日本語
# or in other words, a "note" is a "unit of knowledge" and a "card" is all the
# flashcards based on this unit of knowledge

# TABLE cards:
# nid = note ID
# did = deck ID
# ord = ordinal wtf?
# mod = model

# DEBUGGING
# Use the debug() call to put breakpoints wherever you need and then
# just run anki from the console

################################################################################

class Ada:
    """This class is not instantiated, it's just to clamp up the global
    state and methods of the add-on together. Probably a bad idea, but I'm
    rolling with it for the time being."""

    class Question:
        """Currently processed question."""
        pass

    class CacheEntry:
        """QA cache entry."""
        def __init__(self, card_id, answer_html):
            self.card_id = card_id
            self.answer_html = answer_html
    
    q2a = {}                    # Question => set(Answers)
    cid2qa = {}                 # Card ID => {'q': Question, 'a': Answer}
    recursive = False           # Used to prevent recursive calls.
    question = Question()       # Currently processed question.

    @static_method
    def get_card_qa(collection, card_id):
        return collection.renderQA([card_id])[0]

    @static_method
    def add_cards_to_caches(collection, card_ids):
        for card_id in card_ids:
            qa = get_card_qa(collection, card_id)['q']

            Ada.q2a[deck_id][qa['q']] = set(card_id)

            # We also keep the backwards CardID => {'q': Question, 'a': Answer}
            # relation needed when we need top dynamically update the main
            # dictionary if the user adds/edits/deletes cards.
            Ada.cid2qa[card_id] = qa

    
    @static_method
    def add_deck_to_cache(collection, deck_id):
        Ada.qa_cache[deck_id] = {}
        card_ids = collection.db.list('SELECT id FROM cards WHERE did = {}').format(deck_id)
        add_cards_to_cache(collection, card_ids)

    @static_method
    def add_duplicate_answers(html, card_type, fields, model, data, collection):
        """Combine duplicate answers whenever the card is to be displayed
        data is [cid, nid, mid, did, ord, tags, flds]"""

        # Recursion may happen because reasons. Stolidly ignore it.
        # _log("add_dupe_answers: recursive={}".format(ada.recursive))
        if recursive:
            return html

        if card_type == 'q':
            # Questions remain unique, just remember them
            Ada.question.text = html
            Ada.question.fields = fields
            Ada.question.model = model
            Ada.question.data = data
            Ada.question.collection = collection
            
        elif card_type == 'a':
            # Answers, on the other hand, are not. We'll need to walk through all of them that
            # match the question and merge them into one html to be displayed on the screen.

            Ada.recursive = True

            # Check that we are rendering the answers to the card we rememered the question of.
            # This should always be the case.
            assert(question.fields == fields and
                   question.model == model and
                   question.data == data and
                   question.collection == collection)

            deck_id = data[3]

            if deck_id not in QAcache:
                build_cache_for_deck(collection, deck_id)

            duplicates = qa_cache[did][current_question.text]

            # Show the "true" answer at the top.
            united_html = html

            # Internally render QA for each sub-answer and join them together
            for duplicate in duplicates:
                # Enforce that the card is not absent for whatever reason.
                assert(len(col.db.list("select id from cards where id = %d" % suspect_card)) > 0)

                duplicate_qa = cid2qa[suspect_card]
                
                if html != duplicate_qa['a']:
                    # Add the answer part of the HTML
                    united_html += duplicate_qa['a'][len(duplicate_qa['q']):]

            html = united_html

        Ada.recursive = False

        return html

    @staticmethod
    def add_note_to_caches(self):
        """Dynamic updates of our cache when the user adds/modifies/deletes cards"""
        add_cards_to_cache(self.col, self.cards())

    # When the user adds a card, new cards are not readily available for modification during note.flush().
    # TODO: perhaps updating only cards will suffice?
    @staticmethod
    def add_card_to_caches(self):
        add_cards_to_caches(self.col, self.id)

    @staticmethod
    def remove_cards_from_cache(self, card_ids):
        """Remove cards from cache. Needed when the user moves them to another deck or deletes them."""
        for card_id, deck_id in collection.db.list("SELECT id, did FROM cards WHERE id in {}".format(card_ids)):
            qa_cache[deck_id][card_id].remove

    @staticmethod
    def remove_selected_cards_from_cache(self):
        """Remove selected cards from cache."""
        remove_cards_from_cache(self.selectedCards())
            
    @staticmethod
    def update_after_deck_change(self):
        """Update the plugin's hashes after the deck change."""
        update_caches(self.mw.col, self.selectedCards())

anki.hooks.addHook('mungeQA', Ada.add_duplicate_answers);
anki.notes.Note.flush = anki.hooks.wrap(anki.notes.Note.flush, Ada.add_note_to_caches, 'after')
anki.cards.Card.flush = anki.hooks.wrap(anki.cards.Card.flush, Ada.add_card_to_caches, 'after')
anki.cards.remCards = anki.hooks.wrap(anki.cards.remCards, Ada.remove_cards_from_cache, 'before')
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, Ada.remove_selected_cards_from_cache, 'before')
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, Ada.update_after_deck_change, 'after')
