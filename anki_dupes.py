# Show duplicates v0.4
# Show card duplicates for a card below it.

# Changelog
# 0.4: Disable an overly strict assertion triggering if a card is moved to another deck under certain circumstances.
# 0.3: Don't group together non-text cards.
# 0.2: Update cache when the user adds/modifies/deletes cards.
# 0.1: Initial version.

# TODO
# Update timings on the duplicates.

# Contact
# putspamhereplz@gmail.com

import anki, aqt, hashlib
from aqt.qt import debug
from PyQt4.QtCore import pyqtRemoveInputHook
pyqtRemoveInputHook()

# TABLE cards:
# nid = note ID
# did = deck ID
# ord = ordinal wtf?
# mod = modified?

# Use the debug() call to put breakpoints wherever you need

def gethash(s):
    return int(hashlib.md5(s.encode('utf8')).hexdigest(), 16)

# ada = add dupe answers
def ada(html, type, fields, model, data, col):
    # data is [cid, nid, mid, did, ord, tags, flds]

    # TODO add an assertion that the hook is the last one
    # (otherwise something truly horrifying might just happen, but I don't exactly know what)

    # renderQA will re-call this hook when rendering each sub-answer.
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
                h = gethash(anki.utils.stripHTMLMedia(col.renderQA([card_id])[0]['q']))
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

        h = gethash(ada.question)

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
def UpdateNoteHashes(self, mod=None):
    for cid, did in self.col.db.execute("select id, did from cards where nid = ? order by ord", self.id):
        if cid in ada.CardID2Hash:
            # Modified/deleted card has existed, wipe it from our cache
            ada.QAcache[did][ada.CardID2Hash[cid]] = [id for id in ada.QAcache[did][ada.CardID2Hash[cid]] if id != cid]
        h = gethash(anki.utils.stripHTMLMedia(self.col.renderQA([cid])[0]['q']))
        if h not in ada.QAcache[did]:
            ada.QAcache[did][h] = []
        ada.QAcache[did][h].append(cid)
        ada.CardID2Hash[cid] = h
        
# When the user adds a card, new cards are not readily available for modification during note.flush().
# TODO: perhaps updating only cards will suffice?
def UpdateCardHashes(self, mod=None):
    UpdateNoteHashes(self.note(), mod=None)

ada.QAcache = {}
ada.CardID2Hash = {}
ada.recursive = False
anki.hooks.addHook('mungeQA', ada);
anki.notes.Note.flush = anki.hooks.wrap(anki.notes.Note.flush, UpdateNoteHashes, "after")
anki.cards.Card.flush = anki.hooks.wrap(anki.cards.Card.flush, UpdateCardHashes, "after")
from aqt.qt import debug
