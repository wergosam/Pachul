"""
Pachul — ui_qt/theme.py
The look: libadwaita's palette, radii and spacing, on top of Qt's *Fusion*
style, independent of the desktop it runs on.

Why this is built differently from the first KDE port
-----------------------------------------------------
* The old port laid a partial stylesheet over the desktop's native style
  (Breeze on Plasma). Qt then mixes two renderers — QSS-styled widgets next
  to natively drawn ones — and the result looks patchy. Here Fusion is
  forced (it is identical on every desktop and takes its colours purely
  from the QPalette) and the palette itself is the Adwaita palette.
* Everything that matters visually (cards, rows, badges, switches, nav
  rows, banners …) is painted by our own widgets straight from the tokens
  below, not from QSS. QSS is only used for the few stock widgets
  (buttons, entries, scrollbars, menus, tooltips) and is generated from the
  same tokens, so light/dark switching is one code path.
* Light/dark follows the system live (Qt >= 6.5 colour-scheme signal) or
  can be forced; the accent is Adwaita blue or — optionally — the
  desktop's own accent colour (Plasma's accent setting).

Usage::

    app = QApplication(sys.argv)
    theme.install(app, mode="auto", accent="adwaita")
    ...
    theme.T.card_bg            # QColor, always the *current* scheme
    theme.signals.changed      # emitted after every scheme/accent change
"""

import os
import tempfile

from .qt import (Qt, QObject, QColor, QPalette, QApplication, QFont,
                 QFontInfo, Signal)


def rgba(r, g, b, a=1.0):
    return QColor(int(r), int(g), int(b), int(round(a * 255)))


def css(c):
    """QColor -> QSS colour string."""
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


def mix(a, b, t):
    """Blend colour *a* towards *b* by fraction t (0..1)."""
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def with_alpha(c, alpha):
    out = QColor(c)
    out.setAlphaF(alpha)
    return out


class Tokens:
    """All colours of one scheme. Plain attributes, QColor values."""

    dark = False

    def __init__(self, dark):
        self.dark = dark
        if not dark:
            self.window_bg      = QColor("#fafafb")
            self.window_fg      = QColor("#323233")
            self.view_bg        = QColor("#ffffff")
            self.headerbar_bg   = QColor("#ffffff")
            self.sidebar_bg     = QColor("#ebebed")
            self.card_bg        = QColor("#ffffff")
            self.card_border    = rgba(0, 0, 0, 0.12)
            self.popover_bg     = QColor("#ffffff")
            self.border         = rgba(0, 0, 0, 0.12)
            self.separator      = rgba(0, 0, 0, 0.09)
            self.btn_bg         = rgba(0, 0, 0, 0.08)
            self.btn_hover      = rgba(0, 0, 0, 0.12)
            self.btn_active     = rgba(0, 0, 0, 0.18)
            self.entry_bg       = rgba(0, 0, 0, 0.07)
            self.row_hover      = rgba(0, 0, 0, 0.04)
            self.row_active     = rgba(0, 0, 0, 0.08)
            self.switch_off     = rgba(0, 0, 0, 0.17)
            self.shadow         = rgba(0, 0, 0, 0.18)
            self.terminal_bg    = QColor("#f5f5f6")
            self.terminal_fg    = QColor("#2e3436")
            self.success_text   = QColor("#1b8553")
            self.warning_text   = QColor("#905400")
            self.error_text     = QColor("#c30000")
            self.accent_text    = QColor("#1c71d8")
            self.destructive_bg = QColor("#e01b24")
            self.destructive_text = QColor("#c30000")
        else:
            self.window_bg      = QColor("#222226")
            self.window_fg      = QColor("#ffffff")
            self.view_bg        = QColor("#1d1d20")
            self.headerbar_bg   = QColor("#2e2e32")
            self.sidebar_bg     = QColor("#2a2a2e")
            self.card_bg        = QColor("#343437")
            self.card_border    = rgba(0, 0, 0, 0.30)
            self.popover_bg     = QColor("#36363a")
            self.border         = rgba(255, 255, 255, 0.10)
            self.separator      = rgba(255, 255, 255, 0.10)
            self.btn_bg         = rgba(255, 255, 255, 0.10)
            self.btn_hover      = rgba(255, 255, 255, 0.15)
            self.btn_active     = rgba(255, 255, 255, 0.22)
            self.entry_bg       = rgba(255, 255, 255, 0.10)
            self.row_hover      = rgba(255, 255, 255, 0.05)
            self.row_active     = rgba(255, 255, 255, 0.10)
            self.switch_off     = rgba(255, 255, 255, 0.22)
            self.shadow         = rgba(0, 0, 0, 0.45)
            self.terminal_bg    = QColor("#17171a")
            self.terminal_fg    = QColor("#e6e6e6")
            self.success_text   = QColor("#8ff0a4")
            self.warning_text   = QColor("#ffa348")
            self.error_text     = QColor("#ff938c")
            self.accent_text    = QColor("#78aeed")
            self.destructive_bg = QColor("#c01c28")
            self.destructive_text = QColor("#ff938c")

        self.accent_bg = QColor("#3584e4")
        self.accent_fg = QColor("#ffffff")
        self.success_bg = QColor("#2ec27e")
        self.warning_bg = QColor("#e5a50a")
        self.error_bg   = QColor("#e01b24")
        self.destructive_fg = QColor("#ffffff")

    # derived helpers -----------------------------------------------------
    @property
    def dim_fg(self):          # libadwaita .dim-label: 55 % opacity
        return with_alpha(self.window_fg, 0.55)

    @property
    def disabled_fg(self):
        return with_alpha(self.window_fg, 0.35)

    def accent_wash(self, alpha):
        return with_alpha(self.accent_bg, alpha)


class _Signals(QObject):
    changed = Signal()


signals = _Signals()

# The live token set. Widgets read theme.T at paint time, never copy it.
T = Tokens(False)

_state = {"mode": "auto", "accent": "adwaita", "system_dark": False,
          "system_accent": QColor("#3584e4"), "app": None}


# ─── Public API ──────────────────────────────────────────────────────────────

def install(app, mode="auto", accent="adwaita"):
    """Force Fusion + the Adwaita palette on *app*.

    mode   "auto" (follow the system), "light" or "dark"
    accent "adwaita" (blue) or "system" (the desktop's accent colour)
    """
    _state["app"] = app
    _state["mode"] = mode
    _state["accent"] = accent

    # Capture what the desktop says BEFORE we override its palette.
    _state["system_dark"] = _detect_system_dark(app)
    _state["system_accent"] = QColor(app.palette().color(QPalette.ColorRole.Highlight))

    app.setStyle("Fusion")

    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):          # Qt >= 6.5
        hints.colorSchemeChanged.connect(_on_system_scheme_changed)

    _apply()


def set_mode(mode):
    _state["mode"] = mode
    _apply()


def set_accent(accent):
    _state["accent"] = accent
    _apply()


def is_dark():
    return T.dark


def font_px():
    """Pixel height of the application font (for sizes that should scale
    with the user's font setting)."""
    app = _state["app"] or QApplication.instance()
    px = QFontInfo(app.font()).pixelSize()
    return px if px > 0 else 14


# ─── Internals ───────────────────────────────────────────────────────────────

def _detect_system_dark(app):
    hints = app.styleHints()
    if hasattr(hints, "colorScheme"):
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _on_system_scheme_changed(*_):
    app = _state["app"]
    if app is None:
        return
    scheme = app.styleHints().colorScheme()
    if scheme in (Qt.ColorScheme.Dark, Qt.ColorScheme.Light):
        _state["system_dark"] = (scheme == Qt.ColorScheme.Dark)
    if _state["mode"] == "auto":
        _apply()


def _resolve_dark():
    mode = _state["mode"]
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return _state["system_dark"]


def _apply():
    global T
    app = _state["app"]
    dark = _resolve_dark()
    tok = Tokens(dark)

    if _state["accent"] == "system":
        acc = QColor(_state["system_accent"])
        tok.accent_bg = acc
        # readable accent *text*: lighten on dark, darken on light
        tok.accent_text = mix(acc, QColor("#ffffff"), 0.35) if dark \
            else mix(acc, QColor("#000000"), 0.25)
        tok.accent_fg = QColor("#ffffff") if acc.lightness() < 170 \
            else QColor("#1e1e1e")

    # Mutate the existing object in place so that every module holding
    # `theme.T` keeps seeing current values.
    T.__dict__.update(tok.__dict__)

    app.setPalette(_make_palette(T))
    app.setStyleSheet(build_qss(T))
    signals.changed.emit()


def _make_palette(t):
    p = QPalette()
    R, G = QPalette.ColorRole, QPalette.ColorGroup
    solid_btn = mix(t.window_bg, t.window_fg, 0.10)

    roles = {
        R.Window: t.window_bg, R.WindowText: t.window_fg,
        R.Base: t.view_bg, R.AlternateBase: mix(t.view_bg, t.window_fg, 0.04),
        R.Text: t.window_fg, R.Button: solid_btn, R.ButtonText: t.window_fg,
        R.BrightText: QColor("#ffffff"),
        R.Highlight: t.accent_bg, R.HighlightedText: t.accent_fg,
        R.ToolTipBase: t.popover_bg, R.ToolTipText: t.window_fg,
        R.Link: t.accent_text, R.LinkVisited: t.accent_text,
        R.PlaceholderText: with_alpha(t.window_fg, 0.5),
        R.Light: mix(solid_btn, QColor("#ffffff"), 0.5),
        R.Midlight: mix(solid_btn, QColor("#ffffff"), 0.25),
        R.Mid: mix(solid_btn, t.window_fg, 0.25),
        R.Dark: mix(solid_btn, QColor("#000000"), 0.35),
        R.Shadow: QColor("#000000"),
    }
    for role, col in roles.items():
        p.setColor(role, col)

    for role in (R.WindowText, R.Text, R.ButtonText):
        p.setColor(G.Disabled, role, t.disabled_fg)
    p.setColor(G.Disabled, R.Highlight, mix(t.window_bg, t.window_fg, 0.25))
    return p


def _chevron_files(t):
    """Render the combo-box chevron once per scheme into a temp dir
    (QSS can only reference images by file path)."""
    d = os.path.join(tempfile.gettempdir(), f"pachul-qt-{os.getuid()}")
    os.makedirs(d, exist_ok=True)
    col = "#%02x%02x%02x" % (t.window_fg.red(), t.window_fg.green(), t.window_fg.blue())
    path = os.path.join(d, f"chevron-{'dark' if t.dark else 'light'}.svg")
    with open(path, "w") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" '
            'width="16" height="16"><path d="M4 6.2 L8 10 L12 6.2" fill="none" '
            f'stroke="{col}" stroke-width="1.6" stroke-linecap="round" '
            'stroke-linejoin="round" opacity="0.8"/></svg>')
    return path.replace("\\", "/")


def build_qss(t):
    chevron = _chevron_files(t)
    thumb = with_alpha(t.window_fg, 0.30)
    thumb_h = with_alpha(t.window_fg, 0.50)
    suggested_h = mix(t.accent_bg, QColor("#ffffff"), 0.12)
    suggested_a = mix(t.accent_bg, QColor("#000000"), 0.12)
    destr_h = mix(t.destructive_bg, QColor("#ffffff"), 0.12)
    destr_a = mix(t.destructive_bg, QColor("#000000"), 0.12)
    focus = with_alpha(t.accent_bg, 0.55)

    return f"""
QToolTip {{
    background: {css(t.popover_bg)}; color: {css(t.window_fg)};
    border: 1px solid {css(t.border)}; padding: 4px 8px;
}}

/* ── Buttons ── */
QPushButton, QToolButton {{
    background: {css(t.btn_bg)}; color: {css(t.window_fg)};
    border: none; border-radius: 6px;
    padding: 5px 12px; min-height: 24px;
}}
QPushButton:hover, QToolButton:hover   {{ background: {css(t.btn_hover)}; }}
QPushButton:pressed, QToolButton:pressed,
QPushButton:checked, QToolButton:checked {{ background: {css(t.btn_active)}; }}
QPushButton:disabled, QToolButton:disabled {{
    color: {css(t.disabled_fg)}; background: {css(with_alpha(t.btn_bg, 0.04))};
}}
QPushButton:focus, QToolButton:focus {{ outline: none; }}
QToolButton::menu-indicator {{ image: none; }}

QPushButton[kind="suggested"] {{ background: {css(t.accent_bg)}; color: {css(t.accent_fg)}; }}
QPushButton[kind="suggested"]:hover   {{ background: {css(suggested_h)}; }}
QPushButton[kind="suggested"]:pressed {{ background: {css(suggested_a)}; }}
QPushButton[kind="suggested"]:disabled {{ background: {css(with_alpha(t.accent_bg, 0.4))}; color: {css(with_alpha(t.accent_fg, 0.6))}; }}

QPushButton[kind="destructive"] {{ background: {css(t.destructive_bg)}; color: {css(t.destructive_fg)}; }}
QPushButton[kind="destructive"]:hover   {{ background: {css(destr_h)}; }}
QPushButton[kind="destructive"]:pressed {{ background: {css(destr_a)}; }}

QPushButton[kind="flat"], QToolButton[kind="flat"] {{ background: transparent; }}
QPushButton[kind="flat"]:hover, QToolButton[kind="flat"]:hover {{ background: {css(t.btn_bg)}; }}
QPushButton[kind="flat"]:pressed, QToolButton[kind="flat"]:pressed {{ background: {css(t.btn_hover)}; }}

QPushButton[kind="pill"] {{ border-radius: 20px; padding: 8px 26px; min-height: 28px; }}
QToolButton[kind="circular"] {{ border-radius: 17px; padding: 0px; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; }}
QToolButton[kind="icon"] {{ background: transparent; border-radius: 6px; padding: 0px; min-width: 34px; min-height: 34px; }}
QToolButton[kind="icon"]:hover {{ background: {css(t.btn_bg)}; }}
QToolButton[kind="icon"]:pressed {{ background: {css(t.btn_hover)}; }}

/* ── Entries ── */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {css(t.entry_bg)}; color: {css(t.window_fg)};
    border: 2px solid transparent; border-radius: 6px;
    padding: 3px 8px; min-height: 24px;
    selection-background-color: {css(t.accent_bg)};
    selection-color: {css(t.accent_fg)};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {css(focus)}; }}
QLineEdit:disabled {{ color: {css(t.disabled_fg)}; }}

QComboBox {{
    background: {css(t.btn_bg)}; color: {css(t.window_fg)};
    border: none; border-radius: 6px; padding: 4px 10px; min-height: 24px;
}}
QComboBox:hover {{ background: {css(t.btn_hover)}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: {css(t.popover_bg)}; color: {css(t.window_fg)};
    border: 1px solid {css(t.border)}; padding: 4px; outline: none;
    selection-background-color: {css(t.btn_hover)};
    selection-color: {css(t.window_fg)};
}}

/* ── Menus ── */
QMenu {{
    background: {css(t.popover_bg)}; color: {css(t.window_fg)};
    border: 1px solid {css(t.border)}; padding: 4px;
}}
QMenu::item {{ padding: 6px 14px; border-radius: 6px; margin: 1px 0; }}
QMenu::item:selected {{ background: {css(t.btn_hover)}; }}
QMenu::item:disabled {{ color: {css(t.disabled_fg)}; }}
QMenu::separator {{ height: 1px; background: {css(t.separator)}; margin: 4px 6px; }}

/* ── Scroll areas & bars ── */
QScrollArea, QListView, QTreeView {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {css(thumb)}; border-radius: 3px;
    min-height: 32px; margin: 2px 3px;
}}
QScrollBar::handle:vertical:hover {{ background: {css(thumb_h)}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {css(thumb)}; border-radius: 3px;
    min-width: 32px; margin: 3px 2px;
}}
QScrollBar::handle:horizontal:hover {{ background: {css(thumb_h)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ── Misc ── */
QProgressBar {{
    background: {css(with_alpha(t.window_fg, 0.12))};
    border: none; border-radius: 3px; max-height: 6px; min-height: 6px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {css(t.accent_bg)}; border-radius: 3px; }}
QSplitter::handle {{ background: {css(t.border)}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QPlainTextEdit[kind="terminal"], QTextEdit[kind="terminal"] {{
    background: {css(t.terminal_bg)}; color: {css(t.terminal_fg)};
    border: none; border-radius: 8px; padding: 12px 14px;
    font-family: "Cascadia Code","JetBrains Mono","Fira Code","Noto Sans Mono",monospace;
    selection-background-color: {css(t.accent_bg)};
}}
"""


def set_kind(widget, kind):
    """Pick a stylesheet variant: 'suggested', 'destructive', 'flat', 'pill',
    'circular', 'icon', 'terminal'. Call before the widget is shown (or it
    re-polishes itself, which is what this does anyway)."""
    widget.setProperty("kind", kind)
    st = widget.style()
    st.unpolish(widget)
    st.polish(widget)
    widget.update()
