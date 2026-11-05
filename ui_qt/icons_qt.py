"""
Pachul — ui_qt/icons_qt.py
Renders the app's inline SVG icons (icon_data.ICON_SVGS) to pixmaps in any
colour and at the screen's device-pixel ratio, so they are crisp on HiDPI
and never depend on the desktop's icon theme (same idea as icons.py).
"""

from functools import lru_cache

from .qt import (QByteArray, QPixmap, QPainter, QSvgRenderer, QColor, QLabel,
                 QGuiApplication, Qt, QSize, QIcon)
from . import theme
from .icon_data import ICON_SVGS

# Extra glyphs that the icon set doesn't ship (chevrons, check mark).
_CHEVRON_RIGHT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" '
    'height="16"><path d="M6 3.5 L10.5 8 L6 12.5" fill="none" '
    'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>')
_CHEVRON_DOWN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" '
    'height="16"><path d="M3.5 6 L8 10.5 L12.5 6" fill="none" '
    'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>')
_CHECK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" '
    'height="16"><path d="M3 8.5 L6.5 12 L13 4.5" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>')

_MOON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" '
    'height="16"><path d="M13.6 9.6 A6 6 0 1 1 6.4 2.4 A4.8 4.8 0 0 0 13.6 9.6 Z" '
    'fill="currentColor"/></svg>')
_SUN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" '
    'height="16"><circle cx="8" cy="8" r="3" fill="currentColor"/>'
    '<g stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
    '<line x1="8" y1="1.2" x2="8" y2="3"/><line x1="8" y1="13" x2="8" y2="14.8"/>'
    '<line x1="1.2" y1="8" x2="3" y2="8"/><line x1="13" y1="8" x2="14.8" y2="8"/>'
    '<line x1="3.2" y1="3.2" x2="4.5" y2="4.5"/><line x1="11.5" y1="11.5" x2="12.8" y2="12.8"/>'
    '<line x1="3.2" y1="12.8" x2="4.5" y2="11.5"/><line x1="11.5" y1="4.5" x2="12.8" y2="3.2"/>'
    '</g></svg>')

_EXTRA = {
    "weather-clear-night-symbolic": _MOON,
    "weather-clear-symbolic": _SUN,
    "go-next-symbolic": _CHEVRON_RIGHT,
    "pan-down-symbolic": _CHEVRON_DOWN,
    "object-select-symbolic": _CHECK,
}


def _hex(c):
    return "#%02x%02x%02x" % (c.red(), c.green(), c.blue())


def _dpr():
    scr = QGuiApplication.primaryScreen()
    return scr.devicePixelRatio() if scr else 1.0


@lru_cache(maxsize=1024)
def _render(name, size, color_hex, dpr):
    svg = _EXTRA.get(name) or ICON_SVGS.get(name)
    if svg is None:
        return None
    data = QByteArray(svg.replace("currentColor", color_hex).encode("utf-8"))
    renderer = QSvgRenderer(data)
    px = int(round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def pixmap(name, size=18, color=None, alpha=None):
    """Pixmap of icon *name*. *color* is a QColor (default: window text);
    *alpha* (0..1) is applied on top, e.g. 0.55 for a dimmed icon."""
    c = QColor(color) if color is not None else QColor(theme.T.window_fg)
    if alpha is not None:
        c.setAlphaF(alpha)
    # QSS-free alpha: SVG fill-opacity would need markup surgery, so bake
    # the alpha by pre-blending against nothing — render opaque, then fade.
    pm = _render(name, size, _hex(c), _dpr())
    if pm is None:
        return QPixmap()
    if alpha is not None and alpha < 1.0:
        faded = QPixmap(pm.size())
        faded.setDevicePixelRatio(pm.devicePixelRatio())
        faded.fill(Qt.GlobalColor.transparent)
        p = QPainter(faded)
        p.setOpacity(alpha)
        p.drawPixmap(0, 0, pm)
        p.end()
        return faded
    return pm


def icon(name, size=18, color=None):
    return QIcon(pixmap(name, size, color))


class IconLabel(QLabel):
    """A QLabel showing a themed icon that re-colours itself whenever the
    light/dark scheme or accent changes.

    role: 'fg' (normal text colour), 'dim' (55 %), 'accent', 'success',
          'warning', 'error', or an explicit QColor.
    """

    def __init__(self, name, size=18, role="fg", parent=None):
        super().__init__(parent)
        self._name, self._size, self._role = name, size, role
        self.setFixedSize(QSize(size, size))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme.signals.changed.connect(self._refresh)
        self._refresh()

    def set_icon(self, name):
        self._name = name
        self._refresh()

    def set_role(self, role):
        self._role = role
        self._refresh()

    def _color_alpha(self):
        t, r = theme.T, self._role
        if isinstance(r, QColor):
            return r, None
        return {
            "fg": (t.window_fg, None), "dim": (t.window_fg, 0.55),
            "accent": (t.accent_text, None), "success": (t.success_text, None),
            "warning": (t.warning_text, None), "error": (t.error_text, None),
            "on-accent": (t.accent_fg, None),
        }.get(r, (t.window_fg, None))

    def _refresh(self):
        col, alpha = self._color_alpha()
        self.setPixmap(pixmap(self._name, self._size, col, alpha))
