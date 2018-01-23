# Disable the delete key in reviews.

import aqt
aqt.mw.disconnect(aqt.mw.reviewer.delShortcut, aqt.qt.SIGNAL("activated()"), aqt.mw.reviewer.onDelete)
