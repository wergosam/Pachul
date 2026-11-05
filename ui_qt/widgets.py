"""
Pachul — ui_qt/widgets.py
The libadwaita-style building blocks, drawn directly from theme tokens.

    Adw widget            here
    ───────────────────   ───────────────────────────────────────────────
    PreferencesGroup      Group            (+ Card for the boxed list)
    ActionRow             Row
    SwitchRow             SwitchRow        (+ Switch)
    ComboRow              ComboRow
    EntryRow              EntryRow
    ExpanderRow           ExpanderRow
    StatusPage            StatusPage
    Banner                Banner
    Toast / ToastOverlay  ToastOverlay
    HeaderBar             HeaderBar
    PreferencesPage       PreferencesPage
    (Pachul specific)     Pill, NavRow, StatCard, Label, IconButton

Nothing here reads a stylesheet for its own looks: colours come from
theme.T at paint time, so a light/dark/accent change is just a repaint.
"""

from .qt import (
    Qt, QRectF, QPointF, QSize, QTimer, QEvent, QObject, QPropertyAnimation,
    QEasingCurve, QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QGridLayout, QPushButton, QToolButton, QComboBox, QLineEdit, QScrollArea,
    QAbstractButton, QSizePolicy, QDialog, QPainter, QPainterPath, QPen,
    QColor, QFont, QFontMetrics, QPalette, QApplication, Signal, Property,
)
from . import theme
from .icons_qt import IconLabel, icon as qicon

CARD_RADIUS = 12


# ─── helpers ─────────────────────────────────────────────────────────────────

def rounded_path(rect, tl=0.0, tr=0.0, br=0.0, bl=0.0):
    """Rectangle path with an individual radius per corner."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    p = QPainterPath()
    p.moveTo(x + tl, y)
    p.lineTo(x + w - tr, y)
    if tr:
        p.arcTo(x + w - 2 * tr, y, 2 * tr, 2 * tr, 90, -90)
    p.lineTo(x + w, y + h - br)
    if br:
        p.arcTo(x + w - 2 * br, y + h - 2 * br, 2 * br, 2 * br, 0, -90)
    p.lineTo(x + bl, y + h)
    if bl:
        p.arcTo(x, y + h - 2 * bl, 2 * bl, 2 * bl, 270, -90)
    p.lineTo(x, y + tl)
    if tl:
        p.arcTo(x, y, 2 * tl, 2 * tl, 180, -90)
    p.closeSubpath()
    return p


def _corner_radii(position, r):
    top = r if position in ("first", "only") else 0
    bottom = r if position in ("last", "only") else 0
    return top, top, bottom, bottom           # tl, tr, br, bl


def _scaled_font(base, scale=1.0, weight=None):
    f = QFont(base)
    if f.pointSizeF() > 0:
        f.setPointSizeF(f.pointSizeF() * scale)
    elif f.pixelSize() > 0:
        f.setPixelSize(max(6, int(round(f.pixelSize() * scale))))
    if weight is not None:
        f.setWeight(weight)
    return f


def _repolish(w):
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


# ─── Label ───────────────────────────────────────────────────────────────────

class Label(QLabel):
    """QLabel with libadwaita's text roles.

    roles: normal, dim, subtitle, heading, caption, title-1 … title-4,
           accent, success, warning, error, nav, section
    """

    _STYLE = {
        # role: (scale, weight, colour-key, alpha)
        "normal":   (1.00, None, "window_fg", None),
        "dim":      (1.00, None, "window_fg", 0.55),
        "subtitle": (0.88, None, "window_fg", 0.55),
        "heading":  (1.00, QFont.Weight.Bold, "window_fg", None),
        "caption":  (0.82, None, "window_fg", None),
        "title-1":  (1.80, QFont.Weight.ExtraBold, "window_fg", None),
        "title-2":  (1.36, QFont.Weight.ExtraBold, "window_fg", None),
        "title-3":  (1.20, QFont.Weight.ExtraBold, "window_fg", None),
        "title-4":  (1.08, QFont.Weight.ExtraBold, "window_fg", None),
        "accent":   (1.00, None, "accent_text", None),
        "success":  (1.00, None, "success_text", None),
        "warning":  (1.00, None, "warning_text", None),
        "error":    (1.00, None, "error_text", None),
        "nav":      (0.97, QFont.Weight.DemiBold, "window_fg", None),
        "section":  (0.82, QFont.Weight.ExtraBold, "window_fg", 0.50),
    }

    def __init__(self, text="", role="normal", wrap=False, parent=None):
        super().__init__(text, parent)
        self._role = role
        self.setWordWrap(wrap)
        scale, weight, _, _ = self._STYLE.get(role, self._STYLE["normal"])
        if scale != 1.0 or weight is not None:
            self.setFont(_scaled_font(self.font(), scale, weight))
        theme.signals.changed.connect(self._apply_color)
        self._apply_color()

    def set_role(self, role):
        self._role = role
        scale, weight, _, _ = self._STYLE.get(role, self._STYLE["normal"])
        self.setFont(_scaled_font(QApplication.font(), scale, weight))
        self._apply_color()

    def _apply_color(self):
        _, _, key, alpha = self._STYLE.get(self._role, self._STYLE["normal"])
        col = QColor(getattr(theme.T, key))
        if alpha is not None:
            col.setAlphaF(alpha)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.WindowText, col)
        self.setPalette(pal)


# ─── Buttons ─────────────────────────────────────────────────────────────────

def button(text, kind=None, icon_name=None):
    """QPushButton in one of the stylesheet variants (see theme.set_kind)."""
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        b.setIcon(qicon(icon_name, 16, _fg_for_kind(kind)))
        b.setIconSize(QSize(16, 16))
    if kind:
        theme.set_kind(b, kind)
    return b


def _fg_for_kind(kind):
    t = theme.T
    if kind == "suggested":
        return t.accent_fg
    if kind == "destructive":
        return t.destructive_fg
    return t.window_fg


class IconButton(QToolButton):
    """Flat 34×34 icon-only button that re-colours itself with the theme."""

    def __init__(self, name, tooltip="", size=18, parent=None):
        super().__init__(parent)
        self._name, self._size = name, size
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setIconSize(QSize(size, size))
        theme.set_kind(self, "icon")
        theme.signals.changed.connect(self._refresh)
        self._refresh()

    def set_icon(self, name):
        self._name = name
        self._refresh()

    def _refresh(self):
        self.setIcon(qicon(self._name, self._size, theme.T.window_fg))


class TextIconButton(QToolButton):
    """Flat header-bar button: icon + text (e.g. 'Tools')."""

    def __init__(self, name, text, parent=None):
        super().__init__(parent)
        self._name = name
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(18, 18))
        theme.set_kind(self, "flat")
        theme.signals.changed.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        self.setIcon(qicon(self._name, 18, theme.T.window_fg))


# ─── Card / Row / Group ──────────────────────────────────────────────────────

class Card(QFrame):
    """Rounded 'card' surface. Draws consecutive row children separated by
    hairlines (libadwaita's boxed-list)."""

    def __init__(self, parent=None, separators=True):
        super().__init__(parent)
        self._separators = separators
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        theme.signals.changed.connect(self.update)

    def paintEvent(self, _e):
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(r, CARD_RADIUS, CARD_RADIUS, CARD_RADIUS, CARD_RADIUS)
        p.fillPath(path, t.card_bg)
        p.setPen(QPen(t.card_border, 1))
        p.drawPath(path)

        if self._separators:
            rows = [c for c in self.children()
                    if isinstance(c, QWidget) and getattr(c, "is_row", False)
                    and not c.isHidden()]
            rows.sort(key=lambda c: c.y())
            for c in rows[1:]:
                p.fillRect(QRectF(1, c.y(), self.width() - 2, 1), t.separator)


class Row(QWidget):
    """Adw.ActionRow: [prefix] title / subtitle [suffix]."""

    is_row = True
    activated = Signal()

    def __init__(self, title="", subtitle="", icon_name=None,
                 activatable=False, parent=None):
        super().__init__(parent)
        self.position = "only"
        self._hover = self._pressed = self._kb_focus = False
        self._activatable = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(12)

        self._prefix = QHBoxLayout()
        self._prefix.setSpacing(10)
        lay.addLayout(self._prefix)

        col = QVBoxLayout()
        col.setSpacing(1)
        col.setContentsMargins(0, 0, 0, 0)
        self.title_label = Label(title, "normal", wrap=True)
        self.subtitle_label = Label(subtitle, "subtitle", wrap=True)
        self.subtitle_label.setVisible(bool(subtitle))
        col.addStretch(1)
        col.addWidget(self.title_label)
        col.addWidget(self.subtitle_label)
        col.addStretch(1)
        lay.addLayout(col, 1)

        self._suffix = QHBoxLayout()
        self._suffix.setSpacing(8)
        lay.addLayout(self._suffix)

        if icon_name:
            self.add_prefix(IconLabel(icon_name, 20, "fg"))

        self.setMinimumHeight(52)
        self.set_activatable(activatable)
        theme.signals.changed.connect(self.update)

    # -- API -----------------------------------------------------------------
    def add_prefix(self, w):
        self._prefix.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)

    def add_suffix(self, w):
        self._suffix.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_title(self, text):
        self.title_label.setText(text)

    def set_subtitle(self, text):
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def set_activatable(self, on):
        self._activatable = on
        self.setCursor(Qt.CursorShape.PointingHandCursor if on
                       else Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if on
                            else Qt.FocusPolicy.NoFocus)
        self.update()

    def set_position(self, pos):
        if pos != self.position:
            self.position = pos
            self.update()

    # -- painting ------------------------------------------------------------
    def paintEvent(self, _e):
        if not self._activatable:
            return
        show_focus = self.hasFocus() and self._kb_focus
        if not (self._hover or self._pressed or show_focus):
            return
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        if self.position not in ("first", "only"):
            r.adjust(0, 1, 0, 0)           # keep the hairline above visible
        radii = _corner_radii(self.position, CARD_RADIUS - 1)
        path = rounded_path(r, *radii)
        p.fillPath(path, t.row_active if self._pressed else t.row_hover)
        if show_focus:
            ring = QColor(t.accent_bg)
            ring.setAlphaF(0.6)
            p.setPen(QPen(ring, 2))
            p.drawPath(rounded_path(r.adjusted(1.5, 1.5, -1.5, -1.5),
                                    *[max(0, x - 1.5) for x in radii]))

    # -- interaction ---------------------------------------------------------
    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = self._pressed = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if self._activatable and e.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._kb_focus = False
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        was = self._pressed
        self._pressed = False
        self.update()
        if (self._activatable and was and e.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(e.position().toPoint())):
            self.activated.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if self._activatable and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter,
                                             Qt.Key.Key_Space):
            self.activated.emit()
            return
        super().keyPressEvent(e)

    def focusInEvent(self, e):
        self._kb_focus = e.reason() in (Qt.FocusReason.TabFocusReason,
                                        Qt.FocusReason.BacktabFocusReason)
        self.update()
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        self._kb_focus = False
        self.update()
        super().focusOutEvent(e)


class Group(QWidget):
    """Adw.PreferencesGroup: heading + optional description + boxed list."""

    def __init__(self, title="", description="", parent=None):
        super().__init__(parent)
        self._rows = []
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self._header = QWidget()
        h = QHBoxLayout(self._header)
        h.setContentsMargins(2, 0, 2, 0)
        left = QVBoxLayout()
        left.setSpacing(3)
        self._title = Label(title, "heading", wrap=True)
        self._desc = Label(description, "dim", wrap=True)
        left.addWidget(self._title)
        left.addWidget(self._desc)
        h.addLayout(left, 1)
        self._header_suffix = QHBoxLayout()
        h.addLayout(self._header_suffix)
        v.addWidget(self._header)

        self.card = Card()
        self._card_lay = QVBoxLayout(self.card)
        self._card_lay.setContentsMargins(1, 1, 1, 1)
        self._card_lay.setSpacing(0)
        v.addWidget(self.card)
        self._sync_header()

    def _sync_header(self):
        self._title.setVisible(bool(self._title.text()))
        self._desc.setVisible(bool(self._desc.text()))
        self._header.setVisible(bool(self._title.text() or self._desc.text()))

    def set_title(self, text):
        self._title.setText(text)
        self._sync_header()

    def set_description(self, text):
        self._desc.setText(text)
        self._sync_header()

    def add_header_suffix(self, w):
        self._header_suffix.addWidget(w, 0, Qt.AlignmentFlag.AlignTop)

    def add(self, row):
        self._card_lay.addWidget(row)
        self._rows.append(row)
        if hasattr(row, "layout_changed"):
            row.layout_changed.connect(self.refresh)
        self.refresh()
        return row

    def refresh(self):
        vis = [r for r in self._rows if not r.isHidden()]
        for i, r in enumerate(vis):
            if len(vis) == 1:
                pos = "only"
            elif i == 0:
                pos = "first"
            elif i == len(vis) - 1:
                pos = "last"
            else:
                pos = "middle"
            r.set_position(pos)
        self.card.update()

    def set_row_visible(self, row, visible):
        row.setVisible(visible)
        self.refresh()


# ─── Switch & friends ────────────────────────────────────────────────────────

class Switch(QAbstractButton):
    """Animated toggle in Adwaita's shape (46×26)."""

    def __init__(self, active=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(active)
        self._offset = 1.0 if active else 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)
        theme.signals.changed.connect(self.update)

    def sizeHint(self):
        return QSize(46, 26)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, v):
        self._offset = v
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _e):
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        track = theme.mix(t.switch_off, t.accent_bg, self._offset)
        if not self.isEnabled():
            track.setAlphaF(track.alphaF() * 0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)

        d = h - 6
        x = 3 + self._offset * (w - d - 6)
        p.setBrush(QColor(0, 0, 0, 55))
        p.drawEllipse(QRectF(x, 3 + 1, d, d))               # soft shadow
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 3, d, d))

        if self.hasFocus() and self.property("_kb"):
            ring = QColor(t.accent_bg)
            ring.setAlphaF(0.6)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(ring, 2))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), h / 2, h / 2)

    def focusInEvent(self, e):
        self.setProperty("_kb", e.reason() in (Qt.FocusReason.TabFocusReason,
                                               Qt.FocusReason.BacktabFocusReason))
        super().focusInEvent(e)


class SwitchRow(Row):
    toggled = Signal(bool)

    def __init__(self, title, subtitle="", active=False, icon_name=None, parent=None):
        super().__init__(title, subtitle, icon_name, activatable=True, parent=parent)
        self.switch = Switch(active)
        self.add_suffix(self.switch)
        self.switch.toggled.connect(self.toggled)
        self.activated.connect(self.switch.toggle)

    def is_active(self):
        return self.switch.isChecked()

    def set_active(self, on):
        self.switch.setChecked(on)


class ComboRow(Row):
    changed = Signal(int)

    def __init__(self, title, subtitle="", items=(), icon_name=None, parent=None):
        super().__init__(title, subtitle, icon_name, parent=parent)
        self.combo = QComboBox()
        self.combo.addItems(list(items))
        self.combo.setMinimumWidth(150)
        self.add_suffix(self.combo)
        self.combo.currentIndexChanged.connect(self.changed)


class EntryRow(Row):
    def __init__(self, title, text="", placeholder="", icon_name=None, parent=None):
        super().__init__(title, "", icon_name, parent=parent)
        self.entry = QLineEdit(text)
        self.entry.setPlaceholderText(placeholder)
        self.entry.setMinimumWidth(220)
        self.add_suffix(self.entry)


class ExpanderRow(QWidget):
    """Adw.ExpanderRow: a header row that reveals nested rows."""

    is_row = True
    layout_changed = Signal()

    def __init__(self, title, subtitle="", icon_name=None, expanded=False, parent=None):
        super().__init__(parent)
        self.position = "only"
        self._expanded = False
        self._sub = []

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.header = Row(title, subtitle, icon_name, activatable=True)
        self._chev = IconLabel("go-next-symbolic", 16, "dim")
        self.header.add_suffix(self._chev)
        self.header.activated.connect(self.toggle)
        v.addWidget(self.header)

        self.body = QWidget()
        bl = QVBoxLayout(self.body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        self._body_lay = bl
        v.addWidget(self.body)
        self.body.hide()

        theme.signals.changed.connect(self.update)
        if expanded:
            self.set_expanded(True)

    def add_row(self, row):
        self._sub.append(row)
        self._body_lay.addWidget(row)
        self._apply_positions()

    def is_expanded(self):
        return self._expanded

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, on):
        self._expanded = on
        self.body.setVisible(on)
        self._chev.set_icon("pan-down-symbolic" if on else "go-next-symbolic")
        self._apply_positions()
        self.layout_changed.emit()
        self.update()

    def set_position(self, pos):
        self.position = pos
        self._apply_positions()

    def _apply_positions(self):
        pos = self.position
        if not self._expanded:
            self.header.set_position(pos)
            return
        self.header.set_position("first" if pos in ("first", "only") else "middle")
        n = len(self._sub)
        for i, r in enumerate(self._sub):
            last = (i == n - 1) and pos in ("last", "only")
            r.set_position("last" if last else "middle")

    def paintEvent(self, _e):
        if not self._expanded:
            return
        t = theme.T
        p = QPainter(self)
        tint = QColor(t.window_fg)
        tint.setAlphaF(0.035)
        p.fillRect(self.body.geometry(), tint)
        by = self.body.y()
        p.fillRect(QRectF(0, by, self.width(), 1), t.separator)
        for r in self._sub[1:]:
            if not r.isHidden():
                p.fillRect(QRectF(0, by + r.y(), self.width(), 1), t.separator)


# ─── Pills / badges ──────────────────────────────────────────────────────────

# tone: (r, g, b) wash colour, text colour on light
_TONES = {
    "core":      ((53, 132, 228),  "#3584e4"),
    "extra":     ((46, 194, 126),  "#26a269"),
    "aur":       ((145, 65, 172),  "#9141ac"),
    "multilib":  ((229, 165, 10),  "#c38600"),
    "foreign":   ((230, 97, 0),    "#e66100"),
    "flatpak":   ((74, 144, 217),  "#3d80c9"),
    "snap":      ((233, 84, 32),   "#e95420"),
    "chaotic":   ((23, 182, 167),  "#12968a"),
    "installed": ((46, 194, 126),  "#26a269"),
    "update":    ((229, 165, 10),  "#c38600"),
    "available": ((53, 132, 228),  "#3584e4"),
    "neutral":   (None, None),
}
_TONES["chaotic-aur"] = _TONES["chaotic"]
_TONES["local"] = _TONES["neutral"]


def pill_font(base, small=False):
    return _scaled_font(base, 0.72 if small else 0.80,
                        QFont.Weight.ExtraBold if small else QFont.Weight.Bold)


def pill_size(text, font, small=False):
    fm = QFontMetrics(font)
    padx = 6 if small else 9
    pady = 1 if small else 2
    return QSize(max(fm.horizontalAdvance(text) + 2 * padx + 2, fm.height() + 2 * pady + 4),
                 fm.height() + 2 * pady + 2)


def draw_pill(p, rect, text, tone, font):
    """Paint one badge into *rect* (QRectF) on painter *p*. Used by the Pill
    widget and by list delegates (which can't host real widgets)."""
    t = theme.T
    rgb, text_hex = _TONES.get(tone, _TONES["neutral"])
    if rgb is None:
        wash = QColor(t.window_fg); wash.setAlphaF(0.10)
        fg = QColor(t.window_fg); fg.setAlphaF(0.60)
    else:
        wash = QColor(*rgb); wash.setAlphaF(0.18)
        fg = QColor(text_hex)
        if t.dark:
            fg = theme.mix(fg, QColor("#ffffff"), 0.38)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(wash)
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    p.setPen(fg)
    p.setFont(font)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    p.restore()


class Pill(QWidget):
    """Small rounded badge ('core', 'AUR', 'UPDATE', counts …)."""

    def __init__(self, text, tone="neutral", small=False, parent=None):
        super().__init__(parent)
        self._text, self._tone, self._small = text, tone, small
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._font = pill_font(self.font(), small)
        theme.signals.changed.connect(self.update)

    def set_text(self, text):
        self._text = text
        self.updateGeometry()
        self.update()

    def set_tone(self, tone):
        self._tone = tone
        self.update()

    def sizeHint(self):
        return pill_size(self._text, self._font, self._small)

    def paintEvent(self, _e):
        p = QPainter(self)
        draw_pill(p, QRectF(self.rect()), self._text, self._tone, self._font)


# ─── Sidebar ─────────────────────────────────────────────────────────────────

class NavRow(QWidget):
    clicked = Signal()

    def __init__(self, icon_name, label, count=None, count_tone="neutral", parent=None):
        super().__init__(parent)
        self._hover = False
        self._selected = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 7, 16, 7)       # 6/1 outer margin + 10/6 inner
        lay.setSpacing(10)
        lay.addWidget(IconLabel(icon_name, 18, "dim"))
        self.label = Label(label, "nav")
        lay.addWidget(self.label, 1)
        self.count = None
        if count is not None:
            self.count = Pill(str(count), count_tone, small=True)
            self.count.setVisible(bool(count))
            lay.addWidget(self.count)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.signals.changed.connect(self.update)

    def set_count(self, n):
        if self.count:
            self.count.set_text(str(n))
            self.count.setVisible(n > 0)

    def set_selected(self, on):
        self._selected = on
        self.update()

    def paintEvent(self, _e):
        if not (self._selected or self._hover):
            return
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(6, 1, -6, -1)
        col = t.accent_wash(0.16) if self._selected else t.row_hover
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(r, 8, 8)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class StatCard(QFrame):
    """Tinted number card at the top of the sidebar."""

    def __init__(self, number, caption, tone="accent", parent=None):
        super().__init__(parent)
        self._tone = tone
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 10, 6, 10)
        v.setSpacing(0)
        self.number = Label(str(number), "title-2")
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number.setFont(_scaled_font(self.font(), 1.55, QFont.Weight.Black))
        self.caption = Label(caption.upper(), "section")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.number)
        v.addWidget(self.caption)
        theme.signals.changed.connect(self.update)

    def set_number(self, n):
        self.number.setText(str(n))

    def _color(self):
        t = theme.T
        return {"accent": t.accent_bg, "aur": QColor(145, 65, 172),
                "updates": QColor(229, 165, 10)}.get(self._tone, t.accent_bg)

    def paintEvent(self, _e):
        c = self._color()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(theme.with_alpha(c, 0.08))
        p.setPen(QPen(theme.with_alpha(c, 0.20), 1))
        p.drawRoundedRect(r, CARD_RADIUS, CARD_RADIUS)


class Panel(QWidget):
    """Flat coloured surface: 'sidebar', 'view', 'window' or 'headerbar',
    with an optional hairline on one edge ('right', 'bottom', None)."""

    def __init__(self, surface="window", edge=None, parent=None):
        super().__init__(parent)
        self._surface, self._edge = surface, edge
        theme.signals.changed.connect(self.update)

    def paintEvent(self, _e):
        t = theme.T
        col = getattr(t, {"sidebar": "sidebar_bg", "view": "view_bg",
                          "window": "window_bg", "headerbar": "headerbar_bg"}
                      .get(self._surface, "window_bg"))
        p = QPainter(self)
        p.fillRect(self.rect(), col)
        if self._edge == "right":
            p.fillRect(QRectF(self.width() - 1, 0, 1, self.height()), t.border)
        elif self._edge == "bottom":
            p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), t.border)
        elif self._edge == "left":
            p.fillRect(QRectF(0, 0, 1, self.height()), t.border)
        elif self._edge == "top":
            p.fillRect(QRectF(0, 0, self.width(), 1), t.border)


# ─── Header bar ──────────────────────────────────────────────────────────────

class HeaderBar(Panel):
    """47 px bar with start / (title) / end slots. With a native window
    frame, leave the title empty to avoid showing it twice."""

    def __init__(self, title="", flat=False, parent=None):
        super().__init__("window" if flat else "headerbar",
                         None if flat else "bottom", parent)
        self.setFixedHeight(47)
        g = QGridLayout(self)
        g.setContentsMargins(8, 0, 8, 0)
        g.setSpacing(6)
        self._start = QHBoxLayout(); self._start.setSpacing(4)
        self._end = QHBoxLayout();   self._end.setSpacing(4)
        self._title = Label(title, "heading")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g.addLayout(self._start, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        g.addWidget(self._title, 0, 1, Qt.AlignmentFlag.AlignCenter)
        g.addLayout(self._end, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(2, 1)
        self._title.setVisible(bool(title))

    def set_title(self, text):
        self._title.setText(text)
        self._title.setVisible(bool(text))

    def pack_start(self, w):
        self._start.addWidget(w)

    def pack_end(self, w):
        self._end.addWidget(w)


# ─── Status page / banner / toast ────────────────────────────────────────────

class StatusPage(QWidget):
    def __init__(self, icon_name, title, description="", parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 24, 32, 24)
        v.setSpacing(10)
        v.addStretch(1)
        ic = IconLabel(icon_name, 88, "dim")
        v.addWidget(ic, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(8)
        self.title = Label(title, "title-2", wrap=True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.title)
        self.description = Label(description, "dim", wrap=True)
        self.description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description.setVisible(bool(description))
        v.addWidget(self.description)
        self._actions = QVBoxLayout()
        self._actions.setSpacing(8)
        v.addLayout(self._actions)
        v.addStretch(2)

    def add_action(self, w):
        self._actions.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)


class Banner(QWidget):
    """Full-width message bar with one action button."""

    clicked = Signal()

    def __init__(self, text="", button_label="", tone="accent", parent=None):
        super().__init__(parent)
        self._tone = tone
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 8, 10, 8)
        h.setSpacing(12)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        h.addWidget(self.label, 1)
        self.button = QPushButton(button_label)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setVisible(bool(button_label))
        self.button.clicked.connect(self.clicked)
        h.addWidget(self.button)
        theme.signals.changed.connect(self._restyle)
        self._restyle()

    def set_revealed(self, on):
        self.setVisible(on)

    def _bg_fg(self):
        t = theme.T
        return {
            "accent":  (t.accent_bg, t.accent_fg),
            "warning": (t.warning_bg, QColor("#1e1e1e")),
            "error":   (t.error_bg, QColor("#ffffff")),
            "success": (t.success_bg, QColor("#1e1e1e")),
        }.get(self._tone, (t.accent_bg, t.accent_fg))

    def _restyle(self):
        bg, fg = self._bg_fg()
        pal = self.label.palette()
        pal.setColor(QPalette.ColorRole.WindowText, fg)
        self.label.setPalette(pal)
        wash = "rgba(255,255,255,45)" if fg.lightness() > 128 else "rgba(0,0,0,30)"
        self.button.setStyleSheet(
            f"QPushButton {{ background: {wash}; color: {fg.name()};"
            f" border: none; border-radius: 6px; padding: 4px 14px; min-height: 22px; }}"
            f"QPushButton:hover {{ background: "
            f"{'rgba(255,255,255,70)' if fg.lightness() > 128 else 'rgba(0,0,0,50)'}; }}")
        self.update()

    def paintEvent(self, _e):
        bg, _ = self._bg_fg()
        QPainter(self).fillRect(self.rect(), bg)


class _ToastWidget(QWidget):
    def __init__(self, text, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._text = text
        self._font = _scaled_font(self.font(), 1.0, QFont.Weight.DemiBold)
        fm = QFontMetrics(self._font)
        self.resize(min(parent.width() - 40, fm.horizontalAdvance(text) + 44),
                    fm.height() + 24)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(30, 30, 33, 235))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(QColor("#ffffff"))
        p.setFont(self._font)
        p.drawText(r.adjusted(18, 0, -18, 0),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, self._text)


class ToastOverlay(QObject):
    """Adw.ToastOverlay equivalent: floats a short message over *host*."""

    def __init__(self, host):
        super().__init__(host)
        self._host = host
        self._toast = None
        host.installEventFilter(self)

    def show_toast(self, text, timeout_ms=3000):
        if self._toast is not None:
            self._toast.deleteLater()
        self._toast = _ToastWidget(text, self._host)
        self._place()
        self._toast.show()
        self._toast.raise_()
        t = self._toast
        QTimer.singleShot(timeout_ms, lambda: self._dismiss(t))

    def _dismiss(self, toast):
        if toast is self._toast:
            self._toast = None
        toast.deleteLater()

    def _place(self):
        if self._toast is not None:
            w = self._toast
            w.move((self._host.width() - w.width()) // 2,
                   self._host.height() - w.height() - 28)

    def eventFilter(self, obj, ev):
        if obj is self._host and ev.type() == QEvent.Type.Resize:
            self._place()
        return False


# ─── Pages & dialogs ─────────────────────────────────────────────────────────

class PreferencesPage(QScrollArea):
    """Scrolling column of groups, clamped to 640 px and centred."""

    def __init__(self, max_width=640, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)

        inner = QWidget()
        outer = QHBoxLayout(inner)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        self.column = QWidget()
        self.column.setMaximumWidth(max_width)
        self._lay = QVBoxLayout(self.column)
        self._lay.setContentsMargins(16, 20, 16, 28)
        self._lay.setSpacing(24)
        outer.addWidget(self.column, 100)
        outer.addStretch(1)
        self._lay.addStretch(1)
        self.setWidget(inner)

    def add(self, w):
        self._lay.insertWidget(self._lay.count() - 1, w)
        return w


class Dialog(QDialog):
    """Modal window: top toolbar (no duplicate title — the window frame has
    it) plus a content slot."""

    def __init__(self, parent, title, width=560, height=640):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(width, height)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.header = HeaderBar(flat=True)
        v.addWidget(self.header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        v.addLayout(self.body, 1)

    def set_content(self, w):
        self.body.addWidget(w)


# ─── small extras ────────────────────────────────────────────────────────────

class ElidedLabel(Label):
    """Single-line label that shows '…' instead of forcing the layout wider."""

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        txt = QFontMetrics(self.font()).elidedText(
            self.text(), Qt.TextElideMode.ElideRight, self.width())
        p.drawText(self.rect(),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)


class Separator(QWidget):
    """1 px horizontal hairline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        theme.signals.changed.connect(self.update)

    def paintEvent(self, _e):
        QPainter(self).fillRect(self.rect(), theme.T.separator)
