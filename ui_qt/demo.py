"""
Pachul — ui_qt/demo.py
Look prototype: the main window as in the libadwaita version, built from the
Qt design system, with fake data. Nothing here touches pacman.

    python3 -m ui_qt.demo                       # follow the system scheme
    python3 -m ui_qt.demo --mode dark
    python3 -m ui_qt.demo --accent system       # use the desktop's accent colour

The package list is a QListView + model + painting delegate (not a widget
per row), which is what keeps 100,000+ packages smooth.
"""

import argparse
import random
import sys

from .qt import (
    Qt, QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListView,
    QStyledItemDelegate, QStyle, QAbstractListModel, QModelIndex, QSplitter,
    QMenu, QLineEdit, QPlainTextEdit, QProgressBar, QToolButton, QAbstractItemView,
    QFrame, QScrollArea, QEvent, QSize, QRectF, QTimer, QFontMetrics, QPainter,
    QColor, QAction, Signal,
)
from . import theme
from .icons_qt import IconLabel, pixmap, icon as qicon
from .widgets import (
    Label, ElidedLabel, Separator, Panel, HeaderBar, Card, Group, Row, SwitchRow,
    ComboRow, EntryRow, ExpanderRow, StatCard, NavRow, Pill, Banner, StatusPage,
    ToastOverlay, PreferencesPage, Dialog, IconButton, TextIconButton, button,
    pill_font, pill_size, draw_pill, _scaled_font as scaled_font,
)

ROLE_REC = 0x0100          # Qt.UserRole
ROLE_CHECKED = 0x0101


# ─── Fake data ───────────────────────────────────────────────────────────────

_UPDATES = [
    ("grub-theme-live-common", "20.2-18", "Manjaro Linux grub theme for live ISO (common files)", "extra"),
    ("grub-theme-manjaro", "20.2-18", "Manjaro Linux grub theme", "extra"),
    ("manjaro-browser-settings", "20231111-3", "Manjaro Linux settings browser defaults", "extra"),
    ("media-downloader", "5.6.6-2", "A Qt/C++ front end to yt-dlp, youtube-dl, gallery-dl, lux, you-get, svtplay-dl, aria2c, wget and safari books.", "chaotic-aur"),
    ("microsoft-edge-stable-bin", "156.0.4314.50-1", "A browser that combines a minimal design with sophisticated technology to make the web faster, safer, and easier", "chaotic-aur"),
    ("python-selenium", "4.51.0-1", "", "aur"),
    ("shelly-bin", "3.1.9-1", "", "aur"),
    ("shelly-flatpak-backend-bin", "3.1.9-1", "", "aur"),
    ("zen-browser-bin", "1.23.4b-1", "A feature packed Firefox-based web browser", "chaotic-aur"),
    ("zoom", "7.2.1-1", "Video Conferencing and Web Conferencing Service", "chaotic-aur"),
]
_PREFIX = ["lib", "python-", "perl-", "qt6-", "kde-", "gnome-", "ttf-", "xorg-",
           "mesa-", "gst-plugin-", "haskell-", "ruby-", "rust-", "go-", "nodejs-"]
_STEM = ["audit", "brotli", "dbus", "debug", "dns", "fuse", "gtk", "harfbuzz",
         "icu", "json", "kerberos", "lz4", "mpv", "nss", "ogg", "pango",
         "readline", "sqlite", "tiff", "udev", "vulkan", "wayland", "xz", "zstd"]
_DESC = ["Plugins for the audit event dispatcher", "Generic-purpose lossless compression algorithm",
         "Freedesktop.org message bus system", "Handle ELF object files and DWARF debugging",
         "POSIX compliant shell that aims to be small", "The Berkeley DB embedded database system",
         "DNSSEC trust anchors for the root zone", "FUSE filesystem in userspace",
         "A fast and light-weight JSON parser", "Library for rendering and layout of text"]


def make_records(n=30000):
    rnd = random.Random(7)
    recs = [(a, b, c, d, "update") for a, b, c, d in _UPDATES]
    repos = (["core"] * 2 + ["extra"] * 40 + ["multilib"] * 1 + ["aur"] * 35 +
             ["chaotic-aur"] * 15 + ["flatpak"] * 1)
    for i in range(n - len(recs)):
        name = f"{rnd.choice(_PREFIX)}{rnd.choice(_STEM)}-{i}"
        ver = f"{rnd.randint(0, 9)}.{rnd.randint(0, 40)}.{rnd.randint(0, 9)}-{rnd.randint(1, 3)}"
        desc = rnd.choice(_DESC) if rnd.random() > 0.08 else ""
        status = "installed" if rnd.random() < 0.09 else "available"
        recs.append((name, ver, desc, rnd.choice(repos), status))
    return recs


# ─── Model & delegate ────────────────────────────────────────────────────────

class PackageModel(QAbstractListModel):
    checked_changed = Signal()

    def __init__(self, records, parent=None):
        super().__init__(parent)
        self._all = records
        self._rows = list(range(len(records)))
        self._checked = set()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None
        i, r = self._rows[index.row()], int(role)
        if r == ROLE_REC:
            return list(self._all[i])
        if r == ROLE_CHECKED:
            return i in self._checked
        if r == int(Qt.ItemDataRole.DisplayRole):
            return self._all[i][0]
        return None

    def setData(self, index, value, role=int(Qt.ItemDataRole.EditRole)):
        if index.isValid() and int(role) == ROLE_CHECKED:
            i = self._rows[index.row()]
            (self._checked.add if value else self._checked.discard)(i)
            self.dataChanged.emit(index, index, [ROLE_CHECKED])
            self.checked_changed.emit()
            return True
        return False

    def record(self, row):
        return self._all[self._rows[row]]

    def apply(self, predicate):
        self.beginResetModel()
        self._rows = [i for i, r in enumerate(self._all) if predicate(r)]
        self.endResetModel()

    def checked_count(self):
        return len(self._checked)

    def clear_checked(self):
        self._checked.clear()
        self.layoutChanged.emit()
        self.checked_changed.emit()


class PackageDelegate(QStyledItemDelegate):
    ROW_H = 60

    @staticmethod
    def _rect(option):
        return QRectF(option.rect).adjusted(8, 1, -8, -1)

    @staticmethod
    def _checkbox(rect):
        return QRectF(rect.left() + 16, rect.center().y() - 11, 22, 22)

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_H)

    def paint(self, p, option, index):
        rec = index.data(ROLE_REC)
        if not rec:
            return
        name, ver, desc, repo, status = rec
        t = theme.T
        checked = bool(index.data(ROLE_CHECKED))
        rect = self._rect(option)
        base = option.font

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(t.accent_wash(0.14) if selected else t.btn_bg)
            p.drawRoundedRect(rect, 10, 10)

        # checkbox
        cb = self._checkbox(rect)
        if checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(t.accent_bg)
            p.drawRoundedRect(cb, 6, 6)
            tick = pixmap("object-select-symbolic", 16, t.accent_fg)
            p.drawPixmap(int(cb.center().x() - 8), int(cb.center().y() - 8), tick)
        else:
            edge = QColor(t.window_fg)
            edge.setAlphaF(0.42)
            pen = p.pen()
            pen.setColor(edge)
            pen.setWidthF(2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(cb.adjusted(1, 1, -1, -1), 6, 6)

        # icon
        ic = pixmap("package-x-generic-symbolic", 22, t.window_fg)
        p.drawPixmap(int(rect.left() + 50), int(rect.center().y() - 11), ic)

        # right column: pills, then version below
        pf = pill_font(base)
        pills = []
        if status == "update":
            pills.append(("UPDATE", "update"))
        elif status == "installed":
            pills.append(("INSTALLIERT", "installed"))
        pills.append((repo.upper(), repo))
        x_right = rect.right() - 14
        y_c = rect.top() + 19
        for text, tone in reversed(pills):
            sz = pill_size(text, pf)
            r = QRectF(x_right - sz.width(), y_c - sz.height() / 2, sz.width(), sz.height())
            draw_pill(p, r, text, tone, pf)
            x_right = r.left() - 5
        pills_left = x_right

        dim = QColor(t.window_fg)
        dim.setAlphaF(0.58)
        vf = scaled_font(base, 0.85)
        vfm = QFontMetrics(vf)
        ver_w = vfm.horizontalAdvance(ver)
        p.setFont(vf)
        p.setPen(dim)
        p.drawText(QRectF(rect.right() - 14 - ver_w - 4, rect.top() + 32, ver_w + 4, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, ver)

        # name + description
        x0 = rect.left() + 86
        nf = scaled_font(base, 1.0)
        nf.setBold(True)
        nfm = QFontMetrics(nf)
        name_w = max(40, pills_left - 10 - x0)
        if desc:
            name_y = rect.top() + 8
        else:
            name_y = rect.center().y() - 11
        p.setFont(nf)
        p.setPen(t.window_fg)
        p.drawText(QRectF(x0, name_y, name_w, 22),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   nfm.elidedText(name, Qt.TextElideMode.ElideRight, int(name_w)))
        if desc:
            df = scaled_font(base, 0.85)
            dfm = QFontMetrics(df)
            desc_w = max(40, rect.right() - 14 - ver_w - 16 - x0)
            p.setFont(df)
            dc = QColor(t.window_fg)
            dc.setAlphaF(0.65)
            p.setPen(dc)
            p.drawText(QRectF(x0, rect.top() + 31, desc_w, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       dfm.elidedText(desc, Qt.TextElideMode.ElideRight, int(desc_w)))
        p.restore()

    def editorEvent(self, event, model, option, index):
        if (event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton):
            hit = self._checkbox(self._rect(option)).adjusted(-8, -8, 8, 8)
            if hit.contains(event.position()):
                model.setData(index, not bool(index.data(ROLE_CHECKED)), ROLE_CHECKED)
                return True
        return False


# ─── Dialogs ─────────────────────────────────────────────────────────────────

def _close_button(dlg):
    b = button("Schließen", "flat")
    b.clicked.connect(dlg.close)
    dlg.header.pack_start(b)


def tools_dialog(parent, on_pick):
    dlg = Dialog(parent, "Werkzeuge", 660, 720)
    _close_button(dlg)

    search = QLineEdit()
    search.setPlaceholderText("Werkzeuge durchsuchen…")
    search.addAction(QAction(qicon("system-search-symbolic", 16, theme.T.dim_fg), search),
                     QLineEdit.ActionPosition.LeadingPosition)
    wrap = QWidget()
    wl = QVBoxLayout(wrap)
    wl.setContentsMargins(14, 4, 14, 8)
    wl.addWidget(search)
    dlg.body.addWidget(wrap)

    page = PreferencesPage()
    catalog = [
        ("Software & Quellen", [
            ("package-x-generic-symbolic", "Lokales Paket installieren", "Eine heruntergeladene .tar.gz-, .pkg.tar.*-, .deb-, .rpm- oder .flatpak-Datei installieren"),
            ("network-server-symbolic", "Repositories verwalten", "Softwarequellen aktivieren, deaktivieren oder hinzufügen"),
            ("network-transmit-receive-symbolic", "Spiegelserver bewerten", "Mirror nach Geschwindigkeit sortieren, damit Downloads schneller werden"),
        ]),
        ("Wartung", [
            ("user-trash-symbolic", "Waisen finden", "Pakete entfernen, die von nichts mehr benötigt werden"),
            ("folder-download-symbolic", "Cache leeren", "Speicherplatz freigeben, den heruntergeladene Paketdateien belegen"),
            ("document-open-recent-symbolic", "Paketverlauf", "Ansehen, was wann installiert, aktualisiert oder entfernt wurde"),
        ]),
        ("System", [
            ("utilities-system-monitor-symbolic", "Systeminfo", "Betriebssystem, Kernel, Hardware und Paketstatistik"),
            ("drive-harddisk-symbolic", "Konfigurations-Backup", "Wichtige Konfigurationsdateien deines Systems sichern"),
        ]),
    ]
    groups = []
    for cat, items in catalog:
        g = Group(cat)
        rows = []
        for icon_name, title, desc in items:
            r = Row(title, desc, icon_name, activatable=True)
            r.add_suffix(IconLabel("go-next-symbolic", 16, "dim"))
            r.activated.connect(lambda t=title: (dlg.close(), on_pick(t)))
            g.add(r)
            rows.append((r, f"{title} {desc}".lower()))
        groups.append((g, rows))
        page.add(g)
    dlg.set_content(page)

    def filt(text):
        q = text.strip().lower()
        for g, rows in groups:
            n = 0
            for r, hay in rows:
                vis = (not q) or all(w in hay for w in q.split())
                r.setVisible(vis)
                n += vis
            g.setVisible(n > 0)
            g.refresh()

    search.textChanged.connect(filt)
    search.setFocus()
    return dlg


def preferences_dialog(parent):
    dlg = Dialog(parent, "Einstellungen", 600, 700)
    _close_button(dlg)
    page = PreferencesPage()

    g = Group("Erscheinungsbild", "Der Look folgt standardmäßig dem System.")
    mode = ComboRow("Farbschema", "", ["Wie das System", "Hell", "Dunkel"])
    mode.combo.setCurrentIndex({"auto": 0, "light": 1, "dark": 2}.get(theme._state["mode"], 0))
    mode.changed.connect(lambda i: theme.set_mode(["auto", "light", "dark"][i]))
    accent = ComboRow("Akzentfarbe", "", ["Adwaita-Blau", "Desktop-Akzent (Plasma)"])
    accent.combo.setCurrentIndex(1 if theme._state["accent"] == "system" else 0)
    accent.changed.connect(lambda i: theme.set_accent(["adwaita", "system"][i]))
    g.add(mode)
    g.add(accent)
    page.add(g)

    g = Group("Updates")
    g.add(SwitchRow("Hintergrund-Benachrichtigungen", "Regelmäßig auf neue Updates prüfen", True))
    g.add(SwitchRow("Snapshot vor System-Upgrade", "Timeshift oder Snapper, falls vorhanden", False))
    g.add(ComboRow("Prüfintervall", "", ["30 Minuten", "1 Stunde", "6 Stunden", "Täglich"]))
    page.add(g)

    g = Group("Erweitert")
    ex = ExpanderRow("AUR-Optionen", "Helfer und Build-Verhalten", "package-x-generic-symbolic")
    ex.add_row(EntryRow("AUR-Helfer", "yay"))
    ex.add_row(SwitchRow("PKGBUILD vor dem Bauen anzeigen", "", True))
    ex.add_row(SwitchRow("Build-Verzeichnis nach Installation löschen", "", True))
    g.add(ex)
    g.add(Row("Cache-Verzeichnis", "/var/cache/pacman/pkg", "folder-symbolic", activatable=True))
    page.add(g)
    dlg.set_content(page)
    return dlg


def terminal_dialog(parent, title):
    dlg = Dialog(parent, title, 760, 520)
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(16, 12, 16, 16)
    v.setSpacing(12)
    v.addWidget(Label(title, "title-3"))
    status = Label("Wird installiert…", "dim")
    v.addWidget(status)
    term = QPlainTextEdit()
    term.setReadOnly(True)
    theme.set_kind(term, "terminal")
    term.setPlainText(
        "==> Entpacke Archiv…\n==> Prüfe Abhängigkeiten\n"
        "==> Starte makepkg\n\n"
        "[sudo] Passwort wird über pkexec abgefragt\n"
        "(1/1) Installiere zoom                     [######################] 100%\n"
        ":: Verarbeite Paketänderungen…\n")
    v.addWidget(term, 1)
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(62)
    v.addWidget(bar)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = button("Abbrechen")
    close = button("Fertig", "suggested")
    cancel.clicked.connect(dlg.close)
    close.clicked.connect(dlg.close)
    row.addWidget(cancel)
    row.addWidget(close)
    v.addLayout(row)
    dlg.set_content(box)
    return dlg


# ─── Detail panel ────────────────────────────────────────────────────────────

class DetailPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("window", "left", parent)
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.banner = Banner("Im AUR ist eine neuere Version verfügbar.", "Aus AUR bauen")
        self.banner.hide()
        lay.addWidget(self.banner)

        page = PreferencesPage(520)
        lay.addWidget(page, 1)

        hero = Card(separators=False)
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(18, 18, 18, 16)
        hv.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(14)
        self.tile = _IconTile()
        top.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.name = Label("", "title-3", wrap=True)
        self.desc = Label("", "dim", wrap=True)
        col.addWidget(self.name)
        col.addWidget(self.desc)
        top.addLayout(col, 1)
        hv.addLayout(top)
        self.pill_row = QHBoxLayout()
        self.pill_row.setSpacing(6)
        hv.addLayout(self.pill_row)
        btns = QHBoxLayout()
        btns.setSpacing(8)
        self.btn_install = button("Installieren", "suggested")
        self.btn_remove = button("Deinstallieren", "destructive")
        self.btn_more = button("Neu installieren")
        for b in (self.btn_install, self.btn_remove, self.btn_more):
            btns.addWidget(b)
        btns.addStretch(1)
        hv.addLayout(btns)
        page.add(hero)

        self.info = Group("Informationen")
        self.rows = {}
        for key in ("Version", "Repository", "Download-Größe", "Installierte Größe",
                    "Lizenz", "Webseite"):
            r = Row(key, "–", activatable=(key == "Webseite"))
            if key == "Webseite":
                r.add_suffix(IconLabel("adw-external-link-symbolic", 16, "dim"))
            self.rows[key] = r
            self.info.add(r)
        page.add(self.info)

        self.deps = Group("Abhängigkeiten")
        self.dep_exp = ExpanderRow("Benötigt", "5 Pakete", "package-x-generic-symbolic")
        for d in ("glibc", "gcc-libs", "openssl", "zlib", "bash"):
            r = Row(d, "", activatable=True)
            r.add_suffix(IconLabel("go-next-symbolic", 16, "dim"))
            self.dep_exp.add_row(r)
        self.deps.add(self.dep_exp)
        self.deps.add(ExpanderRow("Optional", "2 Pakete", "package-x-generic-symbolic"))
        page.add(self.deps)

    def show_pkg(self, rec):
        name, ver, desc, repo, status = rec
        self.name.setText(name)
        self.desc.setText(desc or "Keine Beschreibung verfügbar.")
        for i in reversed(range(self.pill_row.count())):
            it = self.pill_row.takeAt(i)
            if it is not None and it.widget() is not None:
                it.widget().deleteLater()
        self.pill_row.addWidget(Pill(repo.upper(), repo))
        self.pill_row.addWidget(Pill(ver, "neutral"))
        if status != "available":
            self.pill_row.addWidget(Pill("UPDATE" if status == "update" else "INSTALLIERT", status))
        self.pill_row.addStretch(1)
        installed = status != "available"
        self.btn_install.setText("Aktualisieren" if status == "update" else "Installieren")
        self.btn_install.setEnabled(status != "installed")
        self.btn_remove.setEnabled(installed)
        self.btn_more.setEnabled(installed)
        self.rows["Version"].set_subtitle(ver)
        self.rows["Repository"].set_subtitle(repo)
        self.rows["Download-Größe"].set_subtitle("4,2 MiB")
        self.rows["Installierte Größe"].set_subtitle("17,8 MiB")
        self.rows["Lizenz"].set_subtitle("GPL-2.0-or-later")
        self.rows["Webseite"].set_subtitle(f"https://example.org/{name}")
        self.banner.set_revealed(repo in ("aur", "chaotic-aur") and status == "update")


class _IconTile(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(58, 58)
        self._ic = IconLabel("package-x-generic-symbolic", 30, "accent", self)
        self._ic.move(14, 14)
        theme.signals.changed.connect(self.update)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.T.accent_wash(0.14))
        p.drawRoundedRect(QRectF(self.rect()), 14, 14)


# ─── Main window ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pachul")
        self.resize(1200, 760)
        self.setMinimumSize(760, 480)

        self.records = make_records()
        self.model = PackageModel(self.records)
        self._cat = ("updates",)
        self._text = ""

        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        h.addWidget(self._build_content(), 1)
        self.setCentralWidget(root)
        self.toasts = ToastOverlay(root)

        self._select_nav(("updates",))

    # -- sidebar -------------------------------------------------------------
    def _build_sidebar(self):
        side = Panel("sidebar", "right")
        side.setFixedWidth(250)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        head = QWidget()
        head.setFixedHeight(47)
        hl = QHBoxLayout(head)
        title = Label("Pachul", "heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(title)
        v.addWidget(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        col = QWidget()
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 4, 0, 12)
        cl.setSpacing(0)

        total = len(self.records)
        n_aur = sum(1 for r in self.records if r[3] in ("aur",))
        n_upd = sum(1 for r in self.records if r[4] == "update")
        stats = QHBoxLayout()
        stats.setContentsMargins(10, 4, 10, 10)
        stats.setSpacing(8)
        stats.addWidget(StatCard(total, "Gesamt", "accent"), 3)
        stats.addWidget(StatCard(n_aur, "AUR", "aur"), 3)
        stats.addWidget(StatCard(n_upd, "Updates", "updates"), 2)
        cl.addLayout(stats)

        self.nav = {}

        def add_nav(key, icon_name, label, count=None, tone="neutral"):
            r = NavRow(icon_name, label, count, tone)
            r.clicked.connect(lambda k=key: self._select_nav(k))
            self.nav[key] = r
            cl.addWidget(r)

        def section(text):
            cl.addSpacing(6)
            sep = Separator()
            m = QHBoxLayout()
            m.setContentsMargins(10, 0, 10, 0)
            m.addWidget(sep)
            cl.addLayout(m)
            lab = Label(text.upper(), "section")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setContentsMargins(0, 10, 0, 6)
            cl.addWidget(lab)

        add_nav(("all",), "package-x-generic-symbolic", "Alle Pakete")
        add_nav(("updates",), "software-update-available-symbolic", "Updates", n_upd, "update")

        section("Neu")
        add_nav(("new",), "list-add-symbolic", "Alle neuen Pakete", total - n_upd, "installed")
        repos = [("core", "drive-harddisk-symbolic"), ("extra", "folder-symbolic"),
                 ("multilib", "folder-symbolic"), ("aur", "utilities-terminal-symbolic"),
                 ("flatpak", "package-x-generic-symbolic"),
                 ("chaotic-aur", "network-workgroup-symbolic")]
        for repo, ic in repos:
            n = sum(1 for r in self.records if r[3] == repo)
            add_nav(("repo", repo), ic, repo, n, "installed")

        section("Installierte Pakete")
        n_inst = sum(1 for r in self.records if r[4] != "available")
        add_nav(("installed",), "emblem-ok-symbolic", "Alle installierten Pakete", n_inst)
        for repo, ic in repos:
            n = sum(1 for r in self.records if r[3] == repo and r[4] != "available")
            add_nav(("inst_repo", repo), ic, repo, n)

        cl.addStretch(1)
        scroll.setWidget(col)
        v.addWidget(scroll, 1)
        return side

    # -- content -------------------------------------------------------------
    def _build_content(self):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        hdr = HeaderBar(flat=True)
        tools = IconButton("hammer-wrench-symbolic", "Werkzeuge (Strg+T)", size=22)
        tools.clicked.connect(self._open_tools)
        hdr.pack_end(tools)
        # one-click light/dark switch (the full choice incl. "follow system"
        # lives in the menu under "Erscheinungsbild" and in the settings)
        self.mode_btn = IconButton("weather-clear-night-symbolic", "Hell/Dunkel umschalten")
        self.mode_btn.clicked.connect(
            lambda: theme.set_mode("light" if theme.is_dark() else "dark"))
        theme.signals.changed.connect(self._sync_mode_icon)
        self._sync_mode_icon()
        hdr.pack_end(self.mode_btn)
        menu_btn = IconButton("open-menu-symbolic", "Hauptmenü")
        menu_btn.setMenu(self._build_menu())
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        hdr.pack_end(menu_btn)
        v.addWidget(hdr)

        sw = QWidget()
        sl = QHBoxLayout(sw)
        sl.setContentsMargins(10, 0, 10, 10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pakete suchen, z. B. firefox, vlc, git…")
        self.search.setClearButtonEnabled(True)
        self._search_action = QAction(qicon("system-search-symbolic", 16, theme.T.dim_fg), self.search)
        self.search.addAction(self._search_action, QLineEdit.ActionPosition.LeadingPosition)
        theme.signals.changed.connect(
            lambda: self._search_action.setIcon(qicon("system-search-symbolic", 16, theme.T.dim_fg)))
        self.search.textChanged.connect(self._on_search)
        sl.addWidget(self.search)
        v.addWidget(sw)
        v.addWidget(Separator())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(PackageDelegate(self.view))
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.verticalScrollBar().setSingleStep(28)
        self.view.selectionModel().currentChanged.connect(self._on_current)
        split.addWidget(self.view)

        self.detail = DetailPanel()
        self.detail.hide()
        split.addWidget(self.detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([700, 420])
        v.addWidget(split, 1)

        v.addWidget(self._build_bottom())
        self.model.checked_changed.connect(self._update_count)
        return wrap

    def _sync_mode_icon(self):
        self.mode_btn.set_icon("weather-clear-symbolic" if theme.is_dark()
                               else "weather-clear-night-symbolic")

    def _build_bottom(self):
        bar = Panel("window", "top")
        bar.setFixedHeight(56)
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(8)
        sel = IconButton("edit-select-all-symbolic", "Alle auswählen")
        sel.clicked.connect(self._select_all_visible)
        h.addWidget(sel)
        self.btn_main = button("Alle aktualisieren", "suggested")
        self.btn_main.clicked.connect(lambda: self.toasts.show_toast("Update gestartet"))
        h.addWidget(self.btn_main)
        h.addStretch(1)
        self.count_lbl = Label("", "subtitle")
        h.addWidget(self.count_lbl)
        h.addStretch(1)
        chk = button("Auf Updates prüfen")
        chk.clicked.connect(lambda: self.toasts.show_toast("Suche nach Updates…"))
        h.addWidget(chk)
        return bar

    def _build_menu(self):
        m = QMenu(self)

        def act(menu, text, fn):
            a = menu.addAction(text)
            a.triggered.connect(lambda _=False: fn())
            return a

        act(m, "Datenbanken synchronisieren", lambda: self.toasts.show_toast("Datenbanken werden synchronisiert…"))
        act(m, "Nach Updates suchen", lambda: self.toasts.show_toast("Suche nach Updates…"))
        act(m, "Liste aktualisieren", lambda: self.toasts.show_toast("Liste aktualisiert"))
        m.addSeparator()
        act(m, "Einstellungen", lambda: preferences_dialog(self).exec())
        act(m, "Über Pachul", lambda: self.toasts.show_toast("Pachul – Look-Prototyp (Qt)"))
        return m

    # -- behaviour -----------------------------------------------------------
    def _open_tools(self):
        def picked(title):
            if title.startswith("Lokales Paket"):
                terminal_dialog(self, "Lokales Paket installieren").exec()
            else:
                self.toasts.show_toast(f"„{title}“ würde sich jetzt öffnen")
        tools_dialog(self, picked).exec()

    def _select_nav(self, key):
        self._cat = key
        for k, r in self.nav.items():
            r.set_selected(k == key)
        self._refilter()

    def _on_search(self, text):
        self._text = text.strip().lower()
        self._refilter()

    def _refilter(self):
        cat, text = self._cat, self._text

        def ok(rec):
            name, _v, desc, repo, status = rec
            if text and text not in name.lower() and text not in desc.lower():
                return False
            k = cat[0]
            if k in ("all", "new"):
                return True
            if k == "updates":
                return status == "update"
            if k == "installed":
                return status != "available"
            if k == "repo":
                return repo == cat[1]
            if k == "inst_repo":
                return repo == cat[1] and status != "available"
            return True

        self.model.apply(ok)
        self.detail.hide()
        self._update_count()
        self.btn_main.setVisible(cat[0] == "updates")

    def _update_count(self):
        n, tot = self.model.rowCount(), len(self.records)
        sel = self.model.checked_count()
        self.count_lbl.setText(f"{sel} ausgewählt · {n} von {tot} Paketen" if sel
                               else f"{n} von {tot} Paketen")

    def _select_all_visible(self):
        for row in range(min(self.model.rowCount(), 5000)):
            self.model.setData(self.model.index(row), True, ROLE_CHECKED)

    def _on_current(self, current, _prev):
        if current.isValid():
            self.detail.show_pkg(self.model.record(current.row()))
            self.detail.show()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pachul Qt look prototype")
    ap.add_argument("--mode", choices=["auto", "light", "dark"], default="auto")
    ap.add_argument("--accent", choices=["adwaita", "system"], default="adwaita")
    args, qt_args = ap.parse_known_args(argv)

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("Pachul")
    theme.install(app, args.mode, args.accent)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
