"""
Pachul — models.py
GObject data model (PackageItem), the virtualized package ListView factory
(make_package_listview / PackageRowContent), and the sidebar NavRow.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, GObject, Pango

from i18n import tr
from icons import (themed_image, get_icon_texture,
                    resolve_desktop_icon_paintable, get_flatpak_icon_paintable)

# Populated once per full package reload by window.py (see
# backend.build_desktop_icon_map()) — maps pkg_name/Flatpak-app-id to that
# program's own Icon= value from its .desktop file. Empty until the first
# background scan completes, so early binds simply fall through to the
# existing symbolic icon set below; nothing here is required for the app
# to function.
INSTALLED_ICON_MAP = {}


def set_installed_icon_map(mapping):
    global INSTALLED_ICON_MAP
    INSTALLED_ICON_MAP = mapping or {}


def resolve_real_icon_paintable(pkg, size=22):
    """Try to find pkg's own real icon (installed repo/AUR program via the
    system icon theme, or a locally cached Flatpak download). Returns None
    if nothing is available yet — callers fall back to the symbolic icon
    set exactly as before."""
    if pkg.pkg_repo == "flatpak" and pkg.pkg_source_id:
        tex = get_flatpak_icon_paintable(pkg.pkg_source_id, size)
        if tex is not None:
            return tex
    icon_val = INSTALLED_ICON_MAP.get(pkg.pkg_source_id or pkg.pkg_name)
    if icon_val:
        return resolve_desktop_icon_paintable(icon_val, size)
    return None

# ─── Icon helper ──────────────────────────────────────────────────────────────
# Icons are rendered directly from our own inline SVG set (icons.py) instead
# of being looked up by name in the system/GTK icon theme. This used to go
# through Gio.ThemedIcon.new_from_names() with a list of fallback names, but
# that only helps when a name is entirely *absent* from the active theme —
# if the active theme's own index claims to have the icon but its file is
# missing or broken (as happened with a KDE Breeze variant and
# "utilities-terminal-symbolic", used below for bash/zsh/fish packages),
# GTK never reaches the fallback names at all. Rendering our own SVG
# directly sidesteps the system icon theme entirely, so this can't happen
# regardless of what's wrong with the active theme.

def make_icon(icon_names, pixel_size=18):
    """Create a Gtk.Image from a single icon name or a list of fallback names."""
    return themed_image(icon_names, pixel_size)


def set_button_icon(button, icon_names, pixel_size=18):
    """Set an icon-only button's icon using a fallback chain of icon names."""
    img = make_icon(icon_names, pixel_size)
    button.set_child(img)
    button.add_css_class("image-button")


# ─── Repository badge mapping ─────────────────────────────────────────────────

REPO_BADGE_CLASS = {
    "core":         "badge-core",
    "extra":        "badge-extra",
    "aur":          "badge-aur",
    "multilib":     "badge-multilib",
    "local":        "badge-local",
    "foreign":      "badge-foreign",
    "flatpak":      "badge-flatpak",
    "snap":         "badge-snap",
    "chaotic-aur":  "badge-chaotic-aur",
}

# ─── Small layout helper used by the row widgets below ─────────────────────────

def _make_box(vertical, gap, valign=None, halign=None, hexpand=False):
    """Gtk.Box with orientation, spacing and optional alignment / expansion."""
    box = Gtk.Box()
    box.set_orientation(Gtk.Orientation.VERTICAL if vertical
                        else Gtk.Orientation.HORIZONTAL)
    box.set_spacing(gap)
    if valign is not None:
        box.set_valign(valign)
    if halign is not None:
        box.set_halign(halign)
    if hexpand:
        box.set_hexpand(True)
    return box


# ─── Symbolic icons that stand in for well-known packages ─────────────────────
# Grouped by icon: every package listed under a symbol is shown with it.

_ICON_GROUPS = {
    "utilities-terminal-symbolic":
        ("linux", "bash", "zsh", "fish",),
    "drive-harddisk-symbolic":
        ("linux-firmware",),
    "package-x-generic-symbolic":
        ("base", "flatpak", "pacman", "yay", "paru",),
    "preferences-system-details-symbolic":
        ("git",),
    "text-x-script-symbolic":
        ("python", "python-pip", "nodejs", "npm",),
    "application-x-executable-symbolic":
        ("rust", "go", "docker",),
    "applications-engineering-symbolic":
        ("cmake",),
    "network-wireless-symbolic":
        ("networkmanager",),
    "network-server-symbolic":
        ("openssh",),
    "audio-speakers-symbolic":
        ("pipewire",),
    "audio-card-symbolic":
        ("alsa-utils",),
    "utilities-system-monitor-symbolic":
        ("htop",),
    "network-transmit-receive-symbolic":
        ("curl", "wget",),
    "text-editor-symbolic":
        ("vim", "nano", "visual-studio-code-bin",),
    "video-display-symbolic":
        ("mesa",),
    "document-revert-symbolic":
        ("timeshift",),
    "preferences-system-symbolic":
        ("systemd",),
    "web-browser-symbolic":
        ("firefox", "chromium", "google-chrome",),
    "applications-graphics-symbolic":
        ("gimp",),
    "applications-multimedia-symbolic":
        ("vlc",),
}

PKG_ICONS = {pkg: symbol
             for symbol, members in _ICON_GROUPS.items()
             for pkg in members}


def pkg_icon(name):
    return PKG_ICONS.get(name, "package-x-generic-symbolic")


# ─── GObject model ────────────────────────────────────────────────────────────

class PackageItem(GObject.Object):
    __gtype_name__ = 'PachulPackageItem'

    def __init__(self, name, version, repo="local", status="installed",
                 description="", foreign=False, source_id=None, new_version=""):
        super().__init__()
        (self.pkg_name, self.pkg_version, self.pkg_repo,
         self.pkg_status, self.pkg_description, self.pkg_foreign) = (
            name, version, repo, status, description, foreign)
        # Set for Flatpak (application ID, e.g. "org.gimp.GIMP") and Snap
        # (plain package name) entries — that's what the actual install/
        # remove commands need, kept separate from pkg_name so the display
        # name can stay human-friendly. None for ordinary pacman packages.
        self.pkg_source_id   = source_id
        # Version an "update" package would be upgraded to (empty if none
        # known — e.g. Flatpak remotes that publish no version string).
        self.pkg_new_version = new_version or ""
        # Temporärer UI-Backpointer, damit wir beim Klicken das Widget direkt refashen können
        self._bound_widget   = None


# ─── Shared selection state ────────────────────────────────────────────────

def version_text(item):
    """Version label for a package: "installed → available" while an update
    is pending and its new version is known, else just the version."""
    cur = item.pkg_version or ""
    new = getattr(item, "pkg_new_version", "") or ""
    if item.pkg_status == "update" and new and new != cur:
        return f"{cur} → {new}" if cur else f"→ {new}"
    return cur


def selection_key(item):
    """Unique key identifying one list entry in the checkbox selection.

    pkg_name alone is NOT unique: Flatpak/Snap entries use a friendly
    display name, and several entries can share one (runtimes in different
    branches, extensions, ...). Keying the selection by that name made such
    rows share one checkbox, counted them once ("Remove (2740)" for 2741
    rows) and — worse — acted on only one of them. Pacman/AUR names are
    unique, so those keep the plain name."""
    if item.pkg_repo in ("flatpak", "snap"):
        return f"{item.pkg_repo}:{item.pkg_source_id or item.pkg_name}"
    return item.pkg_name


class ListSelectionState:
    """Shared mutable checkbox-selection state for a package ListView's row
    factory.

    A single instance is captured by every row's `bind()` closure, so it is
    read fresh on every (re)bind — meaning recycled/virtualized rows always
    reflect the current selected set, even for rows that scroll into view
    only after a bulk change (Select All / Deselect All).
    """
    __slots__ = ("selected",)

    def __init__(self):
        self.selected = set()    # set of selection_key() strings


# ─── Package list row (virtualized ListView) ─────────────────────────────────

_STATUS_PILL_CSS = ("status-installed", "status-update")
_REPO_BADGE_CSS = tuple(set(REPO_BADGE_CLASS.values()))


class PackageRowContent(Gtk.Box):
    """Recyclable row widget for the package ListView.

    Built once per visible slot in `setup`, then re-bound to whatever
    PackageItem scrolls into it via `bind` — so only ~screenful of widgets
    ever exist, regardless of list size.
    """
    __gtype_name__ = 'PachulPackageRowContent'

    def __init__(self, on_selection_change=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.pkg = None
        self.sel_state = None
        self._on_selection_change = on_selection_change

        self.set_margin_top(9);    self.set_margin_bottom(9)
        self.set_margin_start(10); self.set_margin_end(10)
        self.add_css_class("pkg-row")

        # Selection checkbox — always shown, and its own click target: a
        # click here toggles selection *only*, a click anywhere else on the
        # row opens the package's detail view. Claiming the click sequence
        # on press stops it from also bubbling up to the ListView's own
        # row-activation gesture.
        self.checkbox = Gtk.Box()
        self.checkbox.add_css_class("pkg-checkbox")
        self.checkbox.set_size_request(20, 20)
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.set_halign(Gtk.Align.CENTER)
        self.checkbox.set_can_target(True)
        checkbox_click = Gtk.GestureClick()
        checkbox_click.set_button(1)
        checkbox_click.connect("pressed", self._on_checkbox_pressed)
        self.checkbox.add_controller(checkbox_click)

        self.checkbox_mark = Gtk.Label(label="✓")
        self.checkbox_mark.add_css_class("pkg-checkbox-mark")
        self.checkbox_mark.set_halign(Gtk.Align.CENTER)
        self.checkbox_mark.set_valign(Gtk.Align.CENTER)
        self.checkbox.append(self.checkbox_mark)
        self.append(self.checkbox)

        self.icon = Gtk.Image()
        self.icon.set_pixel_size(22)
        self.icon.set_valign(Gtk.Align.CENTER)
        self.icon.add_css_class("dim-label")
        self.append(self.icon)

        info_box = _make_box(True, 1, valign=Gtk.Align.CENTER, hexpand=True)

        self.name_label = Gtk.Label()
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.add_css_class("body")
        self.name_label.add_css_class("pkg-name")
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_weight_new(Pango.Weight.SEMIBOLD))
        self.name_label.set_attributes(attrs)
        info_box.append(self.name_label)

        self.desc_label = Gtk.Label()
        self.desc_label.set_halign(Gtk.Align.START)
        self.desc_label.add_css_class("caption")
        self.desc_label.add_css_class("dim-label")
        self.desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(self.desc_label)
        self.append(info_box)

        right = _make_box(True, 3, valign=Gtk.Align.CENTER, halign=Gtk.Align.END)
        badges_row = _make_box(False, 4, halign=Gtk.Align.END)
        self.status_badge = Gtk.Label()
        self.status_badge.add_css_class("row-status-pill")
        badges_row.append(self.status_badge)
        self.repo_badge = Gtk.Label()
        self.repo_badge.add_css_class("badge")
        badges_row.append(self.repo_badge)
        right.append(badges_row)

        self.ver_label = Gtk.Label()
        self.ver_label.add_css_class("caption")
        self.ver_label.add_css_class("dim-label")
        self.ver_label.set_halign(Gtk.Align.END)
        right.append(self.ver_label)
        self.append(right)

    def bind(self, pkg, sel_state=None):
        # Alten Backpointer entfernen, falls dieses Widget recycelt wird
        if self.pkg and hasattr(self.pkg, "_bound_widget") and self.pkg._bound_widget == self:
            self.pkg._bound_widget = None

        self.pkg = pkg
        self.sel_state = sel_state

        if pkg:
            pkg._bound_widget = self

        real_tex = resolve_real_icon_paintable(pkg, 22)
        if real_tex is not None:
            self.icon.set_from_paintable(real_tex)
        else:
            tex = get_icon_texture(pkg_icon(pkg.pkg_name), 22)
            if tex is not None:
                self.icon.set_from_paintable(tex)
            else:
                self.icon.set_from_icon_name(pkg_icon(pkg.pkg_name))
        self.name_label.set_label(pkg.pkg_name)
        self.desc_label.set_label(pkg.pkg_description or "")
        self.desc_label.set_visible(bool(pkg.pkg_description))

        # Visuelle Darstellung updaten
        self.update_selection_visuals()

        # Status pill — only for installed/update; clear stale classes first
        for cls in _STATUS_PILL_CSS:
            self.status_badge.remove_css_class(cls)
        if pkg.pkg_status in ("installed", "update"):
            is_update = pkg.pkg_status == "update"
            self.status_badge.set_label(tr("UPDATE") if is_update else tr("INSTALLED"))
            self.status_badge.add_css_class("status-update" if is_update else "status-installed")
            self.status_badge.set_visible(True)
        else:
            self.status_badge.set_visible(False)

        # Repo badge — swap class on every rebind
        repo_str = "aur" if pkg.pkg_foreign else (pkg.pkg_repo or "local")
        for cls in _REPO_BADGE_CSS:
            self.repo_badge.remove_css_class(cls)
        self.repo_badge.set_label(repo_str.upper())
        self.repo_badge.add_css_class(REPO_BADGE_CLASS.get(repo_str.lower(), "badge-local"))

        self.ver_label.set_label(version_text(pkg))

    def update_selection_visuals(self):
        """Reflects whether this row's package is checked. The checkbox
        itself is always visible now — only its checked/unchecked state
        changes."""
        if not self.pkg or not self.sel_state:
            return
        is_selected = selection_key(self.pkg) in self.sel_state.selected
        self.checkbox_mark.set_visible(is_selected)
        if is_selected:
            self.checkbox.add_css_class("pkg-checkbox-checked")
            self.add_css_class("pkg-row-selected")
        else:
            self.checkbox.remove_css_class("pkg-checkbox-checked")
            self.remove_css_class("pkg-row-selected")

    def _on_checkbox_pressed(self, gesture, n_press, x, y):
        # Claim the sequence so it doesn't also bubble up and activate the
        # row (which would open the detail view instead of/as well as
        # toggling the checkbox).
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        if not self.pkg or self.sel_state is None:
            return
        name = selection_key(self.pkg)
        if name in self.sel_state.selected:
            self.sel_state.selected.discard(name)
        else:
            self.sel_state.selected.add(name)
        self.update_selection_visuals()
        if self._on_selection_change:
            self._on_selection_change()


def make_package_listview(on_activate, on_selection_change=None, sel_state=None):
    """Build a virtualized package ListView backed by a Gio.ListStore.

    Returns (listview, store, selection, sel_state).
    """
    store = Gio.ListStore(item_type=PackageItem)
    selection = Gtk.SingleSelection(model=store)
    selection.set_autoselect(False)
    selection.set_can_unselect(True)

    if sel_state is None:
        sel_state = ListSelectionState()

    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", lambda f, li: li.set_child(PackageRowContent(on_selection_change)))
    factory.connect("bind", lambda f, li: li.get_child().bind(li.get_item(), sel_state))

    listview = Gtk.ListView(model=selection, factory=factory)
    listview.add_css_class("navigation-sidebar")
    listview.set_single_click_activate(True)

    def _activate(lv, pos):
        item = store.get_item(pos)
        if item is not None:
            on_activate(item)

    listview.connect("activate", _activate)
    return listview, store, selection, sel_state


# ─── Row in the sidebar navigation ────────────────────────────────────────────

class NavRow(Gtk.ListBoxRow):
    def __init__(self, icon_name, label, count=None, badge_css=None):
        super().__init__()
        self.set_activatable(True)
        self.add_css_class("nav-row")

        content = _make_box(False, 10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        content.set_margin_top(7)
        content.set_margin_bottom(7)

        symbol = make_icon(icon_name, 18)
        symbol.set_valign(Gtk.Align.CENTER)
        symbol.add_css_class("dim-label")
        content.append(symbol)

        title = Gtk.Label(label=label, hexpand=True, halign=Gtk.Align.START,
                          valign=Gtk.Align.CENTER)
        content.append(title)

        self.count_lbl = None
        if count is not None:
            digits = str(count)
            classes = ["count-badge"] + ([badge_css] if badge_css else [])
            badge = Gtk.Label(label=digits, valign=Gtk.Align.CENTER,
                              css_classes=classes)
            # numeric counts of 0 stay hidden; non-numeric text is always shown
            badge.set_visible(int(digits) > 0 if digits.isdigit() else True)
            content.append(badge)
            self.count_lbl = badge

        self._badge_css = badge_css
        self.set_child(content)

    def set_count(self, n):
        badge = self.count_lbl
        if badge is None:
            return
        badge.set_label(str(n))
        badge.set_visible(n > 0)
