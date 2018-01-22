# -*- coding: utf-8 -*-

# Show duplicates v0.5
# Show card duplicates for a card below it.

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
# mod = modified?

# DEBUGGING
# Use the debug() call to put breakpoints wherever you need and then
# just run anki from the console

################################################################################

def _get_hash(s):
    return int(hashlib.md5(s.encode('utf8')).hexdigest(), 16)

def _get_card_hash(col, cid):
    return _get_hash(_get_card_q(col, cid))

def _get_card_q(col, cid):
    return anki.utils.stripHTMLMedia(col.renderQA([cid])[0]['q'])

def _get_card_a(col, cid):
    return anki.utils.stripHTMLMedia(col.renderQA([cid])[0]['a'])

# ada = add dupe answers
def ada(html, type, fields, model, data, col):
    # data is [cid, nid, mid, did, ord, tags, flds]

    # TODO add an assertion that the hook is the last one
    # (otherwise something truly horrifying might just happen, but I don't exactly know what)

    # renderQA will re-call this hook when rendering each sub-answer.

    # _log("Ada(recursive={})".format(ada.recursive))

    if ada.recursive:
        return html

    if type == 'q':
        # Questions remain unique, just remember them
        ada.question = anki.utils.stripHTMLMedia( html)
        ada.q_fields = fields
        ada.q_model = model
        ada.q_data = data
        ada.q_col = col
    elif type == 'a':
        # Answers, on the other hand, are not. We'll need to walk through all of them that
        # match the question and merge them into one html to be displayed on the screen.

        ada.recursive = True

        # Check that we are rendering the answers to the card we rememered the question of.
        # This should always be the case.
        assert ( ada.q_fields == fields and
                 ada.q_model == model and
                 ada.q_data == data and
                 ada.q_col == col)

        # Deck ID
        did = data[3]

        # If we haven't built the table for the current deck, do it now.
        # sibaraku omati kudasai
        if did not in ada.QAcache:
            ada.QAcache[did] = {}
            for card_id in col.db.list("select id from cards where did = %d" % did):
                # We need a fast way to find answers by the html rendition of their questions.
                # Creating the hash(question) => {cards} relation with the dictionary should do.
                h = _get_card_hash(col, card_id)
                if h not in ada.QAcache[did]:
                    ada.QAcache[did][h] = []
                ada.QAcache[did][h].append(card_id)

                # assert(card_id not in ada.CardID2Hash)
                # This assertion will trigger if e.g. a card has been moved to
                # another deck. The stale hash entry should cause no harm except
                # maybe a rare scenario when the card will still be shown for the
                # old deck till restart.
                # I could add a hook to _setDeck@browser.py to address it, but I
                # don't have time to verify this will not break something else.
                # TLDR deal with it, at least for now.

                # We also keep the backwards CardID => hash(question) relation needed
                # when we need to dynamically update the main dictionary
                # when the user adds/edits/deletes cards
                ada.CardID2Hash[card_id] = h

        h = _get_hash(ada.question)

        # TODO get rid of this.
        # There are still unexplored cases where we "forget" to rebuild cache.
        if h not in ada.QAcache[did]:
            ada.recursive = False
            return html

        suspect_cards = ada.QAcache[did][h]

        united_html = html

        # Internally render QA for each sub-answer and join them together
        for suspect_card in suspect_cards:
            if len (col.db.list("select id from cards where id = %d" % suspect_card)) == 0:
                # If the card is absent for some reason (e.g. has been deleted), remove it from cache
                ada.QAcache[did][h] = [id for id in ada.QAcache[did][h] if id != suspect_card]
                ada.CardID2Hash.pop(suspect_card, None)
                continue

            suspect_card_qa = col.renderQA([suspect_card])[0]
            if anki.utils.stripHTMLMedia(suspect_card_qa['q']) == ada.question and \
               html != suspect_card_qa['a'] and \
               ada.question.strip() != '': # This line is no longer needed now that we take media file names into account
                # We found a dupe
                united_html += suspect_card_qa['a'][len(suspect_card_qa['q']):]

        html = united_html

    ada.recursive = False

    return html

# Dynamic updates of our cache when the user adds/modifies/deletes cards
# col = collection, cids = card Ids, did = deck ID
def UpdateHashes(col, cids, did, new_did=None):

    if not new_did:
        new_did = did

    # _log(u"UpdateHashes (cids = {}, did = {}[{}])".format(str(cids), did, col.decks.get(did)['name']))
    for cid in cids:
        # _log(u"  Processing {} [{}]".format(cid, _get_card_q(col, cid).strip()))

        # Purge from the old location
        if cid in ada.CardID2Hash:
            # _log(u"    QAcache before: {}({})".format(ada.CardID2Hash[cid], str(ada.QAcache[did][ada.CardID2Hash[cid]])))
            # Modified/deleted card has existed, wipe it from our cache
            ada.QAcache[did][ada.CardID2Hash[cid]] = [id for id in ada.QAcache[did][ada.CardID2Hash[cid]] if id != cid]
            # _log(u"    QAcache after: {}".format(str(ada.QAcache[did][ada.CardID2Hash[cid]])))

        h = _get_card_hash(col, cid)
        if h not in ada.QAcache[new_did]:
            ada.QAcache[new_did][h] = []
        ada.QAcache[new_did][h].append(cid)
        ada.CardID2Hash[cid] = h

# Dynamic updates of our cache when the user adds/modifies/deletes cards
def UpdateNoteHashes(self):
    cards = self.cards();
    if not cards:
        return
    UpdateHashes(self.col, [card.id for card in self.cards()], cards[0].did)

# When the user adds a card, new cards are not readily available for modification during note.flush().
# TODO: perhaps updating only cards will suffice?
def UpdateCardHashes(self):
    UpdateHashes(self.col, [self.id], self.did)

def BrowserCid2Did(self, cid):
    return self.mw.col.db.scalar("select did from cards where id = ?", cid)

def PreUpdateSelectedCardHashes(self):
    cids = self.selectedCards()
    UpdateSelectedCardHashes.old_did = BrowserCid2Did(self, cids[0])

def UpdateSelectedCardHashes(self):
    cids = self.selectedCards()
    old_did = UpdateSelectedCardHashes.old_did
    new_did = BrowserCid2Did(self, cids[0])
    UpdateHashes(self.mw.col, cids, old_did, new_did)
    del UpdateSelectedCardHashes.old_did

ada.QAcache = {}
ada.CardID2Hash = {}
ada.recursive = False

anki.hooks.addHook('mungeQA', ada);
anki.notes.Note.flush = anki.hooks.wrap(anki.notes.Note.flush, UpdateNoteHashes, "after")
anki.cards.Card.flush = anki.hooks.wrap(anki.cards.Card.flush, UpdateCardHashes, "after")
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, PreUpdateSelectedCardHashes, "before") # Deck change, remember old deck
aqt.browser.Browser.setDeck = anki.hooks.wrap(aqt.browser.Browser.setDeck, UpdateSelectedCardHashes, "after") # Deck change, process old & new decks
