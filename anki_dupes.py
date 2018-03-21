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
    
    QAcache = {}
    recursive = False
    old_dids = None
    question = Question()       # Current question

    @static_method
    def get_card_qa(collection, card_id):
        return map(anki.utils.stripHTMLMedia, collection.renderQA([card_id])[0])

    @static_method
    def build_cache_from_deck(collection, deck_id):

        # If we haven't built the table for the current deck, do it now.
        # sibaraku omati kudasai

        QAcache[deck_id] = {}
        
        for card_id in collection.db.list("SELECT id FROM cards WHERE did = %d" % deck_id):
            question = get_card_q(collection, card_id)

            QAcache[deck_id][question] = set(card_id)

            # We also keep the backwards CardID => hash(question) relation
            # needed when we need to dynamically update the main dictionary if
            # the user adds/edits/deletes cards.
            Ada.CardID2QA[card_id] = question

    @static_method
    def add_dupe_answers(html, card_type, fields, model, data, collection):
        """Combine duplicate answers whenever the card is to be displayed
        data is [cid, nid, mid, did, ord, tags, flds]"""

        # Recursion may happen because reasons. Stolidly ignore it.
        # _log("add_dupe_answers: recursive={}".format(ada.recursive))
        if Ada.recursive:
            return html

        if card_type == 'q':
            # Questions remain unique, just remember them
            Ada.question.text = anki.utils.stripHTMLMedia(html)
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
            assert ( Ada.question.fields == fields and
                     Ada.question.model == model and
                     Ada.question.data == data and
                     Ada.question.collection == collection)

            deck_id = data[3]            

            if deck_id not in QAcache:
                build_cache_from_deck(collection, deck_id)

            duplicates = ada.QAcache[did][current_question.text]

            # Show the "true" answer at the top.
            united_html = html

            # Internally render QA for each sub-answer and join them together
            for duplicate in duplicates:                
                # Enforce that the card is not absent for whatever reason.
                assert(len(col.db.list("select id from cards where id = %d" % suspect_card)) > 0)

                duplicate_qa = collection.renderQA([suspect_card])[0]
                
                if html != duplicate_qa['a']:
                    # Add the question part of the HTML
                    united_html += duplicate_qa['a'][len(duplicate_qa['q']):]

            html = united_html

        Ada.recursive = False

        return html

    def UpdateHashes(collection, card_ids):
        """Dynamically update our cache when the user adds/modifies/deletes cards."""

        # _log(u"UpdateHashes (cids = {}, did = {}[{}])".format(str(cids), did, col.decks.get(did)['name']))

        for card_id in card_ids:

            # _log(u"  Processing {} [{}]".format(cid, _get_card_q(col, cid).strip()))

            deck_id = collection.db.scalar("SELECT did FROM cards WHERE id = ?", card_id)

            # Purge from the old location
            if cid in ada.CardID2Hash:
                # _log(u"    QAcache before: {}({})".format(ada.CardID2Hash[cid], str(ada.QAcache[did][ada.CardID2Hash[cid]])))
                # Modified/deleted card has existed, wipe it from our cache

                # If we haven't visited the deck, nothing needs to be done.
                # We'll build an up-to-date cache once the user starts revising it.
                if did not in ada.QAcache:
                    continue

                print("{} {}".format(cid in ada.CardID2Hash, ada.CardID2Hash[cid] in ada.QAcache[did]))

                # Exclude the card from the "old" deck.
                ada.QAcache[did][ada.CardID2Hash[cid]] = [id for id in ada.QAcache[did][ada.CardID2Hash[cid]] if id != cid]

                # _log(u"    QAcache after: {}".format(str(ada.QAcache[did][ada.CardID2Hash[cid]])))

            h = _get_card_q(col, cid)
            if h not in ada.QAcache[new_did]:
                ada.QAcache[new_did][h] = []
            ada.QAcache[new_did][h].append(cid)
            ada.CardID2Hash[cid] = h

    @staticmethod
    def UpdateNoteHashes(self):
        """Dynamic updates of our cache when the user adds/modifies/deletes cards"""
        cards = self.cards();
        if not cards:
            return
        UpdateHashes(self.col, {card.id: card.did for card in cards})

    # When the user adds a card, new cards are not readily available for modification during note.flush().
    # TODO: perhaps updating only cards will suffice?
    @staticmethod
    def UpdateCardHashes(self):
        UpdateHashes(self.col, {self.id: self.did})

    def BrowserCids2Dids(self, cids):
        """Return a list of (cid, did) tuples containing the IDs of each changed card and its respective deck."""
        return dict(zip(cids, (self.mw.col.db.scalar(query, cid) for cid in cids)))

    @staticmethod
    def remove_cards_from_cache(self):
        """Remove cards from cache. Needed when the user moves them to another deck or deletes them."""
        card_ids = self.selectedCards()
        for card_id, deck_id in collection.db.list("SELECT id, did FROM cards WHERE id in {}".format(card_ids)):
            QAcache[deck_id][card_id].remove            
            
    @staticmethod
    def update_after_deck_change(self):
        """Update the plugin's hashes after the deck change."""
        UpdateHashes(self.mw.col, self.selectedCards())

anki.hooks.addHook('mungeQA', Ada.add_dupe_answers);
anki.notes.Note.flush = anki.hooks.wrap(anki.notes.Note.flush, Ada.UpdateNoteHashes, 'after')
anki.cards.Card.flush = anki.hooks.wrap(anki.cards.Card.flush, Ada.UpdateCardHashes, 'after')
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, Ada.remove_cards_from_cache, 'before')
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, Ada.update_after_deck_change, 'after')
# TODO Now I need to handle card deletion
